#!/usr/bin/env python3
"""Verify the deterministic code-review-lite v3 report contract."""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL = "code-review-lite v3.0.0"
PROFILES = {"Docs Tiny", "Code Tiny", "Lite"}
SEMANTIC_AGENTS = {
    "Requirement Validator",
    "Security Reviewer",
    "Performance Reviewer",
    "Philosophy Reviewer",
    "Standard Reviewer",
}
SPECIALISTS = SEMANTIC_AGENTS - {"Requirement Validator"}
BUILD_STATUSES = {
    "PASS",
    "PASS WITH WARNINGS",
    "FAIL",
    "NOT RUN (environment)",
    "NOT RUN (timeout)",
    "JS-SKIPPED",
}
BRANCH_FIELDS = {"Status", "Branch", "Work Item", "Source", "Reason"}
COUNTER_FIELDS = ("input", "cache read", "cache write", "output")


def field(text, name):
    match = re.search(
        rf"^\*\*{re.escape(name)}\*\*:\s*(.+?)\s*$", text, re.MULTILINE
    )
    return match.group(1).strip() if match else None


def bullet(text, name):
    match = re.search(
        rf"^- \*\*{re.escape(name)}\*\*:\s*(.+?)\s*$", text, re.MULTILINE
    )
    return match.group(1).strip() if match else None


def section(text, heading, level=2):
    marker = "#" * level
    match = re.search(
        rf"^{marker} {re.escape(heading)}\s*(.*?)(?=^#{{1,{level}}} |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else None


def section_bullets(text, heading, level=3):
    body = section(text, heading, level)
    if body is None:
        return {}
    return {
        name: value.strip()
        for name, value in re.findall(
            r"^- \*\*([^*]+)\*\*:\s*(.+?)\s*$", body, re.MULTILINE
        )
    }


def add(results, condition, message):
    results.append(("PASS" if condition else "FAIL", message))


def table_cells(line):
    if not line.strip().startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def data_rows(body, expected_columns):
    """Return parsed rows and whether every non-header pipe row is complete."""
    if body is None:
        return [], False
    rows = []
    complete = True
    for line in body.splitlines():
        cells = table_cells(line)
        if cells is None:
            continue
        if not cells or cells[0] in {"Repo", "Agent", "Requirement", "Behavior"}:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if len(cells) != expected_columns:
            complete = False
            continue
        rows.append(cells)
    return rows, complete


def normalize_cell(value):
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def parse_build_rows(text):
    body = section(text, "Build Gates", 3)
    rows, complete = data_rows(body, 7)
    parsed = []
    for cells in rows:
        repo, status, command, exit_code, errors, warnings, log_reason = map(
            normalize_cell, cells
        )
        parsed.append(
            {
                "repo": repo,
                "status": status,
                "command": command,
                "exit": exit_code,
                "errors": errors,
                "warnings": warnings,
                "log_reason": log_reason,
            }
        )
    return body, parsed, complete


def parse_agent_list(text, heading):
    body = section(text, heading, 3)
    if body is None:
        return None, []
    agents = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-") or stripped == "- None":
            continue
        match = re.match(r"^-\s+(.+?)\s+\(`[^`]+`\)\s+-\s+.+$", stripped)
        agents.append(match.group(1).strip() if match else stripped[1:].strip())
    return body, agents


def parse_usage_rows(text):
    body = section(text, "Agent Usage", 3)
    rows, complete = data_rows(body, 7)
    parsed = []
    for cells in rows:
        agent, runtime, context, input_tokens, cache_read, cache_write, output = map(
            normalize_cell, cells
        )
        parsed.append(
            {
                "agent": agent,
                "runtime": runtime,
                "context": context,
                "counters": (input_tokens, cache_read, cache_write, output),
            }
        )
    return body, parsed, complete


def is_gate_actor(name):
    lowered = name.lower()
    return "gate" in lowered or lowered in {"build validator", "branch work item"}


def valid_counter(value):
    return value == "not exposed" or bool(re.fullmatch(r"\d+", value))


def expected_specialists(text):
    value = bullet(text, "Specialist Triggers")
    if not value or value == "None":
        return []
    return [part.split("=", 1)[0].strip() for part in value.split(" | ") if "=" in part]


def load_context_manifest(report_path, text, override=None):
    """Load the report's authoritative Lite context manifest, if declared."""
    reference = override or field(text, "Context Manifest")
    if not reference or normalize_cell(reference) == "n/a":
        return reference, None, None
    manifest_path = Path(normalize_cell(reference))
    if not manifest_path.is_absolute():
        return reference, None, "context manifest path is not absolute"
    if not manifest_path.is_file():
        return reference, None, f"context manifest does not exist: {manifest_path}"
    try:
        return reference, json.loads(manifest_path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return reference, None, f"context manifest is invalid: {exc}"


def manifest_build_rows(manifest):
    """Project deterministic build JSON into the exact report-row contract."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("buildResults"), list):
        return None
    rows = []
    for record in manifest["buildResults"]:
        if not isinstance(record, dict):
            return None
        command_exit = record.get("commandExitCode")
        log_path = str(record.get("logPath") or "").strip()
        reason = str(record.get("reason") or "").strip()
        log_reason = f"{log_path} / {reason}" if log_path else reason
        rows.append(
            {
                "repo": str(record.get("repo") or ""),
                "status": str(record.get("status") or ""),
                "command": str(record.get("command") or ""),
                "exit": "n/a" if command_exit is None else str(command_exit),
                "errors": str(record.get("totalErrorCount", "")),
                "warnings": str(record.get("totalWarningCount", "")),
                "log_reason": log_reason,
            }
        )
    return rows


def evaluate(
    output_path,
    expected_profile=None,
    expected_main_runtime=None,
    context_manifest=None,
):
    path = Path(output_path)
    results = []
    add(results, path.is_file(), f"report exists: {path}")
    add(results, path.name.endswith(".lite.md"), "report uses .lite.md suffix")
    if not path.is_file():
        return results

    text = path.read_text(encoding="utf-8", errors="replace")
    profile = field(text, "Review Profile")
    main_runtime = field(text, "Main Runtime") or ""
    add(results, field(text, "Skill") == SKILL, f"Skill is exactly {SKILL}")
    add(results, profile in PROFILES, "Profile is Docs Tiny, Code Tiny, or Lite")
    manifest_reference, manifest, manifest_error = load_context_manifest(
        path, text, context_manifest
    )
    add(
        results,
        manifest_reference is not None,
        "Report declares Context Manifest (absolute path or n/a)",
    )
    if expected_profile:
        add(results, profile == expected_profile, f"Profile matches {expected_profile}")
    add(
        results,
        bool(re.fullmatch(r".+ / .+", main_runtime)),
        "Main Runtime reports model and effort visibility",
    )
    if expected_main_runtime:
        add(
            results,
            main_runtime == expected_main_runtime,
            f"Main Runtime matches expected launch runtime: {expected_main_runtime}",
        )

    required_sections = (
        "Classification",
        "Deterministic Gates",
        "Semantic Agents",
        "Requirement Evidence",
    )
    for heading in required_sections:
        add(results, section(text, heading) is not None, f"{heading} section exists")

    files_text = bullet(text, "Files Changed")
    lines_text = bullet(text, "Changed Lines")
    docs_text = bullet(text, "Documentation Only")
    risks_text = bullet(text, "Risk Triggers")
    files = int(files_text) if files_text and files_text.isdigit() else None
    lines = int(lines_text) if lines_text and lines_text.isdigit() else None
    docs_only = docs_text == "true" if docs_text in {"true", "false"} else None
    risks = [] if risks_text == "None" else [
        item.strip() for item in (risks_text or "").split(" | ") if item.strip()
    ]
    add(results, files is not None, "Classification reports Files Changed")
    add(results, lines is not None, "Classification reports Changed Lines")
    add(results, docs_only is not None, "Classification reports Documentation Only")
    add(results, risks_text is not None, "Classification reports Risk Triggers")
    add(
        results,
        bullet(text, "Specialist Triggers") is not None,
        "Classification reports Specialist Triggers",
    )

    branch = section_bullets(text, "Branch Work Item Gate")
    add(results, BRANCH_FIELDS <= set(branch), "Branch gate reports required fields")
    branch_status = branch.get("Status")
    add(
        results,
        branch_status in {"PASS", "WARN", "FAIL", "SKIPPED"},
        "Branch gate status is valid",
    )

    build_body, builds, build_rows_complete = parse_build_rows(text)
    build_not_applicable = bool(
        build_body and re.search(r"^Build Gates: Not applicable\s*$", build_body, re.MULTILINE)
    )
    add(results, build_rows_complete, "Build gate rows are complete deterministic records")
    build_records_valid = all(
        row["repo"]
        and row["command"]
        and row["status"] in BUILD_STATUSES
        and row["errors"].isdigit()
        and row["warnings"].isdigit()
        and row["log_reason"]
        and (
            row["exit"].isdigit()
            if row["status"] in {"PASS", "PASS WITH WARNINGS", "FAIL"}
            else row["exit"] == "n/a"
        )
        for row in builds
    )
    add(results, build_records_valid, "Build gate rows contain valid deterministic values")
    add(
        results,
        len({row["repo"] for row in builds}) == len(builds),
        "Build gate rows have one record per repo",
    )
    if profile == "Lite":
        add(results, manifest_error is None and manifest is not None, "Lite context manifest is readable")
        projected_builds = manifest_build_rows(manifest)
        add(
            results,
            projected_builds is not None and builds == projected_builds,
            "Build gate rows match context manifest",
        )

    _, triggered = parse_agent_list(text, "Triggered")
    usage_body, usage, usage_complete = parse_usage_rows(text)
    add(results, usage_complete, "Agent Usage rows are complete")
    add(
        results,
        not any(is_gate_actor(actor) for actor in triggered),
        "Deterministic gates never appear as semantic agents",
    )
    add(
        results,
        not any(is_gate_actor(row["agent"]) for row in usage),
        "Deterministic gates never appear in Agent Usage",
    )
    add(
        results,
        sorted(row["agent"] for row in usage) == sorted(triggered),
        "Agent Usage rows match triggered semantic agents",
    )
    add(
        results,
        all(valid_counter(value) for row in usage for value in row["counters"]),
        "Agent Usage values are non-negative integers or exact not exposed",
    )
    add(
        results,
        all(row["runtime"] and row["context"] for row in usage),
        "Agent Usage reports runtime and context mode",
    )
    if not triggered:
        add(
            results,
            bool(usage_body and re.search(r"^None\s*$", usage_body, re.MULTILINE)),
            "Zero semantic agents report Agent Usage as None",
        )

    specialists = [actor for actor in triggered if actor in SPECIALISTS]
    classified = expected_specialists(text)
    build_has_failure = any(row["status"] == "FAIL" for row in builds)
    build_has_gap = any(
        row["status"].startswith("NOT RUN") or row["status"] == "JS-SKIPPED"
        for row in builds
    )

    if profile == "Docs Tiny":
        add(results, docs_only is True, "Docs Tiny requires documentation-only scope")
        add(results, not triggered, "Docs Tiny triggers zero semantic agents")
        add(results, build_not_applicable and not builds, "Docs Tiny reports no build gates")
    elif profile == "Code Tiny":
        add(
            results,
            docs_only is False
            and files is not None
            and files <= 3
            and lines is not None
            and lines <= 100
            and not risks,
            "Code Tiny obeys Tiny thresholds and risk exclusions",
        )
        add(results, not triggered, "Code Tiny triggers zero semantic agents")
        add(results, bool(builds), "Non-doc profiles report deterministic build gate rows")
    elif profile == "Lite":
        add(
            results,
            docs_only is False
            and (
                (files is not None and files > 3)
                or (lines is not None and lines > 100)
                or bool(risks)
            ),
            "Lite is non-docs and fails Code Tiny eligibility",
        )
        add(results, bool(builds), "Non-doc profiles report deterministic build gate rows")
        add(results, len(classified) <= 1, "Lite classifies at most one specialist")
        if branch_status == "FAIL":
            add(results, not triggered, "Branch FAIL triggers zero semantic agents")
        else:
            add(
                results,
                triggered.count("Requirement Validator") == 1,
                "Lite triggers the mandatory Requirement Validator",
            )
            add(results, len(specialists) <= 1, "Lite triggers at most one named specialist")
            add(
                results,
                all(actor in classified for actor in specialists),
                "Lite triggers only the classified specialist",
            )
            if build_has_failure:
                add(
                    results,
                    triggered == ["Requirement Validator"],
                    "Lite build failure triggers Requirement Validator only",
                )
            elif build_has_gap:
                add(
                    results,
                    triggered == ["Requirement Validator"],
                    "Lite build gap triggers Requirement Validator only",
                )
            else:
                expected_agents = ["Requirement Validator", *classified]
                add(
                    results,
                    sorted(triggered) == sorted(expected_agents)
                    and len(triggered) == len(expected_agents),
                    "Lite passing builds trigger every selected semantic agent",
                )

        requirement_body = section(text, "Requirement Evidence")
        requirement_rows, requirement_complete = data_rows(requirement_body, 3)
        requirements = manifest.get("requirements", {}) if isinstance(manifest, dict) else {}
        direct = requirements.get("direct") if isinstance(requirements, dict) else None
        requires_rows = (
            isinstance(requirements, dict)
            and requirements.get("mode") == "work-item"
            and bool(str(direct or "").strip())
        )
        if requires_rows:
            add(
                results,
                requirement_complete and bool(requirement_rows),
                "Work-item Lite reports evidence for direct requirements",
            )

        behavior = section(text, "Behavior Preservation and Collateral Impact")
        behavior_rows, behavior_complete = data_rows(behavior, 6)
        valid_behavior = behavior_complete and bool(behavior_rows) and all(
            normalize_cell(row[1])
            in {"Direct requirement", "Necessary collateral", "Unrelated", "Unclear"}
            and normalize_cell(row[5]) in {"Preserved", "Regressed", "Unproven"}
            for row in behavior_rows
        )
        add(
            results,
            behavior is not None and valid_behavior,
            "Lite reports behavior-preservation and collateral-impact evidence",
        )
        add(
            results,
            bool(behavior and bullet(behavior, "Collateral Impact") is not None),
            "Lite reports Collateral Impact",
        )
        add(
            results,
            bool(behavior and bullet(behavior, "Scope Drift") is not None),
            "Lite reports Scope Drift",
        )

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
    parser.add_argument(
        "--expected-main-runtime",
        help="Exact launch runtime expected in the report, e.g. 'gpt-5.6-sol / xhigh'",
    )
    parser.add_argument(
        "--context-manifest",
        help="Absolute context manifest path (overrides the report header)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Read-only verification preview")
    args = parser.parse_args(argv)

    results = evaluate(
        args.output_path,
        args.expected_profile,
        args.expected_main_runtime,
        args.context_manifest,
    )
    output, fails = report(results, args.dry_run)
    print(output)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
