#!/usr/bin/env python3
"""Verify the strict code-review-pro v3 report package."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


SKILL = "code-review-pro v3.0.0"
PROFILES = {"No-production-code", "Tiny", "Pro"}
BRANCH_GATE_FIELDS = {
    "Status", "Branch", "Prefix", "Work Item ID", "Expected Type",
    "Actual Type", "Title", "State", "Source", "Reason",
}
BRANCH_GATE_SIDE_FIELDS = {
    "status", "branch", "prefix", "workItemId", "expectedType",
    "actualType", "title", "state", "source", "reason",
}
SPECIALISTS = ("Security", "Performance", "Philosophy", "Standard")
REQUIRED_HEADINGS = (
    "## Runtime Evidence",
    "## Scope Evidence",
    "## Test Evidence",
    "## Review Classification",
    "## Branch Work Item Gate",
    "## Build Status",
    "## Semantic Review",
    "## Requirement Validation",
    "## Summary",
    "## Detailed Findings",
)


def add(results, ok, message):
    results.append(("PASS" if ok else "FAIL", message))


def field(text, name):
    matches = re.findall(rf"^\*\*{re.escape(name)}\*\*: (.+)$", text, re.MULTILINE)
    if len(matches) != 1:
        return None, f"{name} field appears {len(matches)} times"
    return matches[0].strip(), None


def records(value):
    if not value or value == "None":
        return []
    return [item.strip() for item in value.split(" | ") if item.strip()]


def bullet(text, name):
    matches = re.findall(
        rf"^- \*\*{re.escape(name)}\*\*: (.+)$",
        text,
        re.MULTILINE,
    )
    return matches[0].strip() if len(matches) == 1 else None


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
            r"^- \*\*([^*]+)\*\*: (.+)$",
            match.group(1),
            re.MULTILINE,
        )
    }


def infer_sidecar(report):
    return report.with_name(f".{report.stem}.review-meta.json")


def _is_string(value):
    return isinstance(value, str) and bool(value.strip())


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _string_list(value, *, allow_empty=True):
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_is_string(item) for item in value)
        and len(value) == len(set(value))
    )


def _actor(records_list, prefix):
    return [item for item in records_list if item.startswith(prefix)]


def _artifact(sidecar, reference, name, results):
    """Load one JSON artifact only when its contained path and digest bind."""
    reference_ok = (
        isinstance(reference, dict)
        and set(reference) == {"path", "sha256"}
        and _is_string(reference.get("path"))
        and isinstance(reference.get("sha256"), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]))
    )
    add(results, reference_ok, f"{name} reference has path and sha256")
    if not reference_ok:
        return {}

    relative = Path(reference["path"])
    root = sidecar.parent.resolve()
    candidate = (root / relative).resolve()
    contained = not relative.is_absolute() and candidate.is_relative_to(root)
    add(results, contained, f"{name} artifact path is relative and contained")
    exists = contained and candidate.is_file()
    add(results, exists, f"{name} artifact exists")
    if not exists:
        return {}

    try:
        payload = candidate.read_bytes()
    except OSError:
        add(results, False, f"{name} artifact is readable")
        return {}
    add(results, hashlib.sha256(payload).hexdigest() == reference["sha256"],
        f"{name} artifact SHA-256 matches")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        add(results, False, f"{name} artifact is JSON")
        return {}
    add(results, isinstance(parsed, dict), f"{name} artifact is a JSON object")
    return parsed if isinstance(parsed, dict) else {}


def _validate_runtime(text, values, data, runtime, results):
    required = {
        "status", "host", "sessionId", "modelId", "effort",
        "thinkingEnabled", "source", "crossChecks", "freshness",
        "sessionStatus", "overrideRecorded",
    }
    add(results, required <= set(runtime), "runtime attestation is complete")
    add(results, runtime.get("status") == "pass", "runtime attestation status is pass")
    add(results, runtime.get("sessionStatus") in {"fresh", "existing"},
        "runtime attestation sessionStatus is valid")
    add(results, isinstance(runtime.get("overrideRecorded"), bool),
        "runtime attestation overrideRecorded is boolean")
    add(results, all(_is_string(runtime.get(key)) for key in
                     ("host", "sessionId", "modelId", "effort", "source")),
        "runtime attestation identity fields are populated")
    add(results,
        _is_string(runtime.get("host"))
        and _is_string(runtime.get("sessionId"))
        and runtime.get("freshness") == "current"
        and _string_list(runtime.get("crossChecks"), allow_empty=False),
        "runtime attestation identifies a current cross-checked host session")

    session = data.get("session")
    add(results, isinstance(session, dict)
        and set(session) >= {"status", "overrideRecorded"}, "session record exists")
    if isinstance(session, dict):
        add(results, session.get("status") == runtime.get("sessionStatus"),
            "session matches attestation")
        add(results, session.get("overrideRecorded") == runtime.get("overrideRecorded"),
            "session override matches attestation")
    add(results, runtime.get("sessionStatus") != "existing"
        or runtime.get("overrideRecorded") is True,
        "existing session requires recorded override")
    add(results, runtime.get("sessionStatus") != "fresh"
        or runtime.get("overrideRecorded") is False,
        "fresh session requires overrideRecorded false")

    attested = f"{runtime.get('modelId')} / {runtime.get('effort')}"
    add(results, values.get("Main Runtime") == attested,
        "Main Runtime matches attested modelId / effort")
    runtime_section = section_bullets(text, "## Runtime Evidence")
    add(results, runtime_section.get("Status") == "PASS",
        "Runtime Evidence status is PASS")

    try:
        harness_root = str(Path(__file__).resolve().parent)
        if harness_root not in sys.path:
            sys.path.insert(0, harness_root)
        from review_harness.runtime_preflight import evaluate_runtime
        policy = evaluate_runtime(
            runtime.get("host", ""), runtime.get("modelId", ""),
            runtime.get("effort", ""),
        )
        thinking_enabled = runtime.get("thinkingEnabled")
        policy_ok = (
            policy.get("status") == "pass"
            and (
                thinking_enabled is True
                or (runtime.get("host") == "codex" and thinking_enabled is None)
            )
        )
    except (ImportError, OSError, UnicodeError, json.JSONDecodeError,
            KeyError, TypeError, ValueError):
        policy_ok = False
    add(results, policy_ok, "runtime attestation meets shared runtime policy")


def _validate_scope(text, data, scope, results):
    production = scope.get("productionFiles")
    evidence = scope.get("evidenceFiles")
    excluded = scope.get("excludedFiles")
    arrays_ok = all(_string_list(value) for value in (production, evidence, excluded))
    add(results, arrays_ok, "scope file lists are unique string arrays")
    production = production if isinstance(production, list) else []
    evidence = evidence if isinstance(evidence, list) else []
    excluded = excluded if isinstance(excluded, list) else []

    files = scope.get("files")
    files_ok = isinstance(files, list) and all(
        isinstance(entry, dict)
        and _is_string(entry.get("path"))
        and entry.get("classification") in {"production", "evidence", "excluded"}
        and _is_string(entry.get("reasonCode"))
        for entry in files
    )
    add(results, files_ok, "scope files entries are complete and classified")
    files = files if isinstance(files, list) else []
    paths = [entry.get("path") for entry in files if isinstance(entry, dict)]
    add(results, len(paths) == len(set(paths)), "scope files contain no duplicate paths")
    add(results, not (
        set(production) & set(evidence)
        or set(production) & set(excluded)
        or set(evidence) & set(excluded)
    ), "scope arrays have no overlap")
    projection = {
        kind: [
            entry.get("path") for entry in files
            if isinstance(entry, dict) and entry.get("classification") == kind
        ]
        for kind in ("production", "evidence", "excluded")
    }
    add(results,
        production == projection["production"]
        and evidence == projection["evidence"]
        and excluded == projection["excluded"],
        "scope arrays exactly recompute from files entries")

    expected_status = "pass" if production else "no-production-code"
    add(results, scope.get("status") == expected_status,
        "scope status matches productionFiles")
    add(results, data.get("productionFiles") == production,
        "sidecar productionFiles match scope manifest")
    add(results, data.get("evidenceFiles") == evidence,
        "sidecar evidenceFiles match scope manifest")
    add(results, data.get("excludedFiles") == excluded,
        "sidecar excludedFiles match scope manifest")
    add(results, data.get("reviewedFiles") == production,
        "reviewedFiles exactly match scope productionFiles")
    scope_section = section_bullets(text, "## Scope Evidence")
    add(results, scope_section.get("Status") == scope.get("status"),
        "Scope Evidence status matches manifest")
    return production, evidence, excluded


def _validate_discovery(discovery, evidence, results, *, no_production=False):
    required = {"status", "advisory", "changedSymbols", "directTests", "affectedTests"}
    add(results, isinstance(discovery, dict) and required <= set(discovery),
        "test discovery contains required fields")
    discovery = discovery if isinstance(discovery, dict) else {}
    advisory = discovery.get("advisory")
    symbols = discovery.get("changedSymbols")
    direct = discovery.get("directTests")
    affected = discovery.get("affectedTests")
    lists_ok = all(_string_list(value) for value in (symbols, direct, affected))
    add(results, lists_ok, "test discovery lists are unique string arrays")
    symbols = symbols if isinstance(symbols, list) else []
    direct = direct if isinstance(direct, list) else []
    affected = affected if isinstance(affected, list) else []
    linkage_ok = (
        not symbols and not direct and not affected and advisory is None
        if no_production
        else (
            (bool(symbols) and bool(direct) and advisory is None)
            or (bool(symbols) and not direct and advisory == "use-unit-testing")
            or (not symbols and not direct and advisory is None)
        )
    )
    add(results, linkage_ok,
        "changed symbols and direct-test advisory contract is valid")
    expected_status = (
        "not-applicable" if no_production
        else "advisory" if advisory else "pass"
    )
    add(results, discovery.get("status") == expected_status,
        "test discovery status matches advisory")
    add(results, all(path in evidence for path in [*direct, *affected]),
        "direct and affected tests are evidence files")
    return advisory


def _run_valid(run):
    if not isinstance(run, dict):
        return False
    required = {
        "repo", "status", "command", "exitCode", "durationMs", "counts",
        "stdout", "stderr", "logsTruncated",
    }
    if not required <= set(run):
        return False
    counts = run.get("counts")
    command = run.get("command")
    shape_ok = (
        _is_string(run.get("repo"))
        and run.get("status") in {"pass", "fail", "timeout"}
        and isinstance(command, list) and bool(command)
        and all(_is_string(part) for part in command)
        and _is_int(run.get("exitCode"))
        and _is_int(run.get("durationMs")) and run["durationMs"] >= 0
        and isinstance(counts, dict)
        and {"passed", "failed", "skipped"} <= set(counts)
        and all(_is_int(counts.get(key)) and counts[key] >= 0
                for key in ("passed", "failed", "skipped"))
        and isinstance(run.get("stdout"), str)
        and isinstance(run.get("stderr"), str)
        and isinstance(run.get("logsTruncated"), bool)
    )
    if not shape_ok:
        return False
    if run["status"] == "pass":
        return run["exitCode"] == 0 and counts["failed"] == 0
    if run["status"] == "fail":
        return run["exitCode"] != 0 and counts["failed"] > 0
    return run["exitCode"] == 124 and counts["failed"] == 0


def _validate_tests(text, data, tests, evidence, production, results):
    discovery = tests.get("discovery")
    advisory = _validate_discovery(
        discovery, evidence, results, no_production=not production,
    )
    executions = tests.get("executions")
    executions = executions if isinstance(executions, list) else []
    repos = data.get("reposReviewed")
    add(results, _string_list(repos), "reposReviewed is a unique string array")

    if not production:
        no_execution = (
            isinstance(tests.get("executions"), list)
            and not executions
            and tests.get("status") == "not-applicable"
            and repos == []
        )
        add(results, no_execution,
            "No-production-code test evidence is not-applicable with no executions or repositories")
        gate = data.get("testGate")
        routed = (
            isinstance(gate, dict)
            and gate.get("status") == "NOT-APPLICABLE"
            and gate.get("blocking") is False
        )
        add(results, routed, "test execution outcomes match blocking routing")
        report_tests = section_bullets(text, "## Test Evidence")
        add(results, report_tests.get("Status") == "NOT-APPLICABLE",
            "Test Evidence status matches execution routing")
        add(results, report_tests.get("Advisory") == "None",
            "Test Evidence advisory matches discovery")
        return [], "not-applicable"

    add(results, isinstance(tests.get("executions"), list) and bool(executions),
        "test evidence has non-empty executions array")
    names = [run.get("repo") for run in executions if isinstance(run, dict)]
    complete = (
        bool(executions)
        and len(names) == len(executions)
        and len(names) == len(set(names))
        and all(_run_valid(run) for run in executions)
    )
    add(results, complete, "test execution records are complete and consistent")

    overall = "pass" if complete and all(
        run.get("status") == "pass" for run in executions
    ) else "blocked"
    gate = data.get("testGate")
    routed = (
        tests.get("status") == overall
        and isinstance(gate, dict)
        and gate.get("status") == ("PASS" if overall == "pass" else "BLOCKED")
        and gate.get("blocking") is (overall == "blocked")
    )
    add(results, routed, "test execution outcomes match blocking routing")
    report_tests = section_bullets(text, "## Test Evidence")
    add(results, report_tests.get("Status") ==
        ("PASS" if overall == "pass" else "BLOCKED"),
        "Test Evidence status matches execution routing")
    add(results, report_tests.get("Advisory") == (advisory or "None"),
        "Test Evidence advisory matches discovery")

    add(results, repos == names, "reposReviewed matches test execution repositories")
    return names, overall


def _parse_specialist_bullet(value):
    parsed = {}
    if not value or value == "None":
        return parsed
    for item in records(value):
        if "=" not in item:
            return None
        reviewer, trigger = item.split("=", 1)
        parsed.setdefault(reviewer, []).append(trigger)
    return parsed


def _validate_classifier(text, values, data, scope, production, results):
    classifier = data.get("classifier")
    required = {
        "filesChanged", "changedLines", "scopeStatus", "riskTriggers",
        "specialistTriggers",
    }
    classifier_ok = (
        isinstance(classifier, dict)
        and required <= set(classifier)
        and "docsOnly" not in classifier
    )
    add(results, classifier_ok, "classifier uses scopeStatus and excludes docsOnly")
    classifier = classifier if isinstance(classifier, dict) else {}
    risks = classifier.get("riskTriggers")
    specialist_triggers = classifier.get("specialistTriggers")
    types_ok = (
        _is_int(classifier.get("filesChanged"))
        and classifier["filesChanged"] >= 0
        and _is_int(classifier.get("changedLines"))
        and classifier["changedLines"] >= 0
        and classifier.get("scopeStatus") in {"pass", "no-production-code"}
        and classifier.get("scopeStatus") == scope.get("status")
        and _string_list(risks)
        and isinstance(specialist_triggers, dict)
        and all(
            reviewer in {f"{name} Reviewer" for name in SPECIALISTS}
            and _string_list(triggers, allow_empty=False)
            for reviewer, triggers in specialist_triggers.items()
        )
    )
    add(results, types_ok, "classifier field types are valid")
    risks = risks if isinstance(risks, list) else []
    specialist_triggers = specialist_triggers if isinstance(specialist_triggers, dict) else {}
    add(results, all(trigger in risks for triggers in specialist_triggers.values()
                     if isinstance(triggers, list) for trigger in triggers),
        "specialist triggers are classified risk triggers")

    classification = section_bullets(text, "## Review Classification")
    add(results, classification.get("Files Changed") == str(classifier.get("filesChanged")),
        "report Files Changed matches sidecar classifier")
    add(results, classification.get("Changed Lines") == str(classifier.get("changedLines")),
        "report Changed Lines matches sidecar classifier")
    add(results, classification.get("Scope Status") == classifier.get("scopeStatus"),
        "report Scope Status matches sidecar classifier")
    add(results, "Docs Only" not in classification,
        "report classifier excludes deprecated Docs Only")
    report_risks = classification.get("Risk Triggers")
    add(results, ([] if report_risks == "None" else records(report_risks)) == risks,
        "report Risk Triggers match sidecar classifier")
    add(results, _parse_specialist_bullet(classification.get("Specialist Triggers"))
        == specialist_triggers,
        "report Specialist Triggers match sidecar classifier")

    profile = values.get("Review Profile")
    if profile == "No-production-code":
        add(results, not production and classifier.get("scopeStatus") == "no-production-code"
            and not risks and not specialist_triggers,
            "No-production-code follows empty production scope")
    elif profile == "Tiny":
        add(results, bool(production) and classifier.get("scopeStatus") == "pass"
            and classifier.get("filesChanged", -1) <= 3
            and classifier.get("changedLines", -1) <= 100
            and not risks and not specialist_triggers,
            "Tiny obeys thresholds and has no risk triggers")
    elif profile == "Pro":
        add(results, bool(production) and classifier.get("scopeStatus") == "pass"
            and (classifier.get("filesChanged", 0) > 3
                 or classifier.get("changedLines", 0) > 100 or bool(risks)),
            "Pro is non-docs and fails Tiny eligibility")
        add(results, data.get("requirementMode") in {"work-item", "regression-only"},
            "Pro records required requirement mode")
        add(results, "### Scope Drift" in text or bullet(text, "Scope Drift") is not None,
            "Pro report contains Scope Drift marker")
    return risks, specialist_triggers


def _validate_retained(text, values, data, results):
    required = {
        "reviewKind", "classifier", "branchWorkItemGate", "runtime", "triggered",
        "skipped", "reposReviewed", "requirementMode", "reviewedCommit",
        "targetBranch", "workItemId", "scopeType", "scopeBase",
        "diffFingerprint", "standardsPaths", "exemplarMap", "reviewedFiles",
        "iteration", "reviewedAt", "prOnlyMode", "prMergePreview",
        "mergePreviewStrategy", "jsDepsStrategy", "findings", "testGate",
        "blockingValidations", "productionFiles", "evidenceFiles", "excludedFiles",
        "runtimeAttestation", "scopeManifest", "testEvidence", "session",
    }
    add(results, required <= set(data), "sidecar contains retained v3 provenance fields")
    add(results, _is_string(data.get("reviewedCommit")), "reviewedCommit is populated")
    add(results, _is_string(data.get("targetBranch")), "targetBranch is populated")
    add(results, data.get("scopeType") in {"pr", "branch", "staged", "working", "files"},
        "scopeType is valid")
    add(results, _is_string(data.get("scopeBase")), "scopeBase is populated")
    fingerprint = data.get("diffFingerprint")
    add(results, isinstance(fingerprint, str) and fingerprint.startswith("sha256:")
        and len(fingerprint) > len("sha256:"), "diffFingerprint is populated SHA-256")
    add(results, data.get("reviewKind") in {"initial", "follow-up"},
        "reviewKind is initial or follow-up")
    add(results, _is_int(data.get("iteration")) and data.get("iteration", 0) >= 1,
        "iteration is a positive integer")
    add(results, data.get("reviewKind") != "initial" or data.get("iteration") == 1,
        "initial review uses iteration 1")
    add(results, data.get("reviewKind") != "follow-up" or data.get("iteration", 0) >= 2,
        "follow-up review increments iteration")
    add(results, _string_list(data.get("standardsPaths")), "standardsPaths is a list")
    add(results, isinstance(data.get("exemplarMap"), dict), "exemplarMap is an object")
    add(results, _is_string(data.get("reviewedAt")), "reviewedAt is populated")
    add(results, data.get("workItemId") is None or
        (_is_int(data.get("workItemId")) and data["workItemId"] > 0),
        "workItemId is positive integer or null")

    scope_type = data.get("scopeType")
    pr_only = data.get("prOnlyMode")
    pr_preview = data.get("prMergePreview")
    merge_strategy = data.get("mergePreviewStrategy")
    add(results, isinstance(pr_only, bool), "prOnlyMode is boolean")
    add(results, isinstance(pr_preview, bool), "prMergePreview is boolean")
    add(results, merge_strategy in {"server-merge", "local-merge", "source-head"},
        "mergePreviewStrategy is valid (server-merge, local-merge, source-head)")
    if scope_type == "pr":
        add(results, merge_strategy in {"server-merge", "local-merge", "source-head"},
            "mergePreviewStrategy is valid for pr scope (server-merge, local-merge, source-head)")
    if pr_only:
        add(results, scope_type == "pr", "PR-only mode requires pr scopeType")
    add(results, data.get("jsDepsStrategy") in {"link", "skip", "install", "mixed", "none"},
        "jsDepsStrategy is valid (link, skip, install, mixed, none)")
    if data.get("jsDepsStrategy") in {"skip", "mixed"}:
        build = re.search(
            r"^## Build Status\s*(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        add(results, bool(build and re.search(
            r"^\|\s*`[^`]+`\s*\|\s*JS-SKIPPED(?:\s*\([^)|]*\))?\s*\|",
            build.group(1),
            re.MULTILINE,
        )), "Build Status table contains JS-SKIPPED row when jsDepsStrategy is skip/mixed")

    runtime = data.get("runtime")
    roles = ("main", "build", "requirement", "specialists")
    runtime_ok = isinstance(runtime, dict) and set(runtime) >= set(roles) and all(
        _is_string(runtime.get(role)) and bool(re.fullmatch(r".+ / .+", runtime[role]))
        for role in roles
    )
    add(results, runtime_ok, "sidecar runtime contains populated v3 child roles")
    runtime = runtime if isinstance(runtime, dict) else {}
    add(results, runtime.get("main") == values.get("Main Runtime"),
        "sidecar runtime.main matches report Main Runtime")


def _validate_branch_gate(text, data, runtime, triggered, skipped, results):
    gate_report = section_bullets(text, "## Branch Work Item Gate")
    gate = data.get("branchWorkItemGate")
    add(results, BRANCH_GATE_FIELDS <= set(gate_report),
        "Branch Work Item Gate reports required fields")
    add(results, isinstance(gate, dict) and BRANCH_GATE_SIDE_FIELDS <= set(gate),
        "sidecar branchWorkItemGate contains required fields")
    gate = gate if isinstance(gate, dict) else {}
    add(results, gate.get("status") in {"PASS", "WARN", "FAIL", "SKIPPED"},
        "Branch Work Item Gate status is valid")
    mapping = {
        "Status": "status", "Branch": "branch", "Prefix": "prefix",
        "Work Item ID": "workItemId", "Expected Type": "expectedType",
        "Actual Type": "actualType", "Title": "title", "State": "state",
        "Source": "source", "Reason": "reason",
    }
    add(results, all(str(gate_report.get(label)) == str(gate.get(key))
                     for label, key in mapping.items()),
        "Branch Work Item Gate report fields match sidecar")
    actor = f"Branch Work Item Gate({runtime.get('build')}; branch work item convention)"
    triggered_gate = _actor(triggered, "Branch Work Item Gate(")
    skipped_gate = _actor(skipped, "Branch Work Item Gate(")
    if gate.get("status") == "SKIPPED":
        add(results, not triggered_gate and len(skipped_gate) == 1,
            "Skipped Branch Work Item Gate is recorded only in skipped actors")
    else:
        add(results, triggered_gate == [actor] and not skipped_gate,
            "Branch Work Item Gate uses Build Validator runtime when triggered")


def _validate_actors(values, data, runtime, profile, repo_names,
                     specialist_triggers, results):
    triggered = data.get("triggered")
    skipped = data.get("skipped")
    add(results, _string_list(triggered), "sidecar triggered is a unique string list")
    add(results, _string_list(skipped), "sidecar skipped is a unique string list")
    triggered = triggered if isinstance(triggered, list) else []
    skipped = skipped if isinstance(skipped, list) else []
    add(results, triggered == records(values.get("Agents Triggered")),
        "Triggered report records match sidecar")
    add(results, skipped == records(values.get("Agents Skipped")),
        "Skipped report records match sidecar")

    build_records = _actor(triggered, "Build Validator[")
    expected_builds = [
        f"Build Validator[{repo}]({runtime.get('build')}; code build)"
        for repo in repo_names
    ]
    semantic = [
        item for item in triggered
        if item.startswith(("Main(", "Requirement Validator(",
                            "Security Reviewer(", "Performance Reviewer(",
                            "Philosophy Reviewer(", "Standard Reviewer("))
    ]
    if profile == "No-production-code":
        add(results, not semantic and not data.get("findings"),
            "no-production-code has no semantic findings or agents")
        add(results, not build_records, "No-production-code triggers no Build Validator")
    elif profile == "Tiny":
        gate = data.get("branchWorkItemGate")
        gate_failed = isinstance(gate, dict) and gate.get("status") == "FAIL"
        if gate_failed:
            add(results, not semantic and not build_records,
                "Branch Work Item Gate failure triggers no semantic actors or builds")
            add(results,
                _actor(skipped, "Main(")
                == ["Main(Tiny all-lens; branch work item gate failed)"],
                "Branch Work Item Gate failure skips Tiny main review")
            expected_skipped_builds = [
                f"Build Validator[{repo}](branch work item gate failed)"
                for repo in repo_names
            ]
            add(results,
                _actor(skipped, "Build Validator[") == expected_skipped_builds,
                "Branch Work Item Gate failure skips every Build Validator")
            for actor in (
                "Requirement Validator",
                *[f"{name} Reviewer" for name in SPECIALISTS],
            ):
                add(results,
                    _actor(skipped, f"{actor}(")
                    == [f"{actor}(branch work item gate failed)"],
                    f"Branch Work Item Gate failure skips {actor}")
        else:
            add(results, triggered.count("Main(Tiny all-lens)") == 1,
                "Tiny triggers main all-lens review")
            add(results, build_records == expected_builds,
                "Tiny triggers one Build Validator per repo")
            for actor in (
                "Requirement Validator",
                *[f"{name} Reviewer" for name in SPECIALISTS],
            ):
                add(results, not _actor(triggered, f"{actor}(")
                    and len(_actor(skipped, f"{actor}(")) == 1,
                    f"Tiny skips {actor} exactly once")
    elif profile == "Pro":
        gate = data.get("branchWorkItemGate")
        gate_failed = isinstance(gate, dict) and gate.get("status") == "FAIL"
        if gate_failed:
            add(results, not semantic and not build_records,
                "Branch Work Item Gate failure triggers no semantic actors or builds")
            expected_skipped_builds = [
                f"Build Validator[{repo}](branch work item gate failed)"
                for repo in repo_names
            ]
            add(results,
                _actor(skipped, "Build Validator[") == expected_skipped_builds,
                "Branch Work Item Gate failure skips every Build Validator")
            for actor in (
                "Requirement Validator",
                *[f"{name} Reviewer" for name in SPECIALISTS],
            ):
                add(results,
                    _actor(skipped, f"{actor}(")
                    == [f"{actor}(branch work item gate failed)"],
                    f"Branch Work Item Gate failure skips {actor}")
        else:
            add(results, not _actor(triggered, "Main("),
                "Pro does not use Tiny main actor")
            add(results, build_records == expected_builds,
                "Pro triggers one Build Validator per repo")
            expected_requirement = (
                f"Requirement Validator({runtime.get('requirement')}; "
                f"{data.get('requirementMode')})"
            )
            add(results, _actor(triggered, "Requirement Validator(") == [expected_requirement]
                and not _actor(skipped, "Requirement Validator("),
                "Pro triggers dedicated Requirement Validator")
            for name in SPECIALISTS:
                actor = f"{name} Reviewer"
                triggered_records = _actor(triggered, f"{actor}(")
                skipped_records = _actor(skipped, f"{actor}(")
                expected_triggers = specialist_triggers.get(actor, [])
                expected_records = [
                    f"{actor}({runtime.get('specialists')}; {trigger})"
                    for trigger in expected_triggers
                ]
                if expected_triggers:
                    add(results, triggered_records == expected_records and not skipped_records,
                        f"Pro triggers classified {actor} with child runtime")
                else:
                    add(results, not triggered_records and len(skipped_records) == 1,
                        f"Pro skips untriggered {actor}")
    return triggered, skipped


def _validate_findings(text, data, production, evidence, results):
    findings = data.get("findings")
    add(results, isinstance(findings, list), "findings is a list")
    findings = findings if isinstance(findings, list) else []
    finding_shape = all(
        isinstance(item, dict)
        and _is_string(item.get("file"))
        and item.get("file") in production
        and ("evidence" not in item or (
            _string_list(item.get("evidence"))
            and all(path in evidence for path in item["evidence"])
        ))
        for item in findings
    )
    add(results, finding_shape, "finding file is in scope productionFiles")
    report_findings = re.findall(
        r"^- (Must Fix|Should Fix|Consider): (.+):(\d+)\s+—",
        text,
        re.MULTILINE,
    )
    parity = len(report_findings) == len(findings)
    if parity:
        for report_finding, side_finding in zip(report_findings, findings):
            action, path, line = report_finding
            if path != side_finding.get("file"):
                parity = False
                break
            if side_finding.get("action") is not None and action != side_finding["action"]:
                parity = False
                break
            if side_finding.get("line") is not None and str(side_finding["line"]) != line:
                parity = False
                break
    add(results, parity, "Detailed Findings targets match sidecar production findings")
    blocking = data.get("blockingValidations")
    add(results, isinstance(blocking, list) and all(
        isinstance(item, dict) and _is_string(item.get("gate"))
        and _is_string(item.get("reason")) for item in blocking
    ), "blockingValidations contains non-file gate blockers")


def _validate_branch_gate_blocker(data, results):
    gate = data.get("branchWorkItemGate")
    if not isinstance(gate, dict) or gate.get("status") != "FAIL":
        return
    blocking = data.get("blockingValidations")
    expected = {
        "gate": "Branch Work Item Gate",
        "reason": gate.get("reason"),
    }
    add(results, isinstance(blocking, list) and expected in blocking,
        "Branch Work Item Gate failure records blocking validation")


def evaluate(report_path, sidecar_path=None):
    results = []
    report = Path(report_path)
    add(results, report.is_file(), f"report exists: {report}")
    if not report.is_file():
        return results

    try:
        text = report.read_text(encoding="utf-8")
    except OSError as exc:
        add(results, False, f"report is readable: {exc}")
        return results

    values = {}
    for name in ("Skill", "Review Profile", "Main Runtime", "Agents Triggered", "Agents Skipped"):
        value, error = field(text, name)
        add(results, error is None, error or f"{name} field appears exactly once")
        values[name] = value
    add(results, values.get("Skill") == SKILL, f"Skill is {SKILL}")
    add(results, values.get("Review Profile") in PROFILES, "Review Profile is valid")
    add(results, bool(re.fullmatch(r".+ / .+", values.get("Main Runtime") or "")),
        "Main Runtime exposes exact model and effort")
    add(results, values.get("Agents Triggered") is not None, "Agents Triggered is populated")
    add(results, values.get("Agents Skipped") is not None, "Agents Skipped is populated")
    for heading in REQUIRED_HEADINGS:
        add(results, text.count(heading) == 1, f"{heading} section exists")

    sidecar = Path(sidecar_path) if sidecar_path else infer_sidecar(report)
    add(results, sidecar.is_file(), f"sidecar exists: {sidecar}")
    if not sidecar.is_file():
        return results
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add(results, False, f"sidecar parses: {exc}")
        return results
    add(results, isinstance(data, dict), "sidecar is a JSON object")
    data = data if isinstance(data, dict) else {}

    add(results, data.get("recordVersion") == 3, "recordVersion is 3")
    add(results, data.get("skillName") == "code-review-pro", "skillName is code-review-pro")
    add(results, data.get("skillVersion") == "3.0.0", "skillVersion is 3.0.0")
    add(results, data.get("reviewProfile") == values.get("Review Profile"),
        "reviewProfile matches report")
    _validate_retained(text, values, data, results)

    runtime = _artifact(sidecar, data.get("runtimeAttestation"),
                        "runtimeAttestation", results)
    scope = _artifact(sidecar, data.get("scopeManifest"), "scopeManifest", results)
    tests = _artifact(sidecar, data.get("testEvidence"), "testEvidence", results)
    _validate_runtime(text, values, data, runtime, results)
    production, evidence, _ = _validate_scope(text, data, scope, results)
    repo_names, _ = _validate_tests(text, data, tests, evidence, production, results)
    _, specialist_triggers = _validate_classifier(
        text, values, data, scope, production, results,
    )

    runtime_roles = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    triggered, skipped = _validate_actors(
        values, data, runtime_roles, values.get("Review Profile"), repo_names,
        specialist_triggers, results,
    )
    _validate_branch_gate(text, data, runtime_roles, triggered, skipped, results)
    _validate_findings(text, data, production, evidence, results)
    _validate_branch_gate_blocker(data, results)

    gate = data.get("branchWorkItemGate")
    if isinstance(gate, dict) and gate.get("status") == "FAIL":
        semantic = [
            item for item in triggered
            if item.startswith(("Main(", "Requirement Validator(", "Security Reviewer(",
                                "Performance Reviewer(", "Philosophy Reviewer(",
                                "Standard Reviewer("))
        ]
        add(results, not semantic,
            "Branch Work Item Gate failure blocks later semantic dispatch")
    return results


def render(results, dry_run=False):
    heading = "=== OUTPUT CHECK: code-review-pro v3 ==="
    if dry_run:
        heading += " [DRY RUN]"
    lines = [heading]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    failures = sum(level == "FAIL" for level, _ in results)
    passes = sum(level == "PASS" for level, _ in results)
    lines.extend(["", f"Result: {failures} FAIL, {passes} PASS"])
    return "\n".join(lines), failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Path to .CodeReview report")
    parser.add_argument("--sidecar", help="Path to recordVersion 3 review sidecar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate read-only and label output")
    args = parser.parse_args(argv)
    output, failures = render(evaluate(args.report, args.sidecar), args.dry_run)
    print(output)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
