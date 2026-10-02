#!/usr/bin/env python3
"""Structured-template consistency helper for implement-plan.

Static and hermetic: it reads the plan text only. Inconsistencies are FAIL (exit 1);
recorded blocked probes are BLOCK (exit 3). This helper is not permission authority.
Legacy and pre-v4 plans are normalized on read without rewriting decision provenance.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FIELD_RE = re.compile(r"^-?[ \t]*(?P<key>[A-Za-z][A-Za-z -]*):[ \t]*(?P<value>.*?)[ \t]*$", re.MULTILINE)
TASK_RE = re.compile(r"^### Task (?P<id>\d+):.*?(?=^### Task |^## |\Z)", re.MULTILINE | re.DOTALL)
TABLE_RE = re.compile(r"^\|(?P<cells>.+)\|\s*$", re.MULTILINE)
RESULT_RE = re.compile(r"^-\s*(?P<pid>.+?)\s+(?P<state>ready|blocked|unverifiable)\s*:\s*(?P<detail>.*)$",
                       re.MULTILINE)

CONTEXT_FIELDS = ("Plan path", "Unit tests", "Code review")
ORIGINS = ("host-plan-mode", "existing-input", "backlog-requirement", "generated-project-root")
SOURCES = ("user", "flag", "project", "assessment", "auto-assessment")
DECISIONS = ("selected", "skipped")
TASK_FIELDS = ("Status", "Depends on", "Files", "Description", "Done when", "ACs")
STATUSES = ("pending", "scaffolded", "in-progress", "complete", "blocked")
MODES = ("existing-method", "simple-new", "complex-backbone")
AUTONOMY_STATES = ("verified-ready", "unverifiable-with-fallback", "verified-blocked")
PROBE_KINDS = ("path", "command", "command-version", "auth", "env", "url", "node-deps", "dotnet-restore",
               "manual")
LEGACY_DECISIONS = {"requested": "selected", "not requested": "skipped"}


def fields(text):
    output = {}
    for match in FIELD_RE.finditer(text):
        output.setdefault(match["key"].strip(), []).append(match["value"].strip())
    return output


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE)
    return match.group(1) if match else ""


def rows(text):
    parsed = []
    for row in TABLE_RE.finditer(text):
        cells = [cell.strip() for cell in row.group("cells").split("|")]
        if cells and cells[0].lower() == "id":
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue
        parsed.append(cells)
    return parsed


def derived_file_probes(text):
    """Reuse preflight's parser so the two scripts cannot drift on what counts as a derived probe."""
    script = Path(__file__).with_name("preflight.py")
    spec = importlib.util.spec_from_file_location("implement_plan_preflight", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return [probe.pid for probe in module.derived_probes(text)]


def normalize(data, plan_path=None):
    """Map legacy Context shapes while preserving recorded assessment provenance."""
    normalized = {key: list(values) for key, values in data.items()}
    for label in ("Unit tests", "Code review"):
        value = (normalized.get(label) or [""])[0]
        if value in LEGACY_DECISIONS:
            normalized[label] = [LEGACY_DECISIONS[value]]
            normalized.setdefault(f"{label} source", ["user"])
            normalized.setdefault(f"{label} reason", [f"legacy explicit choice: {value}"])
        for dropped in (f"{label} decision", f"{label} recommendation", f"{label} recommendation reason",
                        "TDD decision", "TDD recommendation", "TDD recommendation reason", "Depth"):
            normalized.pop(dropped, None)
    if "Plan path origin" not in normalized:
        normalized["Plan path origin"] = ["existing-input"]
        normalized.setdefault("Plan path evidence", [f"existing plan supplied as input: {plan_path}"])
    if "Plan path" not in normalized:
        if plan_path:
            normalized["Plan path"] = [str(plan_path)]
        elif data.get("Plan path evidence"):
            normalized["Plan path"] = list(data["Plan path evidence"])
    return normalized


def one(data, key, results, label="Context"):
    values = data.get(key, [])
    if len(values) != 1:
        results.append(("FAIL", f"{label} field must occur once: {key}" if values
                        else f"missing {label} field: {key}"))
        return None
    if not values[0]:
        results.append(("FAIL", f"{label} field must be non-empty: {key}"))
    return values[0]


def context_contract(data, results):
    for key in CONTEXT_FIELDS:
        one(data, key, results)
    origin = (data.get("Plan path origin") or [None])[0]
    evidence = (data.get("Plan path evidence") or [""])[0]
    if origin is not None and origin not in ORIGINS:
        results.append(("FAIL", "Plan path origin is invalid"))
    elif origin == "backlog-requirement" and ".backlog" not in evidence:
        results.append(("FAIL", "backlog path origin requires .backlog evidence"))
    elif origin == "generated-project-root" and ".plans" not in evidence:
        results.append(("FAIL", "generated path origin requires .plans evidence"))
    elif origin == "host-plan-mode" and "plans" not in evidence.lower():
        results.append(("FAIL", "host-plan-mode origin must name the host draft it was promoted from"))
    decisions = {}
    for label in ("Unit tests", "Code review"):
        value = (data.get(label) or [None])[0]
        if value not in DECISIONS:
            results.append(("FAIL", f"{label} must be selected or skipped"))
        if f"{label} source" in data:
            source = one(data, f"{label} source", results)
            if source not in SOURCES:
                results.append(("FAIL", f"{label} source is invalid"))
        decisions[label] = value
    return decisions["Unit tests"], decisions["Code review"]


def task_contract(text, unit, results):
    tasks = list(TASK_RE.finditer(section(text, "Tasks")))
    if not tasks:
        results.append(("FAIL", "missing Task section"))
        return False
    has_tdd = False
    for task in tasks:
        number = task.group("id")
        data = fields(task.group())
        label = f"Task {number}"
        for key in TASK_FIELDS:
            one(data, key, results, label)
        if (data.get("Status") or [None])[0] not in STATUSES:
            results.append(("FAIL", f"{label} Status is invalid"))
        mode = (data.get("Mode") or [None])[0]
        if mode is not None and mode not in MODES:
            results.append(("FAIL", f"{label} Mode is invalid"))
        depth = (data.get("Depth") or ["simplify"])[0]
        if depth not in ("simplify", "TDD"):
            results.append(("FAIL", f"{label} Depth is invalid"))
        if depth == "TDD":
            has_tdd = True
            if unit != "selected":
                results.append(("FAIL", f"{label} Depth TDD requires Unit tests: selected"))
            if not ((data.get("TDD reason") or [""])[0] or (data.get("Risk reason") or [""])[0]):
                results.append(("FAIL", f"{label} Depth TDD requires a non-empty TDD reason"))
    structure_contract(text, tasks, results)
    return has_tdd


def tdd_task_numbers(text):
    return [task.group("id") for task in TASK_RE.finditer(section(text, "Tasks"))
            if (fields(task.group()).get("Depth") or ["simplify"])[0] == "TDD"]


def structure_contract(text, tasks, results):
    """Check declared task relationships, without interpreting implementation prose."""
    ids = [task.group("id") for task in tasks]
    for tid in set(ids):
        if ids.count(tid) > 1:
            results.append(("FAIL", f"duplicate Task {tid}"))
    declared_acs = set(re.findall(r"\bAC-\d+\b", section(text, "Acceptance Criteria")))
    dependencies, files = {}, {}
    for task in tasks:
        tid, data = task.group("id"), fields(task.group())
        dependency_text = (data.get("Depends on") or [""])[0]
        dependencies[tid] = set(re.findall(r"\bTask\s+(\d+)\b", dependency_text, re.I))
        if dependency_text.lower() not in ("none", "n/a", "-") and not dependencies[tid]:
            results.append(("FAIL", f"Task {tid} Depends on must name Task IDs or none"))
        for dependency in dependencies[tid]:
            if dependency not in ids:
                results.append(("FAIL", f"Task {tid} depends on unknown Task {dependency}"))
            if dependency == tid:
                results.append(("FAIL", f"Task {tid} depends on itself"))
        file_text = (data.get("Files") or [""])[0]
        paths = re.findall(r"`([^`]+)`", file_text)
        if not paths:
            paths = [item.strip() for item in re.split(r"[,;]", file_text)]
        files[tid] = {path.replace("\\", "/").casefold() for path in paths if path}
        ac_refs = re.findall(r"\bAC-\d+\b", (data.get("ACs") or [""])[0])
        if not ac_refs:
            results.append(("FAIL", f"Task {tid} ACs must reference at least one AC-N"))
        for ac in ac_refs:
            if ac not in declared_acs:
                results.append(("FAIL", f"Task {tid} references undefined {ac}"))

    def reaches(start, target, visited=None):
        visited = set() if visited is None else visited
        if start in visited:
            return False
        visited.add(start)
        return any(dep == target or reaches(dep, target, visited)
                   for dep in dependencies.get(start, ()))

    if any(reaches(tid, tid) for tid in ids):
        results.append(("FAIL", "task dependencies contain a cycle"))
    unique_ids = list(dict.fromkeys(ids))
    for index, first in enumerate(unique_ids):
        for second in unique_ids[index + 1:]:
            shared = files[first] & files[second]
            if shared and not (reaches(first, second) or reaches(second, first)):
                results.append(("FAIL", f"Task {first} and Task {second} overlap Files without dependency ordering: "
                                + ", ".join(sorted(shared))))


def preflight_contract(text, results):
    preflight = section(text, "Preflight")
    if not preflight.strip():
        if re.search(r"^## Preflight\s*$", text, re.MULTILINE):
            results.append(("FAIL", "provided Preflight section is empty"))
        if re.search(r"\bverified-ready\b", text):
            results.append(("FAIL", "verified-ready requires recorded Preflight results"))
        return None
    task_names = {match.group(1) for match in re.finditer(r"^### (Task \d+):", text, re.MULTILINE)}
    declared = []
    for cells in rows(preflight):
        if len(cells) != 5:
            results.append(("FAIL", f"Preflight row needs 5 columns, got {len(cells)}"))
            continue
        pid, kind, _target, expect, blocks = cells
        declared.append(pid)
        if kind not in PROBE_KINDS:
            results.append(("FAIL", f"{pid} uses an unknown probe kind: {kind}"))
        if not expect:
            results.append(("FAIL", f"{pid} must state what it expects"))
        for named in re.findall(r"Task \d+", blocks):
            if named not in task_names:
                results.append(("FAIL", f"{pid} blocks {named}, which does not exist"))
        if not blocks:
            results.append(("FAIL", f"{pid} must name what it blocks"))
    if not re.search(r"^Run:\s*\S+", preflight, re.MULTILINE):
        results.append(("FAIL", "Preflight results need a Run: line naming the probe run"))
    observed = list(RESULT_RE.finditer(preflight))
    if not observed:
        results.append(("FAIL", "provided Preflight has no recorded probe results"))
    for line in preflight.splitlines():
        if re.match(r"^-\s*(?:PF-\S+|derived path\b)", line) and not RESULT_RE.match(line):
            results.append(("FAIL", f"malformed Preflight result: {line}"))
    reported = {match.group("pid").strip() for match in observed}
    for pid in declared:
        if pid not in reported:
            results.append(("FAIL", f"{pid} has no recorded preflight result"))
    try:
        expected_derived = derived_file_probes(text)
    except (OSError, ImportError, AttributeError) as error:
        results.append(("FAIL", f"cannot verify derived file probes: {error}"))
        expected_derived = []
    for pid in expected_derived:
        if pid not in reported:
            results.append(("FAIL", f"missing recorded result for {pid}"))
    for match in observed:
        if match.group("state") == "unverifiable" and "fallback:" not in match.group("detail").lower():
            results.append(("FAIL", f"{match.group('pid').strip()} is unverifiable without a Fallback"))
    states = {match.group("state") for match in observed}
    declared_autonomy = one(fields(preflight), "Autonomy", results, "Preflight")
    if declared_autonomy is not None and declared_autonomy not in AUTONOMY_STATES:
        results.append(("FAIL", "Autonomy is invalid"))
        return None
    computed = ("verified-blocked" if "blocked" in states
                else "unverifiable-with-fallback" if "unverifiable" in states else "verified-ready")
    if declared_autonomy is not None and declared_autonomy != computed:
        results.append(("FAIL", f"Autonomy says {declared_autonomy} but recorded results aggregate to {computed}"))
    return declared_autonomy


def assignment_agents_for_task(assignment, number):
    """Return Agent-column values for exact Task rows, never prose in evidence cells."""
    lines = assignment.splitlines()
    header = next((line for line in lines if "|" in line and re.search(r"\bAgent\b", line, re.I)), None)
    if not header:
        return []
    columns = [cell.strip().lower() for cell in header.strip().strip("|").split("|")]
    try:
        task_index, agent_index = columns.index("task(s)"), columns.index("agent")
    except ValueError:
        return []
    values = []
    for line in lines:
        if "|" not in line or re.fullmatch(r"\s*\|?\s*[-:| ]+\s*\|?\s*", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) <= max(task_index, agent_index):
            continue
        if str(number) in re.findall(r"\bTask\s*(\d+)\b", cells[task_index], re.I):
            values.append(cells[agent_index].lower())
    return values


def evaluate(text, plan_path=None):
    results = []
    context = section(text, "Context")
    if not context:
        return [("FAIL", "missing ## Context section")]
    unit, review = context_contract(normalize(fields(context), plan_path), results)
    assignment, verification = section(text, "Agent Assignment"), section(text, "Verification")
    task_contract(text, unit, results)
    autonomy = preflight_contract(text, results)
    for number in tdd_task_numbers(text):
        task_agents = assignment_agents_for_task(assignment, number)
        if not any("code-implementer" in agent or
                   (re.search(r"\b(?:worker|default)\b", agent) and "implementation" in agent) or
                   ("main" in agent and "tiny" in agent) for agent in task_agents):
            results.append(("FAIL", f"TDD Task {number} requires implementation-role assignment"))
        if any("qa-engineer" in agent for agent in task_agents):
            results.append(("FAIL", f"TDD Task {number} must not assign qa-engineer; unit/component tests belong to code-implementer"))
    verification_data = fields(verification)
    for label in ("Build", "Existing tests"):
        evidence = one(verification_data, label, results, "Verification")
        if evidence and re.fullmatch(r"(?:N/A|not applicable|skipped)\s*[.!]?", evidence, re.I):
            results.append(("FAIL", f"Verification {label} N/A requires a reason"))
    review_evidence = " ".join(verification_data.get("Code review", []))
    scoped_review = (re.search(r"\bcode-review-(?:lite|pro)\b", review_evidence) or
                     (re.search(r"\bcode-reviewer\b", review_evidence, re.I) and
                      re.search(r"\bscope\b|\bscoped\b", review_evidence, re.I)) or
                     (re.search(r"\breviewer\s*:\s*\S+", review_evidence, re.I) and
                      re.search(r"\bscope\b|\bscoped\b", review_evidence, re.I)))
    if review == "selected" and not scoped_review:
        results.append(("FAIL", "selected code review requires a named scoped reviewer or code-review-lite/pro"))
    if review == "skipped" and scoped_review:
        results.append(("FAIL", "skipped code review must not invoke a reviewer"))
    if not any(level == "FAIL" for level, _ in results):
        results.extend((("PASS", "structured plan is consistent"), ("PASS", "task and verification flows match")))
        if autonomy is not None:
            results.append(("PASS", "preflight results recorded and consistent"))
    if autonomy == "verified-blocked":
        results.append(("BLOCK", "recorded Preflight has blocked probes; resolve them and re-run Preflight"))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify implement-plan plan output.")
    parser.add_argument("plan_path")
    path = Path(parser.parse_args(argv).plan_path)
    if not path.is_file():
        print(f"FAIL  plan file not found: {path}")
        return 1
    results = evaluate(path.read_text(encoding="utf-8", errors="replace"), path)
    fails = sum(level == "FAIL" for level, _ in results)
    blocks = sum(level == "BLOCK" for level, _ in results)
    print(f"=== OUTPUT CHECK: implement-plan ({path}) ===")
    print("\n".join(f"{level:<5}  {message}" for level, message in results))
    print(f"\nResult: {fails} FAIL, {blocks} BLOCK, {len(results) - fails - blocks} PASS")
    if fails:
        return 1
    return 3 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
