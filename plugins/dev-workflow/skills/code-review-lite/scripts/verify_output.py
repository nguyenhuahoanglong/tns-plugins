#!/usr/bin/env python3
"""Verify deterministic code-review-lite report requirements."""

import argparse
import re
import sys
from pathlib import Path

SKILL = "code-review-lite v2.1.1"
PROFILES = {"Docs Tiny", "Code Tiny", "Lite"}
BRANCH_GATE_FIELDS = {
    "Status", "Branch", "Prefix", "Work Item ID", "Expected Type",
    "Actual Type", "Title", "State", "Source", "Reason",
}


def field(text, name):
    match = re.search(
        rf"^\*\*{re.escape(name)}\*\*:\s*(.+?)\s*$",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def add(results, condition, message):
    results.append(("PASS" if condition else "FAIL", message))


def bullet(text, name):
    match = re.search(
        rf"^- \*\*{re.escape(name)}\*\*:\s*(.+?)\s*$",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def section_bullets(text, heading):
    match = re.search(
        rf"^{re.escape(heading)}\s*(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return {}
    return {
        name: value.strip()
        for name, value in re.findall(
            r"^- \*\*([^*]+)\*\*:\s*(.+?)\s*$",
            match.group(1),
            re.MULTILINE,
        )
    }


def build_repo_count(text):
    section = re.search(
        r"^## Build Status\s*(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not section:
        return 0
    return len(
        re.findall(
            r"^\|\s*`[^`]+`\s*\|\s*(?:PASS|FAIL|PASS WITH WARNINGS|NOT RUN|JS-SKIPPED)\s*\|",
            section.group(1),
            re.MULTILINE,
        )
    )


def evaluate(output_path, expected_profile=None, expected_main_runtime=None):
    path = Path(output_path)
    results = []
    add(results, path.is_file(), f"report exists: {path}")
    add(results, path.name.endswith(".lite.md"), "report uses .lite.md suffix")
    if not path.is_file():
        return results

    text = path.read_text(encoding="utf-8", errors="replace")
    values = {
        name: field(text, name)
        for name in (
            "Skill",
            "Review Profile",
            "Main Runtime",
            "Agents Triggered",
            "Agents Skipped",
        )
    }

    add(results, values["Skill"] == SKILL, f"Skill is exactly {SKILL}")
    profile = values["Review Profile"]
    add(results, profile in PROFILES, "Profile is Docs Tiny, Code Tiny, or Lite")
    if expected_profile:
        add(results, profile == expected_profile, f"Profile matches {expected_profile}")
    main_runtime = values["Main Runtime"] or ""
    add(
        results,
        bool(
            re.fullmatch(
                r".+ / .+",
                main_runtime,
            )
        ),
        "Main Runtime reports exact model/effort visibility and main agent",
    )
    if expected_main_runtime:
        add(
            results,
            main_runtime == expected_main_runtime,
            f"Main Runtime matches expected launch runtime: {expected_main_runtime}",
        )
    add(results, bool(values["Agents Triggered"]), "Agents Triggered are reported")
    add(results, bool(values["Agents Skipped"]), "Agents Skipped are reported")
    add(results, "## Classification" in text, "Classification section exists")
    add(results, "## Branch Work Item Gate" in text,
        "Branch Work Item Gate section exists")
    add(results, "## Requirement Evidence" in text, "Requirement Evidence section exists")

    triggered = values["Agents Triggered"] or ""
    skipped = values["Agents Skipped"] or ""
    build_matches = re.findall(
        r"Build Validator\[[^\]]+\]\(.+ / .+;\s*[^)]+\)",
        triggered,
    )
    build_runtime_match = re.search(
        r"Build Validator\[[^\]]+\]\(([^;()]+ / [^;()]+);\s*[^)]+\)",
        triggered,
    )
    build_runtime = build_runtime_match.group(1) if build_runtime_match else None
    repo_count = build_repo_count(text)
    requirement_runtime = "Requirement Validator("
    specialists = ("Security Reviewer(", "Performance Reviewer(", "Philosophy Reviewer(", "Standard Reviewer(")
    files_text = bullet(text, "Files Changed")
    lines_text = bullet(text, "Changed Lines")
    docs_text = bullet(text, "Documentation Only")
    risks_text = bullet(text, "Risk Triggers")
    specialist_text = bullet(text, "Specialist Triggers")
    files = int(files_text) if files_text and files_text.isdigit() else None
    lines = int(lines_text) if lines_text and lines_text.isdigit() else None
    docs_only = docs_text == "true" if docs_text in {"true", "false"} else None
    risks = [] if risks_text == "None" else [
        item.strip() for item in (risks_text or "").split(" | ") if item.strip()
    ]
    expected_specialists = []
    if specialist_text and specialist_text != "None":
        expected_specialists = [
            item.split("=", 1)[0]
            for item in specialist_text.split(" | ")
            if "=" in item
        ]
    gate = section_bullets(text, "## Branch Work Item Gate")
    add(results, BRANCH_GATE_FIELDS <= set(gate),
        "Branch Work Item Gate reports required fields")
    gate_status = gate.get("Status")
    add(results, gate_status in {"PASS", "FAIL", "SKIPPED"},
        "Branch Work Item Gate status is valid")
    branch_trigger_pattern = r"Branch Work Item Gate\(([^;()]+ / [^;()]+);\s*branch work item convention\)"
    branch_runtime_match = re.search(branch_trigger_pattern, triggered)
    branch_triggered = bool(re.search(branch_trigger_pattern, triggered))
    branch_skipped = "Branch Work Item Gate(" in skipped
    if gate_status in {"PASS", "FAIL"}:
        add(results, branch_triggered,
            "Branch Work Item Gate uses Build Validator runtime when triggered")
        if build_runtime:
            add(results, branch_runtime_match and branch_runtime_match.group(1) == build_runtime,
                "Branch Work Item Gate uses same runtime as Build Validator")
        add(results, not branch_skipped,
            "Triggered Branch Work Item Gate is not also skipped")
    elif gate_status == "SKIPPED":
        add(results, branch_skipped and not branch_triggered,
            "Skipped Branch Work Item Gate is recorded only in skipped actors")
    add(results, files is not None, "Classification reports Files Changed")
    add(results, lines is not None, "Classification reports Changed Lines")
    add(results, docs_only is not None, "Classification reports Documentation Only")
    add(results, risks_text is not None, "Classification reports Risk Triggers")
    add(results, specialist_text is not None, "Classification reports Specialist Triggers")

    if profile == "Docs Tiny":
        add(results, docs_only is True, "Docs Tiny requires documentation-only scope")
        add(results, triggered == "None" or branch_triggered,
            "Docs Tiny triggers no child agents except optional branch gate")
        for actor in ("Build Validator", "Requirement Validator", "Security Reviewer", "Performance Reviewer", "Philosophy Reviewer", "Standard Reviewer"):
            add(
                results,
                bool(re.search(rf"{re.escape(actor)}\([^)]+\)", skipped)),
                f"Docs Tiny explains skipped {actor}",
            )
    elif profile == "Code Tiny":
        add(results, docs_only is False and files is not None and files <= 3
            and lines is not None and lines <= 100 and risks == [],
            "Code Tiny obeys thresholds and has no risk triggers")
        add(
            results,
            repo_count > 0 and len(build_matches) == repo_count,
            "Code Tiny triggers one Build Validator runtime per repo",
        )
        add(results, "Requirement Validator" not in triggered, "Code Tiny skips requirement agent")
        add(results, not any(actor in triggered for actor in specialists), "Code Tiny skips specialists")
        add(
            results,
            bool(re.search(r"Requirement Validator\([^)]+\)", skipped)),
            "Code Tiny records requirement skip reason",
        )
        add(
            results,
            all(actor.removesuffix("(") in skipped for actor in specialists),
            "Code Tiny records specialist skip reasons",
        )
    elif profile == "Lite":
        add(results, docs_only is False and (
            (files is not None and files > 3)
            or (lines is not None and lines > 100)
            or bool(risks)
        ), "Lite is non-docs and fails Code Tiny eligibility")
        add(results, len(expected_specialists) <= 1,
            "Lite classification has at most one specialist trigger")
        add(
            results,
            repo_count > 0 and len(build_matches) == repo_count,
            "Lite triggers one Build Validator runtime per repo",
        )
        add(results, requirement_runtime in triggered, "Lite triggers Requirement Validator runtime")
        specialist_count = sum(triggered.count(actor) for actor in specialists)
        add(results, specialist_count <= 1, "Lite triggers at most one named specialist")
        triggered_specialists = [
            actor.removesuffix("(")
            for actor in specialists
            if actor in triggered
        ]
        add(results, all(actor in expected_specialists for actor in triggered_specialists),
            "Lite does not trigger unclassified specialists")
        if specialist_count == 0:
            add(
                results,
                all(actor.removesuffix("(") in skipped for actor in specialists),
                "Lite records why named specialists were skipped",
            )

    # v2.1.0 — Scope Drift marker required for Lite profile
    if profile == "Lite":
        scope_drift_heading = bool(re.search(r"^### Scope Drift", text, re.MULTILINE))
        scope_drift_bullet = bool(re.search(r"^- \*\*Scope Drift\*\*:", text, re.MULTILINE))
        add(results, scope_drift_heading or scope_drift_bullet,
            "Lite report contains Scope Drift marker (### Scope Drift heading or - **Scope Drift**: bullet)")

    # v2.1.0 — PR-Only header: if present, Source field in Branch Work Item Gate must be pr
    pr_only_header = field(text, "PR-Only")
    if pr_only_header == "true":
        gate_source = gate.get("Source")
        add(results, gate_source == "pr",
            "PR-Only header true requires Branch Work Item Gate Source to be pr")

    return results


def report(results, dry_run=False):
    title = f"=== OUTPUT CHECK: {SKILL} ==="
    if dry_run:
        title += " [DRY RUN]"
    lines = [title]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    fails = sum(level == "FAIL" for level, _ in results)
    passes = sum(level == "PASS" for level, _ in results)
    lines.extend(("", f"Result: {fails} FAIL, {passes} PASS"))
    return "\n".join(lines), fails


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_path", help="Path to a .lite.md review report")
    parser.add_argument("--expected-profile", choices=sorted(PROFILES))
    parser.add_argument("--expected-main-runtime",
                        help="Exact launch runtime expected in the report, e.g. 'gpt-5.5 / xhigh'")
    parser.add_argument("--dry-run", action="store_true", help="Read-only verification preview")
    args = parser.parse_args(argv)

    results = evaluate(
        args.output_path,
        args.expected_profile,
        args.expected_main_runtime,
    )
    text, fails = report(results, args.dry_run)
    print(text)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
