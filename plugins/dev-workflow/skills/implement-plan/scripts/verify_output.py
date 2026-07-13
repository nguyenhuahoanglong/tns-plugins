#!/usr/bin/env python3
"""Deterministic contract check for implement-plan plan files.

Accepts modern selected/skipped Context fields and complete legacy requested/not requested flags.
Exit 0 when no FAIL; exit 1 otherwise.
"""

import argparse
import re
import sys
from pathlib import Path


FIELD_RE = re.compile(r"^(?P<key>[A-Za-z ]+):\s*(?P<value>.*?)\s*$", re.MULTILINE)
PLACEHOLDERS = (
    (re.compile(r"\bTBD\b", re.IGNORECASE), "TBD"),
    (re.compile(r"\bTO" r"DO\b", re.IGNORECASE), "task-decision marker"),
    (re.compile(r"\bundecided\b", re.IGNORECASE), "undecided marker"),
    (re.compile(r"\{[^{}]+\}"), "template braces"),
    (re.compile(r"\bappropriate(?:ly)?\b", re.IGNORECASE), "vague 'appropriate'"),
    (re.compile(r"\bsimilar to Task\b", re.IGNORECASE), "cross-task shorthand"),
)


def _fields(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for match in FIELD_RE.finditer(text):
        values.setdefault(match.group("key").strip(), []).append(match.group("value").strip())
    return values


def _one(fields, key, results, required=True):
    values = fields.get(key, [])
    if not values:
        if required:
            results.append(("FAIL", f"missing Context field: {key}"))
        return None
    if len(values) != 1:
        results.append(("FAIL", f"field must occur once: {key}"))
        return None
    return values[0]


def _decision(fields, label, results):
    value = _one(fields, label, results)
    if value in ("selected", "skipped"):
        source = _one(fields, f"{label} source", results)
        reason = _one(fields, f"{label} reason", results)
        if source not in ("user", "auto-assessment"):
            results.append(("FAIL", f"{label} source must be user or auto-assessment"))
        if reason is not None and not reason.strip():
            results.append(("FAIL", f"{label} reason must be non-empty"))
        return value, "modern"
    if value in ("requested", "not requested"):
        return ("selected" if value == "requested" else "skipped"), "legacy"
    if value is not None:
        results.append(("FAIL", f"{label} must be selected/skipped (or legacy requested/not requested)"))
    return None, None


def evaluate(text: str):
    results = []
    context_match = re.search(r"^## Context\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE)
    if not context_match:
        return [("FAIL", "missing ## Context section")]
    fields = _fields(context_match.group(1))
    unit, unit_shape = _decision(fields, "Unit tests", results)
    review, review_shape = _decision(fields, "Code review", results)
    depth = _one(fields, "Depth", results)

    expected_depth = {"selected": "TDD", "skipped": "simplify"}.get(unit)
    if expected_depth and depth != expected_depth:
        results.append(("FAIL", f"Depth must be {expected_depth} when Unit tests is {unit}"))

    assignment_match = re.search(
        r"^## Agent Assignment\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE
    )
    assignment = assignment_match.group(1) if assignment_match else ""
    assignment_lower = assignment.lower()
    if unit == "selected":
        if not assignment_match:
            results.append(("FAIL", "selected unit tests require ## Agent Assignment section"))
        if "qa-engineer" not in assignment_lower:
            results.append(("FAIL", "selected unit tests require qa-engineer assignment"))
        if "scaffold" not in assignment_lower:
            results.append(("FAIL", "selected unit tests require scaffold evidence in Agent Assignment"))
    elif unit == "skipped":
        if "qa-engineer" in assignment_lower:
            results.append(("FAIL", "skipped unit tests must not assign qa-engineer"))
        if re.search(r"new unit tests\s*:", text, re.IGNORECASE):
            results.append(("FAIL", "skipped unit tests must not add new-test verification"))

    verification_match = re.search(r"^## Verification\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE)
    verification = verification_match.group(1) if verification_match else ""
    verification_lower = verification.lower()
    if not verification.strip():
        results.append(("FAIL", "missing non-empty Verification section"))
    else:
        if not re.search(r"\bbuild\b", verification, re.IGNORECASE):
            results.append(("FAIL", "Verification must include project build"))
        if not re.search(r"\btest(?:s| suite)?\b", verification, re.IGNORECASE):
            results.append(("FAIL", "Verification must include existing test suite"))
    if review == "selected" and "code-review-lite" not in verification_lower:
        results.append(("FAIL", "selected code review requires code-review-lite in Verification"))
    elif review == "skipped" and "code-review-lite" in verification_lower:
        results.append(("FAIL", "skipped code review must not invoke code-review-lite in Verification"))

    for pattern, name in PLACEHOLDERS:
        if pattern.search(text):
            results.append(("FAIL", f"placeholder/vague text detected: {name}"))

    if not results:
        shape = "legacy" if unit_shape == review_shape == "legacy" else "modern"
        results.append(("PASS", f"quality decision contract valid ({shape})"))
        results.append(("PASS", "TDD/QA and review flows match decisions"))
        results.append(("PASS", "no placeholders detected"))
    return results


def report(path, results):
    lines = [f"=== OUTPUT CHECK: implement-plan ({path}) ==="]
    lines.extend(f"{level:<4}  {message}" for level, message in results)
    fails = sum(level == "FAIL" for level, _ in results)
    lines.append("")
    lines.append(f"Result: {fails} FAIL, {len(results) - fails} PASS")
    return "\n".join(lines), fails


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify implement-plan plan output.")
    parser.add_argument("plan_path", help="Path to generated or existing plan markdown")
    args = parser.parse_args(argv)
    path = Path(args.plan_path)
    if not path.is_file():
        print(f"FAIL  plan file not found: {path}")
        return 1
    results = evaluate(path.read_text(encoding="utf-8", errors="replace"))
    output, fails = report(path, results)
    print(output)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
