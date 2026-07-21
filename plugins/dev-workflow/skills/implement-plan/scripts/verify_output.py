#!/usr/bin/env python3
"""Deterministic implement-plan contract verifier with old-modern and legacy input compatibility."""

import argparse
import re
import sys
from pathlib import Path


FIELD_RE = re.compile(r"^-?\s*(?P<key>[A-Za-z -]+):\s*(?P<value>.*?)\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^### Task \d+:.*?(?=^### Task |^## |\Z)", re.MULTILINE | re.DOTALL)
NEW_FIELDS = (
    "Plan path origin", "Plan path evidence", "TDD recommendation", "TDD recommendation reason",
    "TDD decision", "Unit tests", "Unit tests source", "Unit tests reason",
    "Code review recommendation", "Code review recommendation reason", "Code review decision",
    "Code review", "Code review source", "Code review reason", "Depth",
)
NEW_DETECT_FIELDS = ("Plan path origin", "Plan path evidence", "TDD recommendation", "TDD recommendation reason",
                     "TDD decision", "Code review recommendation", "Code review recommendation reason", "Code review decision")
PLACEHOLDERS = ((re.compile(r"\bTBD\b", re.I), "TBD"), (re.compile(r"\bTO" r"DO\b", re.I), "task-decision marker"),
                (re.compile(r"\bundecided\b", re.I), "undecided marker"), (re.compile(r"\{[^{}]+\}"), "template braces"),
                (re.compile(r"\bappropriate(?:ly)?\b", re.I), "vague 'appropriate'"),
                (re.compile(r"\bsimilar to Task\b", re.I), "cross-task shorthand"))


def fields(text):
    output = {}
    for match in FIELD_RE.finditer(text):
        output.setdefault(match["key"].strip(), []).append(match["value"].strip())
    return output


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE)
    return match.group(1) if match else ""


def one(data, key, results, label="Context"):
    values = data.get(key, [])
    if len(values) != 1:
        results.append(("FAIL", f"{label} field must occur once: {key}" if values else f"missing {label} field: {key}"))
        return None
    if not values[0]: results.append(("FAIL", f"{label} field must be non-empty: {key}"))
    return values[0]


def decision(data, label, results, modern):
    value = one(data, label, results)
    if value in {"selected", "skipped"}:
        source, reason = one(data, f"{label} source", results), one(data, f"{label} reason", results)
        allowed = {"user"} if modern and value == "selected" else {"user", "auto-assessment"}
        if source not in allowed: results.append(("FAIL", f"{label} source is invalid for {value}"))
        return value
    if not modern and value in {"requested", "not requested"}:
        return "selected" if value == "requested" else "skipped"
    results.append(("FAIL", f"{label} must be selected/skipped" + ("" if modern else " or requested/not requested")))
    return None


def context_contract(data, results):
    modern = any(key in data for key in NEW_DETECT_FIELDS)
    if modern:
        for key in NEW_FIELDS: one(data, key, results)
        origin, evidence = data.get("Plan path origin", [None])[0], data.get("Plan path evidence", [""])[0]
        if origin not in {"existing-input", "backlog-requirement", "generated-project-root"}:
            results.append(("FAIL", "Plan path origin is invalid"))
        elif origin == "backlog-requirement" and ".backlog" not in evidence:
            results.append(("FAIL", "backlog path origin requires .backlog evidence"))
        elif origin == "generated-project-root" and ".plans" not in evidence:
            results.append(("FAIL", "generated path origin requires .plans evidence"))
        for label in ("TDD", "Code review"):
            if data.get(f"{label} recommendation", [None])[0] not in {"recommended", "not-recommended"}:
                results.append(("FAIL", f"{label} recommendation must be recommended or not-recommended"))
            if data.get(f"{label} decision", [None])[0] not in {"selected", "skipped"}:
                results.append(("FAIL", f"{label} decision is invalid"))
    unit, review = decision(data, "Unit tests", results, modern), decision(data, "Code review", results, modern)
    if modern and data.get("TDD decision", [None])[0] != unit: results.append(("FAIL", "TDD decision must equal Unit tests"))
    if modern and data.get("Code review decision", [None])[0] != review: results.append(("FAIL", "Code review decision must equal Code review"))
    depth = one(data, "Depth", results)
    expected = {"selected": "TDD", "skipped": "simplify"}.get(unit)
    if expected and depth != expected: results.append(("FAIL", f"Depth must be {expected} when Unit tests is {unit}"))
    return modern, unit, review


def new_task_contract(text, unit, results):
    tasks = TASK_RE.findall(section(text, "Tasks"))
    if not tasks: results.append(("FAIL", "missing Task section")); return False
    has_tdd = False
    required = ("Status", "Depends on", "Files", "Risk", "Risk reason", "Depth", "Mode", "Existing-method baseline", "Scaffold", "Description", "Done when", "ACs")
    for number, task in enumerate(tasks, 1):
        data = fields(task)
        for key in required: one(data, key, results, f"Task {number}")
        risk, depth, mode = data.get("Risk", [None])[0], data.get("Depth", [None])[0], data.get("Mode", [None])[0]
        if risk not in {"routine", "risky"}: results.append(("FAIL", f"Task {number} Risk is invalid"))
        if depth not in {"simplify", "TDD"}: results.append(("FAIL", f"Task {number} Depth is invalid"))
        if mode not in {"existing-method", "simple-new", "complex-backbone"}: results.append(("FAIL", f"Task {number} Mode is invalid"))
        if depth == "TDD":
            has_tdd = True
            if risk != "risky" or unit != "selected": results.append(("FAIL", f"Task {number} TDD requires risky selected decision"))
        if depth == "TDD" and mode == "existing-method" and data.get("Existing-method baseline", [""])[0] in {"", "not applicable"}:
            results.append(("FAIL", f"Task {number} existing-method TDD requires baseline"))
        if depth == "TDD" and mode == "simple-new" and data.get("Scaffold", [""])[0] in {"", "not applicable"}:
            results.append(("FAIL", f"Task {number} simple-new TDD requires Scaffold"))
        if depth == "simplify" and mode == "simple-new" and data.get("Scaffold", [""])[0] != "not applicable":
            results.append(("FAIL", f"Task {number} simplify simple-new Scaffold must be not applicable"))
        if mode == "complex-backbone" and any(word not in task.lower() for word in ("design-backbone", "approval", "handoff", "resume", "duplicate tests")):
            results.append(("FAIL", f"Task {number} complex-backbone semantics are incomplete"))
    return has_tdd


def evaluate(text):
    context, results = section(text, "Context"), []
    if not context: return [("FAIL", "missing ## Context section")]
    modern, unit, review = context_contract(fields(context), results)
    assignment, verification = section(text, "Agent Assignment"), section(text, "Verification")
    has_tdd = new_task_contract(text, unit, results) if modern else unit == "selected"
    if has_tdd and "qa-engineer" not in assignment.lower(): results.append(("FAIL", "TDD requires qa-engineer assignment"))
    if not verification.strip() or not re.search(r"\bbuild\b", verification, re.I) or not re.search(r"\btest(?:s| suite)?\b", verification, re.I):
        results.append(("FAIL", "Verification requires build and existing tests"))
    if review == "selected" and "code-review-lite" not in verification.lower(): results.append(("FAIL", "selected code review requires code-review-lite"))
    if modern and review == "selected" and "escalation policy: ask" not in verification.lower(): results.append(("FAIL", "new selected review requires Escalation Policy: ask"))
    if review == "skipped" and "code-review-lite" in verification.lower(): results.append(("FAIL", "skipped code review must not invoke code-review-lite"))
    if modern and "code-implementer" in assignment.lower():
        safety = ("task-listed", "delete or move", "reset", "restore", "checkout", "stash", "stage", "commit", "push", "publish", "install", "working-tree-aware", "scoped diff")
        if any(term not in text.lower() for term in safety): results.append(("FAIL", "delegation safety/working-tree-aware contract is incomplete"))
    for pattern, name in PLACEHOLDERS:
        if pattern.search(text): results.append(("FAIL", f"placeholder/vague text detected: {name}"))
    if not results: results.extend((("PASS", "plan contract valid"), ("PASS", "quality, task, and verification flows match"), ("PASS", "no placeholders detected")))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify implement-plan plan output."); parser.add_argument("plan_path")
    path = Path(parser.parse_args(argv).plan_path)
    if not path.is_file(): print(f"FAIL  plan file not found: {path}"); return 1
    results = evaluate(path.read_text(encoding="utf-8", errors="replace")); fails = sum(level == "FAIL" for level, _ in results)
    print(f"=== OUTPUT CHECK: implement-plan ({path}) ==="); print("\n".join(f"{level:<4}  {message}" for level, message in results)); print(f"\nResult: {fails} FAIL, {len(results) - fails} PASS")
    return int(bool(fails))


if __name__ == "__main__": sys.exit(main())
