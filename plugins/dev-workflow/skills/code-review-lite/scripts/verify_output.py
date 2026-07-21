#!/usr/bin/env python3
"""Verify the deterministic code-review-lite report contract."""

import argparse
import json
import re
import sys
from pathlib import Path

LEGACY_SKILL = "code-review-lite v3.0.0"
SKILL = "code-review-lite v4.1.0"
PROFILES = {"Docs Tiny", "Code Tiny", "Lite", "No Production Code"}
SEMANTIC_AGENTS = {
    "Requirement Validator",
    "Security Reviewer",
    "Performance Reviewer",
    "Philosophy Reviewer",
    "Standard Reviewer",
}
SPECIALISTS = SEMANTIC_AGENTS - {"Requirement Validator"}
SPECIALIST_PRIORITY = (
    "Security Reviewer",
    "Philosophy Reviewer",
    "Performance Reviewer",
    "Standard Reviewer",
)
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


def specialist_trigger_entries(text):
    """Return ordered ``Reviewer=trigger`` entries, or ``None`` when malformed."""
    value = bullet(text, "Specialist Triggers")
    if value == "None":
        return []
    if not value:
        return None
    entries = value.split(" | ")
    if any(not re.fullmatch(r"(?:Security|Philosophy|Performance|Standard) Reviewer=.+", entry) for entry in entries):
        return None
    reviewers = [entry.split("=", 1)[0] for entry in entries]
    return entries if len(reviewers) == len(set(reviewers)) else None


def validate_escalation_contract(text, sidecar, tests, profile):
    """Validate the v4.1 Lite escalation fields and bounded dispatch outcome."""
    results = []
    entries = specialist_trigger_entries(text)
    policy = bullet(text, "Escalation Policy")
    decision = bullet(text, "Escalation Decision")
    selected = bullet(text, "Selected Specialist")
    unreviewed = bullet(text, "Unreviewed Risk Families")
    add(results, entries is not None, "Specialist Triggers uses exact ordered Reviewer=trigger entries or None")
    add(results, policy in {"auto", "ask"}, "Escalation Policy is auto or ask")
    add(results, decision in {"not-needed", "pro-declined"}, "Escalation Decision is not-needed or pro-declined")
    add(results, selected in {*SPECIALIST_PRIORITY, "None"}, "Selected Specialist is an exact supported value")
    add(results, unreviewed is not None, "Unreviewed Risk Families is reported")
    mirrors = {
        "escalationPolicy": policy,
        "escalationDecision": decision,
        "selectedSpecialist": selected,
        "unreviewedRiskFamilies": unreviewed,
    }
    add(results, all(sidecar.get(key) == value for key, value in mirrors.items()), "Lite metadata mirrors escalation fields exactly")
    if entries is None:
        return results

    branch = section_bullets(text, "Branch Work Item Gate")
    _, builds, _ = parse_build_rows(text)
    _, triggered = parse_agent_list(text, "Triggered")
    blocked = (
        any(row["status"] == "FAIL" or row["status"].startswith("NOT RUN") or row["status"] == "JS-SKIPPED" for row in builds)
        or tests.get("status") in {"fail", "timeout", "gap"}
    )
    branch_failed = branch.get("Status") == "FAIL"
    count = len(entries)
    expected_decision = "pro-declined" if count >= 2 else "not-needed"
    add(results, decision == expected_decision, "Escalation Decision matches triggered-family count")
    if count >= 2:
        add(results, policy == "ask", "Multi-family Lite is only allowed after ask is declined")

    if not entries:
        expected_selected = "None"
        expected_unreviewed = "None"
        expected_agents = ["Requirement Validator"] if profile == "Lite" and not branch_failed else []
    elif branch_failed or blocked:
        expected_selected = "None"
        expected_unreviewed = " | ".join(entries)
        expected_agents = [] if branch_failed else ["Requirement Validator"]
    else:
        expected_selected = next(reviewer for reviewer in SPECIALIST_PRIORITY if any(entry.startswith(f"{reviewer}=") for entry in entries))
        expected_unreviewed = " | ".join(entry for entry in entries if not entry.startswith(f"{expected_selected}=")) or "None"
        expected_agents = ["Requirement Validator", expected_selected]

    add(results, selected == expected_selected, "Selected Specialist follows gate outcome and priority")
    add(results, unreviewed == expected_unreviewed, "Unreviewed Risk Families preserves the required ordered residual list")
    add(results, triggered == expected_agents, "Semantic agents match the bounded escalation route")
    return results


def artifact_reference(text, name):
    """Read ``path / sha256:hex`` evidence from the v4 report section."""
    value = bullet(text, name)
    if not value or " / sha256:" not in value:
        return None, None
    path, digest = value.rsplit(" / sha256:", 1)
    return Path(normalize_cell(path)), digest.strip().lower()


def load_hashed_artifact(text, name, sidecar):
    path, digest = artifact_reference(text, name)
    key = {"Runtime Attestation": "runtime", "Scope Manifest": "scope", "Test Evidence": "tests"}[name]
    record = sidecar.get("artifacts", {}).get(key)
    if not path or not digest or not isinstance(record, dict):
        return None, f"{name} artifact reference is missing"
    if not path.is_absolute():
        return None, f"{name} artifact path is not absolute"
    if str(path) != str(record.get("path", "")) or digest != str(record.get("sha256", "")).lower():
        return None, f"{name} artifact hash reference disagrees with Lite metadata"
    if not path.is_file():
        return None, f"{name} artifact is missing"
    import hashlib
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        return None, f"{name} artifact SHA-256 hash does not match"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, f"{name} artifact is invalid JSON"


def runtime_meets_policy(runtime):
    """Re-evaluate attested values with the shared preflight policy implementation."""
    try:
        from review_harness.runtime_preflight import evaluate_runtime

        evaluated = evaluate_runtime(
            str(runtime.get("host", "")),
            str(runtime.get("modelId", "")),
            str(runtime.get("effort", "")),
        )
    except (ImportError, OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False
    return evaluated.get("status") == "pass"


def valid_test_run(run):
    """Require status, exit code, and count evidence to agree."""
    if not isinstance(run, dict) or run.get("status") not in {"pass", "fail", "timeout"}:
        return False
    counts = run.get("counts")
    if (
        not isinstance(run.get("command"), list)
        or not run["command"]
        or not all(isinstance(part, str) and part for part in run["command"])
        or not isinstance(counts, dict)
        or ("repo" in run and (not isinstance(run["repo"], str) or not run["repo"].strip()))
    ):
        return False
    if not isinstance(run.get("exitCode"), int) or any(
        not isinstance(counts.get(key), int) or counts[key] < 0
        for key in ("passed", "failed", "skipped")
    ):
        return False
    if run["status"] == "pass":
        return run["exitCode"] == 0 and counts["failed"] == 0
    if run["status"] == "fail":
        return run["exitCode"] != 0 and counts["failed"] > 0
    return run["exitCode"] != 0 and sum(counts.values()) == 0


def test_runs(tests):
    """Return flat test runs from legacy ``runs`` or v4 multi-repo ``executions``."""
    runs_value = tests.get("runs")
    executions_value = tests.get("executions")
    if runs_value is not None and executions_value is not None:
        return [], False
    source = executions_value if executions_value is not None else runs_value
    if not isinstance(source, list):
        return [], False
    flattened = []
    for execution in source:
        if not isinstance(execution, dict):
            return [], False
        nested = execution.get("runs")
        if nested is None:
            flattened.append(execution)
            continue
        repo = execution.get("repo")
        if not isinstance(repo, str) or not repo.strip() or not isinstance(nested, list) or not nested:
            return [], False
        for run in nested:
            if not isinstance(run, dict):
                return [], False
            flattened.append({"repo": repo, **run})
    return flattened, True


def normalized_scope_path(value):
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().replace("\\", "/").removeprefix("./").casefold()


def findings_are_none(body):
    return bool(body is not None and re.fullmatch(r"\s*None\.?\s*", body, re.IGNORECASE))


def finding_targets(body):
    """Parse finding targets only; evidence citations are intentionally unrestricted."""
    if body is None:
        return [], 0
    headings = re.findall(r"^###\s+.+$", body, re.MULTILINE)
    targets = []
    for raw in re.findall(r"^- \*\*Target\*\*:\s*`([^`]+)`\s*$", body, re.MULTILINE):
        match = re.fullmatch(r"(.+?):\d+(?:-\d+)?", raw.strip())
        targets.append(match.group(1) if match else None)
    return targets, len(headings)


def validate_preserved_gates(text, profile, tests):
    """Keep the deterministic v3 review evidence checks active for v4 reports."""
    results = []
    for heading in ("Classification", "Deterministic Gates", "Semantic Agents", "Requirement Evidence"):
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
    add(results, bullet(text, "Specialist Triggers") is not None, "Classification reports Specialist Triggers")
    branch = section_bullets(text, "Branch Work Item Gate")
    add(results, BRANCH_FIELDS <= set(branch), "Branch gate reports required fields")
    branch_status = branch.get("Status")
    add(results, branch_status in {"PASS", "WARN", "FAIL", "SKIPPED"}, "Branch gate status is valid")
    build_body, builds, complete = parse_build_rows(text)
    not_applicable = bool(build_body and re.search(r"^Build Gates: Not applicable\s*$", build_body, re.MULTILINE))
    add(results, complete, "Build gate rows are complete deterministic records")
    add(
        results,
        all(
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
            and (row["status"] not in {"PASS", "PASS WITH WARNINGS"} or row["exit"] == "0")
            and (row["status"] != "FAIL" or (row["exit"].isdigit() and int(row["exit"]) != 0))
            for row in builds
        ),
        "Build gate rows contain valid deterministic values",
    )
    add(results, len({row["repo"] for row in builds}) == len(builds), "Build gate rows have one record per repo")
    usage_body, usage, usage_complete = parse_usage_rows(text)
    _, triggered = parse_agent_list(text, "Triggered")
    add(results, usage_complete, "Agent Usage rows are complete")
    add(results, not any(is_gate_actor(actor) for actor in triggered), "Deterministic gates never appear as semantic agents")
    add(results, not any(is_gate_actor(row["agent"]) for row in usage), "Deterministic gates never appear in Agent Usage")
    add(results, sorted(row["agent"] for row in usage) == sorted(triggered), "Agent Usage rows match triggered semantic agents")
    add(results, len(triggered) == len(set(triggered)), "Semantic agent triggers are unique")
    add(results, len(usage) == len({row["agent"] for row in usage}), "Agent Usage rows are unique")
    add(results, all(valid_counter(value) for row in usage for value in row["counters"]), "Agent Usage values are non-negative integers or exact not exposed")
    add(results, all(row["runtime"] and row["context"] for row in usage), "Agent Usage reports runtime and context mode")
    if not triggered:
        add(results, bool(usage_body and re.search(r"^None\s*$", usage_body, re.MULTILINE)), "Zero semantic agents report Agent Usage as None")
    if profile == "No Production Code":
        add(results, not_applicable and not builds, "No Production Code reports no build gates")
        add(results, not triggered, "No Production Code triggers zero semantic agents")
        return results
    add(results, bool(builds), "Production profiles report deterministic build gate rows")
    if profile == "Code Tiny":
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
    if profile == "Lite":
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
        requirements = section(text, "Requirement Evidence")
        req_rows, req_complete = data_rows(requirements, 3)
        add(
            results,
            req_complete
            and bool(req_rows)
            and all(normalize_cell(row[1]) in {"Addressed", "Partial", "Missing", "Not verifiable"} for row in req_rows),
            "Work-item Lite reports evidence for direct requirements",
        )
        behavior = section(text, "Behavior Preservation and Collateral Impact")
        behavior_rows, behavior_complete = data_rows(behavior, 6)
        add(
            results,
            behavior is not None
            and behavior_complete
            and bool(behavior_rows)
            and all(
                normalize_cell(row[1]) in {"Direct requirement", "Necessary collateral", "Unrelated", "Unclear"}
                and normalize_cell(row[5]) in {"Preserved", "Regressed", "Unproven"}
                for row in behavior_rows
            ),
            "Lite reports behavior-preservation and collateral-impact evidence",
        )
        add(results, bool(behavior and bullet(behavior, "Collateral Impact") is not None), "Lite reports Collateral Impact")
        add(results, bool(behavior and bullet(behavior, "Scope Drift") is not None), "Lite reports Scope Drift")
    return results


def evaluate_v4(path, text, expected_profile=None, sidecar_override=None):
    """Fail-closed verifier for the v4 runtime/scope/test evidence contract."""
    results = []
    profile = field(text, "Review Profile")
    add(results, profile in PROFILES, "Profile is a supported v4 profile")
    if expected_profile:
        add(
            results,
            profile == expected_profile or (expected_profile == "Lite" and profile == "No Production Code"),
            f"Profile matches {expected_profile}",
        )
    add(results, field(text, "Skill") == SKILL, f"Skill is exactly {SKILL}")
    report_sidecar_ref = bullet(text, "Lite Metadata")
    sidecar_ref = sidecar_override or report_sidecar_ref
    sidecar_path = Path(normalize_cell(str(sidecar_ref or "")))
    add(
        results,
        bool(sidecar_ref)
        and normalize_cell(str(sidecar_ref or "")) != "n/a"
        and sidecar_path.is_absolute()
        and sidecar_path.is_file(),
        "Lite metadata sidecar exists at an absolute path",
    )
    if sidecar_override and report_sidecar_ref and normalize_cell(report_sidecar_ref) != "n/a":
        add(
            results,
            Path(normalize_cell(report_sidecar_ref)) == sidecar_path,
            "Explicit sidecar agrees with the report metadata reference",
        )
    sidecar = {}
    if sidecar_path.is_file():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    add(results, sidecar.get("recordVersion") == 3, "Lite metadata uses recordVersion 3")
    add(
        results,
        bool(re.fullmatch(r"\.[A-Za-z0-9][A-Za-z0-9._-]*\.lite\.review-meta\.json", sidecar_path.name)),
        "Lite metadata has collision-safe safe-branch name",
    )
    runtime, runtime_error = load_hashed_artifact(text, "Runtime Attestation", sidecar)
    scope, scope_error = load_hashed_artifact(text, "Scope Manifest", sidecar)
    tests, tests_error = load_hashed_artifact(text, "Test Evidence", sidecar)
    for error in (runtime_error, scope_error, tests_error):
        add(results, error is None, error or "hashed artifact is valid")
    runtime = runtime or {}
    scope = scope or {}
    tests = tests or {}
    side_runtime = sidecar.get("runtime", {})
    exact_runtime = f"{runtime.get('modelId', '')} / {runtime.get('effort', '')}"
    required_runtime_fields = {
        "status",
        "host",
        "sessionId",
        "modelId",
        "effort",
        "thinkingEnabled",
        "source",
        "crossChecks",
        "freshness",
        "sessionStatus",
        "overrideRecorded",
    }
    add(results, required_runtime_fields <= set(runtime), "Runtime attestation is complete")
    add(results, runtime.get("status") == "pass", "Runtime attestation status is pass")
    add(results, runtime_meets_policy(runtime), "Runtime attestation meets shared runtime policy")
    add(
        results,
        bool(runtime.get("host"))
        and bool(runtime.get("sessionId"))
        and runtime.get("freshness") == "current"
        and isinstance(runtime.get("crossChecks"), list)
        and bool(runtime.get("crossChecks")),
        "Runtime attestation identifies a current cross-checked host session",
    )
    add(results, sidecar.get("skillName") == "code-review-lite", "Lite metadata skillName is code-review-lite")
    add(results, sidecar.get("skillVersion") == "4.1.0", "Lite metadata skillVersion is 4.1.0")
    add(results, sidecar.get("reviewProfile") == profile, "Lite metadata reviewProfile matches report")
    add(results, side_runtime == runtime, "Lite metadata runtime matches attestation")
    add(results, field(text, "Main Runtime") == exact_runtime, "Report runtime matches attested runtime")
    session = sidecar.get("session", {})
    existing = session.get("sessionStatus") == "existing"
    expected_session = {
        "status": runtime.get("status"),
        "sessionStatus": runtime.get("sessionStatus"),
        "overrideRecorded": runtime.get("overrideRecorded"),
    }
    add(results, session == expected_session, "Lite metadata session matches attestation")
    add(
        results,
        session.get("status") == "pass"
        and session.get("sessionStatus") in {"fresh", "existing"}
        and (not existing or session.get("overrideRecorded") is True)
        and (existing or session.get("overrideRecorded") is False),
        "Existing session requires recorded override",
    )
    production = scope.get("productionFiles")
    evidence = scope.get("evidenceFiles")
    excluded = scope.get("excludedFiles")
    add(results, isinstance(production, list) and isinstance(evidence, list) and isinstance(excluded, list), "Scope manifest contains production, evidence, and excluded lists")
    all_scopes = production + evidence + excluded if all(isinstance(value, list) for value in (production, evidence, excluded)) else []
    normalized_scopes = [normalized_scope_path(value) for value in all_scopes]
    add(
        results,
        bool(all(value is not None for value in normalized_scopes))
        and len(normalized_scopes) == len(set(normalized_scopes)),
        "Scope lists have no duplicate or overlapping paths",
    )
    add(results, sidecar.get("productionAllowlist") == production, "Lite metadata preserves the production allowlist")
    _, triggered = parse_agent_list(text, "Triggered")
    findings = section(text, "Detailed Findings") or ""
    if scope.get("status") == "no-production-code":
        add(results, profile == "No Production Code", "Evidence-only scope uses No Production Code profile")
        add(results, production == [], "No Production Code has an empty production allowlist")
        add(results, not triggered, "No Production Code has no semantic execution")
        add(results, findings_are_none(findings), "No Production Code has no findings")
        add(results, field(text, "Context Manifest") in {None, "n/a"}, "No Production Code has no context execution")
        add(
            results,
            not sidecar.get("worktreeCreated")
            and not sidecar.get("contextCreated")
            and not sidecar.get("contextManifest"),
            "No Production Code has no worktree or context execution",
        )
        add(
            results,
            not sidecar.get("buildExecuted") and not sidecar.get("buildResults"),
            "No Production Code has no build execution",
        )
        add(
            results,
            not sidecar.get("semanticReviewExecuted") and not sidecar.get("semanticAgents"),
            "No Production Code has no semantic execution metadata",
        )
    else:
        add(results, scope.get("status") == "pass" and bool(production), "Production scope has an allowlist")
        targets, finding_count = finding_targets(findings)
        allowed = {normalized_scope_path(value) for value in production or []}
        add(
            results,
            (findings_are_none(findings) and finding_count == 0)
            or (
                finding_count > 0
                and len(targets) == finding_count
                and all(target is not None and normalized_scope_path(target) in allowed for target in targets)
            ),
            "Findings target production allowlist only",
        )
    runs, executions_valid = test_runs(tests)
    valid_runs = executions_valid and all(valid_test_run(run) for run in runs)
    add(results, valid_runs, "Test runs have consistent status, exit, and count evidence")
    status = tests.get("status")
    valid_status = status in {"pass", "advisory", "fail", "timeout", "gap", "not-applicable"}
    add(results, valid_status, "Test evidence status is valid")
    blocking = tests.get("blocking") is True
    if status in {"pass", "advisory", "not-applicable"}:
        add(results, not blocking, "Non-blocking test status is not marked blocking")
    if status in {"fail", "timeout", "gap"}:
        add(results, blocking, "Failed, timeout, or gap test evidence is blocking")
    if status == "gap":
        add(results, not runs and bool(tests.get("reasonCode")), "Test gap has no fabricated test runs and records a reason")
    if status in {"fail", "timeout"}:
        add(results, any(run.get("status") == status for run in runs), "Blocking test status has a matching test run")
    if status == "fail":
        add(results, any(run.get("status") == "fail" for run in runs), "Failed test evidence includes a failed execution")
    if status == "timeout":
        add(
            results,
            any(run.get("status") == "timeout" for run in runs)
            and not any(run.get("status") == "fail" for run in runs),
            "Timeout test evidence includes a timeout and no failed execution",
        )
    if status in {"pass", "advisory"}:
        add(results, all(run.get("status") == "pass" for run in runs), "Passing or advisory evidence contains only passing executions")
    advisory = tests.get("advisory")
    add(results, advisory in {None, "use-unit-testing"}, "Test advisory is valid")
    changed_symbols = tests.get("changedSymbols")
    direct_tests = tests.get("directTests")
    affected_tests = tests.get("affectedTests")
    add(
        results,
        isinstance(changed_symbols, list)
        and isinstance(direct_tests, list)
        and isinstance(affected_tests, list),
        "Test evidence identifies changed symbols, direct tests, and affected tests",
    )
    missing_direct = bool(changed_symbols) and not direct_tests
    add(results, (missing_direct and status == "advisory" and advisory == "use-unit-testing") or (not missing_direct and advisory is None), "Changed symbols and direct tests have the required advisory relationship")
    if missing_direct:
        add(results, bullet(text, "Unit-Test Advisory") == "use-unit-testing", "Missing direct tests report exact use-unit-testing advisory")
    else:
        add(results, bullet(text, "Unit-Test Advisory") is None, "Unit-test advisory appears only for changed symbols without direct tests")
    if status in {"fail", "timeout", "gap"}:
        add(results, triggered == ["Requirement Validator"], "Test failure or gap routes Requirement Validator only")
        test_gate = bullet(text, "Test Gate") or ""
        add(
            results,
            test_gate.casefold().startswith("blocked") and status in test_gate.casefold(),
            "Blocking test evidence is reported as a blocked Test Gate",
        )
    if profile == "No Production Code":
        add(
            results,
            status == "not-applicable"
            and tests.get("reasonCode") == "no-production-code"
            and not runs
            and changed_symbols == []
            and direct_tests == []
            and affected_tests == []
            and advisory is None,
            "No Production Code keeps not-applicable test evidence without execution",
        )
    results.extend(validate_preserved_gates(text, profile, tests))
    results.extend(validate_escalation_contract(text, sidecar, tests, profile))
    return results


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
    _legacy_expected_main_runtime=None,
    context_manifest=None,
    sidecar=None,
):
    path = Path(output_path)
    results = []
    add(results, path.is_file(), f"report exists: {path}")
    add(results, path.name.endswith(".lite.md"), "report uses .lite.md suffix")
    if not path.is_file():
        return results

    text = path.read_text(encoding="utf-8", errors="replace")
    if field(text, "Skill") == SKILL:
        results.extend(evaluate_v4(path, text, expected_profile, sidecar))
        return results
    add(results, False, f"Only {SKILL} reports are accepted")
    profile = field(text, "Review Profile")
    main_runtime = field(text, "Main Runtime") or ""
    add(results, field(text, "Skill") == LEGACY_SKILL, f"Skill is exactly {LEGACY_SKILL}")
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
        "--sidecar",
        type=Path,
        help="Authoritative Lite metadata sidecar; otherwise infer it from the report",
    )
    parser.add_argument("--dry-run", action="store_true", help="Read-only verification preview")
    args = parser.parse_args(argv)

    results = evaluate(
        args.output_path,
        args.expected_profile,
        sidecar=args.sidecar,
    )
    output, fails = report(results, args.dry_run)
    print(output)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
