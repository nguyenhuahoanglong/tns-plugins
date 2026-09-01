#!/usr/bin/env python3
"""Deterministic implement-plan contract verifier.

Static and hermetic: it reads the plan text only. Contract violations are FAIL (exit 1); a recorded but
unapprovable autonomy state is BLOCK (exit 3). Legacy and pre-v4 plans are normalized on read.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FIELD_RE = re.compile(r"^-?\s*(?P<key>[A-Za-z][A-Za-z -]*):\s*(?P<value>.*?)\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^### Task \d+:.*?(?=^### Task |^## |\Z)", re.MULTILINE | re.DOTALL)
TABLE_RE = re.compile(r"^\|(?P<cells>.+)\|\s*$", re.MULTILINE)
RESULT_RE = re.compile(r"^-\s*(?P<pid>.+?)\s+(?P<state>ready|blocked|unverifiable)\s*:\s*(?P<detail>.*)$",
                       re.MULTILINE)

CONTEXT_FIELDS = ("Plan path", "Plan path origin", "Plan path evidence", "Unit tests", "Unit tests source",
                  "Unit tests reason", "Code review", "Code review source", "Code review reason")
ORIGINS = ("host-plan-mode", "existing-input", "backlog-requirement", "generated-project-root")
SOURCES = ("user", "flag")
DECISIONS = ("selected", "skipped")
TASK_FIELDS = ("Status", "Depends on", "Files", "Mode", "Description", "Done when", "ACs")
STATUSES = ("pending", "scaffolded", "in-progress", "complete", "blocked")
MODES = ("existing-method", "simple-new", "complex-backbone")
AUTONOMY_STATES = ("verified-ready", "unverifiable-with-fallback", "verified-blocked")
PROBE_KINDS = ("path", "command", "command-version", "auth", "env", "url", "node-deps", "dotnet-restore",
               "manual")
SAFETY_TERMS = tuple(re.compile(pattern, re.I) for pattern in (
    r"task-listed", r"delete\w*\s+(?:or|and|,)?\s*move", r"reset", r"restore", r"checkout", r"stash",
    r"stage", r"commit", r"push", r"publish", r"install", r"working-tree-aware", r"scoped diff"))
PLACEHOLDERS = ((re.compile(r"\bTBD\b", re.I), "TBD"),
                (re.compile(r"\bTO" r"DO\b", re.I), "task-decision marker"),
                (re.compile(r"\bundecided\b", re.I), "undecided marker"),
                (re.compile(r"\{[^{}]+\}"), "template braces"),
                (re.compile(r"\bappropriate(?:ly)?\b", re.I), "vague 'appropriate'"),
                (re.compile(r"\bsimilar to Task\b", re.I), "cross-task shorthand"))
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
    """Map legacy and pre-v4 Context shapes onto the v4 field names, once, up front."""
    normalized = {key: list(values) for key, values in data.items()}
    for label in ("Unit tests", "Code review"):
        value = (normalized.get(label) or [""])[0]
        if value in LEGACY_DECISIONS:
            normalized[label] = [LEGACY_DECISIONS[value]]
            normalized.setdefault(f"{label} source", ["user"])
            normalized.setdefault(f"{label} reason", [f"legacy explicit choice: {value}"])
        source = (normalized.get(f"{label} source") or [""])[0]
        if source == "auto-assessment":
            normalized[f"{label} source"] = ["user"]
        for dropped in (f"{label} decision", f"{label} recommendation", f"{label} recommendation reason",
                        "TDD decision", "TDD recommendation", "TDD recommendation reason", "Depth"):
            normalized.pop(dropped, None)
    if "Plan path origin" not in normalized:
        normalized["Plan path origin"] = ["existing-input"]
        normalized.setdefault("Plan path evidence", [f"existing plan supplied as input: {plan_path}"])
    if "Plan path" not in normalized:
        normalized["Plan path"] = [str(plan_path)] if plan_path else list(normalized["Plan path evidence"])
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
    if origin not in ORIGINS:
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
        if (data.get(f"{label} source") or [None])[0] not in SOURCES:
            results.append(("FAIL", f"{label} source must be user or flag"))
        decisions[label] = value
    return decisions["Unit tests"], decisions["Code review"]


def task_contract(text, unit, results):
    tasks = TASK_RE.findall(section(text, "Tasks"))
    if not tasks:
        results.append(("FAIL", "missing Task section"))
        return False
    has_tdd = False
    for number, task in enumerate(tasks, 1):
        data = fields(task)
        label = f"Task {number}"
        for key in TASK_FIELDS:
            one(data, key, results, label)
        if (data.get("Status") or [None])[0] not in STATUSES:
            results.append(("FAIL", f"{label} Status is invalid"))
        mode = (data.get("Mode") or [None])[0]
        if mode not in MODES:
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
            if mode == "existing-method" and not (data.get("Existing-method baseline") or [""])[0]:
                results.append(("FAIL", f"{label} existing-method TDD requires Existing-method baseline"))
            if mode == "simple-new" and not (data.get("Scaffold") or [""])[0]:
                results.append(("FAIL", f"{label} simple-new TDD requires Scaffold"))
        if mode == "complex-backbone" and any(word not in text.lower() for word in
                                              ("design-backbone", "handoff", "resume", "duplicate tests")):
            results.append(("FAIL", f"{label} complex-backbone semantics are incomplete"))
    return has_tdd


def preflight_contract(text, results):
    preflight = section(text, "Preflight")
    if not preflight.strip():
        results.append(("FAIL", "missing ## Preflight section"))
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


def evaluate(text, plan_path=None):
    results = []
    context = section(text, "Context")
    if not context:
        return [("FAIL", "missing ## Context section")]
    unit, review = context_contract(normalize(fields(context), plan_path), results)
    assignment, verification = section(text, "Agent Assignment"), section(text, "Verification")
    has_tdd = task_contract(text, unit, results)
    autonomy = preflight_contract(text, results)
    if has_tdd and "qa-engineer" not in assignment.lower():
        results.append(("FAIL", "TDD requires qa-engineer assignment"))
    if (not verification.strip() or not re.search(r"\bbuild\b", verification, re.I)
            or not re.search(r"\btest(?:s| suite)?\b", verification, re.I)):
        results.append(("FAIL", "Verification requires build and existing tests"))
    if review == "selected" and "code-review-lite" not in verification.lower():
        results.append(("FAIL", "selected code review requires code-review-lite"))
    if review == "selected" and "escalation policy: ask" not in verification.lower():
        results.append(("FAIL", "selected review requires Escalation Policy: ask"))
    if review == "skipped" and "code-review-lite" in verification.lower():
        results.append(("FAIL", "skipped code review must not invoke code-review-lite"))
    if "code-implementer" in assignment.lower() and any(not term.search(text) for term in SAFETY_TERMS):
        results.append(("FAIL", "delegation safety/working-tree-aware contract is incomplete"))
    for pattern, name in PLACEHOLDERS:
        if pattern.search(text):
            results.append(("FAIL", f"placeholder/vague text detected: {name}"))
    if not any(level == "FAIL" for level, _ in results):
        results.extend((("PASS", "plan contract valid"), ("PASS", "task and verification flows match"),
                        ("PASS", "preflight results recorded and consistent"),
                        ("PASS", "no placeholders detected")))
    if autonomy == "verified-blocked":
        results.append(("BLOCK", "Autonomy is verified-blocked: valid plan, but it cannot be approved until "
                                 "every blocked probe is resolved and preflight is re-run"))
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
