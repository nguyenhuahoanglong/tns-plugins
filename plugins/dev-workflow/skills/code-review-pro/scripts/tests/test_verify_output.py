import importlib.util
import hashlib
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def write_legacy_rejection_case(root, profile, classifier, triggered, requirement_mode, gate_status="PASS"):
    risk_text = " | ".join(classifier["riskTriggers"]) or "None"
    specialist_text = " | ".join(
        f"{reviewer}={trigger}"
        for reviewer, triggers in classifier["specialistTriggers"].items()
        for trigger in triggers
    ) or "None"
    runtime = {
        "main": "gpt-5.6-sol / xhigh",
        "build": "gpt-5.6-luna / low",
        "requirement": "gpt-5.6-sol / high",
        "specialists": "gpt-5.6-terra / medium",
    }
    gate = {
        "status": gate_status,
        "branch": "US/123-valid-branch" if gate_status != "SKIPPED" else "None",
        "prefix": "US" if gate_status != "SKIPPED" else "None",
        "workItemId": "123" if gate_status != "SKIPPED" else "None",
        "expectedType": "User Story" if gate_status != "SKIPPED" else "None",
        "actualType": "User Story" if gate_status == "PASS" else "None",
        "title": "Valid story" if gate_status == "PASS" else "None",
        "state": "Active" if gate_status == "PASS" else "None",
        "source": "branch" if gate_status != "SKIPPED" else "working",
        "reason": "Branch prefix and ADO work item type match"
        if gate_status == "PASS"
        else ("Scope has no created PR or branch to validate"
              if gate_status == "SKIPPED"
              else "ADO work item type does not match branch prefix"),
    }
    if gate_status == "WARN":
        gate.update({
            "branch": "hotfix/123",
            "prefix": "hotfix",
            "workItemId": "123",
            "expectedType": "None",
            "actualType": "User Story",
            "title": "Valid story",
            "state": "Active",
            "reason": "Branch prefix is not US, BUG, or ISSUE; ADO work item ID is valid",
        })
    gate_trigger = f"Branch Work Item Gate({runtime['build']}; branch work item convention)"
    triggered_records = list(triggered)
    skipped_records = list(SKIPPED[profile])
    if gate_status == "SKIPPED":
        skipped_records.append("Branch Work Item Gate(no created PR or branch scope)")
    else:
        triggered_records.insert(0, gate_trigger)
    report = root / "feature.md"
    report.write_text(
        "\n".join([
            "# Code Review: Test",
            "",
            "**Skill**: code-review-pro v2.2.0",
            f"**Review Profile**: {profile}",
            "**Main Runtime**: gpt-5.6-sol / xhigh",
            "**Agents Triggered**: None" if not triggered_records else f"**Agents Triggered**: {' | '.join(triggered_records)}",
            f"**Agents Skipped**: {' | '.join(skipped_records) if skipped_records else 'None'}",
            "",
            "## Review Classification",
            f"- **Files Changed**: {classifier['filesChanged']}",
            f"- **Changed Lines**: {classifier['changedLines']}",
            f"- **Docs Only**: {str(classifier['docsOnly']).lower()}",
            f"- **Risk Triggers**: {risk_text}",
            "- **Risk Evidence**: None",
            f"- **Specialist Triggers**: {specialist_text}",
            "## Branch Work Item Gate",
            f"- **Status**: {gate['status']}",
            f"- **Branch**: {gate['branch']}",
            f"- **Prefix**: {gate['prefix']}",
            f"- **Work Item ID**: {gate['workItemId']}",
            f"- **Expected Type**: {gate['expectedType']}",
            f"- **Actual Type**: {gate['actualType']}",
            f"- **Title**: {gate['title']}",
            f"- **State**: {gate['state']}",
            f"- **Source**: {gate['source']}",
            f"- **Reason**: {gate['reason']}",
            "## Build Status",
            "Test.",
            "## Requirement Validation",
            "Test.",
            "### Scope Drift",
            "- **Scope Drift**: None",
            "## Summary",
            "Test.",
            "## Detailed Findings",
            "Test.",
        ]),
        encoding="utf-8",
    )
    sidecar = root / ".feature.review-meta.json"
    sidecar.write_text(json.dumps({
        "recordVersion": 2,
        "skillName": "code-review-pro",
        "skillVersion": "2.2.0",
        "reviewProfile": profile,
        "reviewKind": "initial",
        "classifier": classifier,
        "branchWorkItemGate": gate,
        "runtime": runtime,
        "triggered": triggered_records,
        "skipped": skipped_records,
        "reposReviewed": [] if profile == "Docs-only" else ["repo"],
        "requirementMode": requirement_mode,
        "scopeType": "branch",
        "scopeBase": "origin/main",
        "diffFingerprint": "sha256:abc123",
        "reviewedCommit": "abc123",
        "targetBranch": "main",
        "workItemId": 123 if requirement_mode == "work-item" else None,
        "prOnlyMode": False,
        "prMergePreview": False,
        "mergePreviewStrategy": "source-head",
        "jsDepsStrategy": "none",
        "standardsPaths": ["AGENTS.md"],
        "exemplarMap": {},
        "reviewedFiles": ["src/file.py"],
        "iteration": 1,
        "reviewedAt": "2026-06-19T00:00:00Z",
    }), encoding="utf-8")
    return report, sidecar


ALL_CHILDREN = [
    "Build Validator(docs-only)",
    "Requirement Validator(docs-only)",
    "Security Reviewer(docs-only)",
    "Performance Reviewer(docs-only)",
    "Philosophy Reviewer(docs-only)",
    "Standard Reviewer(docs-only)",
]
TINY_SKIPS = [
    "Requirement Validator(Tiny)",
    "Security Reviewer(Tiny)",
    "Performance Reviewer(Tiny)",
    "Philosophy Reviewer(Tiny)",
    "Standard Reviewer(Tiny)",
]
SKIPPED = {
    "Tiny": TINY_SKIPS,
    "Pro": [
        "Performance Reviewer(no performance trigger)",
        "Philosophy Reviewer(no design trigger)",
        "Standard Reviewer(no standards trigger)",
    ],
}


def _set_report_field(report, name, value):
    text = report.read_text(encoding="utf-8")
    text = re.sub(rf"^\*\*{re.escape(name)}\*\*: .+$", f"**{name}**: {value}", text, flags=re.MULTILINE)
    report.write_text(text, encoding="utf-8")


def _set_report_section_bullet(report, heading, name, value):
    text = report.read_text(encoding="utf-8")
    section = re.search(rf"^{re.escape(heading)}\s*(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert section, heading
    body = re.sub(
        rf"^- \*\*{re.escape(name)}\*\*: .+$",
        f"- **{name}**: {value}",
        section.group(1),
        flags=re.MULTILINE,
    )
    report.write_text(text[:section.start(1)] + body + text[section.end(1):], encoding="utf-8")


def _configure_v3_branch_gate(report, sidecar, status):
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    runtime = data["runtime"]["build"]
    gate = {
        "status": status,
        "branch": "hotfix/123",
        "prefix": "hotfix",
        "workItemId": "123",
        "expectedType": "None",
        "actualType": "User Story",
        "title": "Valid story",
        "state": "Active",
        "source": "branch",
        "reason": "Branch prefix is not US, BUG, or ISSUE; ADO work item ID is valid",
    }
    branch_actor = f"Branch Work Item Gate({runtime}; branch work item convention)"
    data["branchWorkItemGate"] = gate
    data["triggered"] = [branch_actor, *[item for item in data["triggered"] if not item.startswith("Branch Work Item Gate(")]]
    data["skipped"] = [item for item in data["skipped"] if not item.startswith("Branch Work Item Gate(")]
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _set_report_field(report, "Agents Triggered", " | ".join(data["triggered"]) or "None")
    _set_report_field(report, "Agents Skipped", " | ".join(data["skipped"]) or "None")
    mapping = {
        "Status": "status", "Branch": "branch", "Prefix": "prefix", "Work Item ID": "workItemId",
        "Expected Type": "expectedType", "Actual Type": "actualType", "Title": "title", "State": "state",
        "Source": "source", "Reason": "reason",
    }
    for label, key in mapping.items():
        _set_report_section_bullet(report, "## Branch Work Item Gate", label, gate[key])


class VerifyOutputTests(unittest.TestCase):
    def test_no_production_code_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="No-production-code")
            self.assertFalse(_v3_failures(report, sidecar))

    def test_tiny_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Tiny")
            self.assertFalse(_v3_failures(report, sidecar))

    def test_no_production_code_rejects_semantic_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="No-production-code")
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["triggered"] = ["Security Reviewer(gpt-5.6-terra / medium; semantic review)"]
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            _set_report_field(report, "Agents Triggered", data["triggered"][0])
            self.assertIn("no-production-code has no semantic findings or agents", _v3_failures(report, sidecar))

    def test_pro_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            self.assertFalse(_v3_failures(report, sidecar))

    def test_main_runtime_is_bound_to_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp))
            _set_report_field(report, "Main Runtime", "gpt-5.6-sol / high")
            self.assertIn("Main Runtime matches attested modelId / effort", _v3_failures(report, sidecar))

    def test_branch_gate_skipped_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp))
            self.assertFalse(_v3_failures(report, sidecar))

    def test_branch_gate_warn_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp))
            _configure_v3_branch_gate(report, sidecar, "WARN")
            self.assertFalse(_v3_failures(report, sidecar))

    def test_branch_gate_report_sidecar_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp))
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["branchWorkItemGate"]["status"] = "FAIL"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("Branch Work Item Gate report fields match sidecar", _v3_failures(report, sidecar))

    def test_branch_gate_requires_build_runtime_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp))
            _configure_v3_branch_gate(report, sidecar, "WARN")
            text = report.read_text(encoding="utf-8").replace(
                "Branch Work Item Gate(gpt-5.6-luna / low; branch work item convention)",
                "Branch Work Item Gate(gpt-other / low; branch work item convention)",
            )
            report.write_text(text, encoding="utf-8")
            self.assertIn("Triggered report records match sidecar", _v3_failures(report, sidecar))

    def test_pro_requires_requirement_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, requirementMode="inline")
            self.assertTrue(any("requirement mode" in message for message in _v3_failures(report, sidecar)))

    def test_tiny_rejects_risk_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Tiny")
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["classifier"]["riskTriggers"] = ["auth-security-boundary"]
            data["classifier"]["specialistTriggers"] = {"Security Reviewer": ["auth-security-boundary"]}
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            _set_report_section_bullet(report, "## Review Classification", "Risk Triggers", "auth-security-boundary")
            _set_report_section_bullet(report, "## Review Classification", "Specialist Triggers", "Security Reviewer=auth-security-boundary")
            self.assertTrue(any("Tiny" in message for message in _v3_failures(report, sidecar)))


    def test_pr_merge_preview_strategy_valid(self):
        """pr scope with valid mergePreviewStrategy → no failures."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, scopeType="pr", mergePreviewStrategy="server-merge")
            self.assertFalse(_v3_failures(report, sidecar))

    def test_pr_requires_merge_preview_strategy(self):
        """pr scope with missing/invalid mergePreviewStrategy → FAIL mentioning mergePreviewStrategy."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, scopeType="pr", mergePreviewStrategy="invalid-value")
            self.assertTrue(any("mergePreviewStrategy" in message for message in _v3_failures(report, sidecar)))

    def test_pr_only_requires_pr_scope(self):
        """prOnlyMode=true with scopeType=branch → FAIL mentioning PR-only."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, prOnlyMode=True, scopeType="branch")
            self.assertTrue(any("PR-only" in message for message in _v3_failures(report, sidecar)))

    def test_js_deps_skip_requires_build_row(self):
        """jsDepsStrategy=skip with no JS-SKIPPED build row → FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, jsDepsStrategy="skip")
            self.assertTrue(any("JS-SKIPPED" in message for message in _v3_failures(report, sidecar)))

    def test_js_deps_skip_accepts_parenthesized_reason_row(self):
        """JS-SKIPPED (reason) build row satisfies the skip/mixed requirement."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, jsDepsStrategy="skip")
            text = report.read_text(encoding="utf-8")
            text = text.replace(
                "## Build Status\nPASS.",
                "## Build Status\n| `repo` | JS-SKIPPED (no lockfile) |",
            )
            report.write_text(text, encoding="utf-8")
            self.assertFalse(any("JS-SKIPPED" in message for message in _v3_failures(report, sidecar)))

    def test_js_deps_install_is_valid(self):
        """jsDepsStrategy=install is accepted (no JS-SKIPPED row required)."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            _update_sidecar(sidecar, jsDepsStrategy="install")
            self.assertFalse(any("jsDepsStrategy" in message for message in _v3_failures(report, sidecar)))

    def test_scope_drift_required_for_pro(self):
        """Pro report missing Scope Drift marker → FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_strict_v3_case(Path(tmp), profile="Pro")
            text = report.read_text(encoding="utf-8")
            text = re.sub(r"### Scope Drift\s*", "", text)
            text = re.sub(r"- \*\*Scope Drift\*\*: None\s*", "", text)
            report.write_text(text, encoding="utf-8")
            self.assertTrue(any("Scope Drift" in message for message in _v3_failures(report, sidecar)))


# Task 2 spec-first registry: TC-201 through TC-210.
# Design: .plans/code-review-runtime-scope-test-harness.md, Task 2 DoD-2.2 through DoD-2.4.


def _write_json_with_sha256(root, name, payload):
    """Write one deterministic evidence artifact and return its v3 reference."""
    root.mkdir(parents=True, exist_ok=True)
    artifact = root / name
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return {
        "path": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }


def write_v3_case(tmp_path, *, profile="Tiny", findings=None, agents=None,
                  runtime_status="pass", session_status="fresh",
                  override_recorded=False, direct_tests=None,
                  advisory=None, execution_status="pass"):
    """Create an independently hash-bound v3 report package using real files."""
    # Arrange
    findings = findings or []
    agents = agents or ["Main(Tiny all-lens)"]
    direct_tests = ["tests/test_service.py"] if direct_tests is None else direct_tests
    runtime = {
        "status": runtime_status,
        "host": "codex",
        "sessionId": "019f8275-2355-7861-9f3d-f668f099b611",
        "modelId": "gpt-5.6-terra",
        "effort": "medium",
        "thinkingEnabled": True,
        "source": "codex-rollout",
        "crossChecks": ["threadId", "latest-turn-context"],
        "freshness": "current",
        "sessionStatus": session_status,
        "overrideRecorded": override_recorded,
    }
    scope = {
        "status": "no-production-code" if profile == "No-production-code" else "pass",
        "files": [
            {"path": "src/service.py", "classification": "production", "reasonCode": "production_code"},
            {"path": "tests/test_service.py", "classification": "evidence", "reasonCode": "test_file"},
            {"path": "docs/design.md", "classification": "evidence", "reasonCode": "documentation"},
            {"path": "dist/bundle.js", "classification": "excluded", "reasonCode": "generated_output"},
            {"path": "vendor/lib.js", "classification": "excluded", "reasonCode": "vendor_code"},
            {"path": "assets/logo.png", "classification": "excluded", "reasonCode": "binary_file"},
        ],
        "productionFiles": [] if profile == "No-production-code" else ["src/service.py"],
        "evidenceFiles": ["tests/test_service.py", "docs/design.md"],
        "excludedFiles": ["dist/bundle.js", "vendor/lib.js", "assets/logo.png"],
    }
    test_evidence = {
        "discovery": {
            "status": "advisory" if advisory else "pass",
            "advisory": advisory,
            "changedSymbols": ["Service.run"],
            "directTests": direct_tests,
            "affectedTests": [],
        },
        "execution": {
            "status": execution_status,
            "command": ["python", "-m", "pytest", "tests/test_service.py"],
            "exitCode": 0 if execution_status == "pass" else 1,
            "durationMs": 12,
            "counts": {"passed": 1 if execution_status == "pass" else 0, "failed": 0 if execution_status == "pass" else 1, "skipped": 0},
            "stdout": "1 passed" if execution_status == "pass" else "1 failed",
            "stderr": "",
            "logsTruncated": False,
        },
    }
    references = {
        "runtimeAttestation": _write_json_with_sha256(tmp_path, "runtime-attestation.json", runtime),
        "scopeManifest": _write_json_with_sha256(tmp_path, "scope-manifest.json", scope),
        "testEvidence": _write_json_with_sha256(tmp_path, "test-evidence.json", test_evidence),
    }
    report = tmp_path / "feature.md"
    main_runtime = f"{runtime['modelId']} / {runtime['effort']}"
    advisory_line = "" if not advisory else "\n- Advisory: use-unit-testing"
    report.write_text(
        "\n".join([
            "# Code Review: v3 contract",
            "",
            "**Skill**: code-review-pro v3.0.0",
            f"**Review Profile**: {profile}",
            f"**Main Runtime**: {main_runtime}",
            f"**Agents Triggered**: {' | '.join(agents) if agents else 'None'}",
            "**Agents Skipped**: None",
            "",
            "## Review Classification",
            "- **Files Changed**: 1",
            "- **Changed Lines**: 1",
            f"- **Scope Status**: {'no-production-code' if profile == 'No-production-code' else 'pass'}",
            "- **Risk Triggers**: None",
            "- **Risk Evidence**: None",
            "- **Specialist Triggers**: None",
            "## Branch Work Item Gate",
            "- **Status**: SKIPPED",
            "- **Branch**: None",
            "- **Prefix**: None",
            "- **Work Item ID**: None",
            "- **Expected Type**: None",
            "- **Actual Type**: None",
            "- **Title**: None",
            "- **State**: None",
            "- **Source**: working",
            "- **Reason**: Scope has no created PR or branch to validate",
            "## Build Status",
            "Not required for the verifier contract fixture.",
            "## Requirement Validation",
            "Not required for the verifier contract fixture.",
            "### Scope Drift",
            "- **Scope Drift**: None",
            "## Summary",
            "v3 contract fixture.",
            "## Detailed Findings",
            *[f"- Must Fix: {item['file']}:1 — contract finding" for item in findings],
            advisory_line,
        ]),
        encoding="utf-8",
    )
    sidecar = tmp_path / ".feature.review-meta.json"
    sidecar.write_text(json.dumps({
        "recordVersion": 3,
        "skillName": "code-review-pro",
        "skillVersion": "3.0.0",
        "reviewProfile": profile,
        "runtimeAttestation": references["runtimeAttestation"],
        "scopeManifest": references["scopeManifest"],
        "testEvidence": references["testEvidence"],
        "runtime": {
            "main": main_runtime,
            "build": "gpt-5.6-luna / low",
            "requirement": "gpt-5.6-sol / high",
            "specialists": "gpt-5.6-terra / medium",
        },
        "session": {"status": session_status, "overrideRecorded": override_recorded},
        "productionFiles": scope["productionFiles"],
        "evidenceFiles": scope["evidenceFiles"],
        "excludedFiles": scope["excludedFiles"],
        "reviewedFiles": scope["productionFiles"],
        "findings": findings,
        "triggered": agents,
        # Retained v2 provenance values ensure a red test isolates the v3 contract.
        "reviewKind": "initial",
        "classifier": {"filesChanged": 1, "changedLines": 1, "scopeStatus": "no-production-code" if profile == "No-production-code" else "pass", "riskTriggers": [], "specialistTriggers": {}},
        "branchWorkItemGate": {"status": "SKIPPED", "branch": "None", "prefix": "None", "workItemId": "None", "expectedType": "None", "actualType": "None", "title": "None", "state": "None", "source": "working", "reason": "Scope has no created PR or branch to validate"},
        "reposReviewed": ["repo"],
        "requirementMode": "inline",
        "scopeType": "branch",
        "scopeBase": "origin/main",
        "diffFingerprint": "sha256:abc123",
        "reviewedCommit": "abc123",
        "targetBranch": "main",
        "workItemId": None,
        "prOnlyMode": False,
        "prMergePreview": False,
        "mergePreviewStrategy": "source-head",
        "jsDepsStrategy": "none",
        "standardsPaths": ["AGENTS.md"],
        "exemplarMap": {},
        "skipped": ["Branch Work Item Gate(no created PR or branch scope)"],
        "iteration": 1,
        "reviewedAt": "2026-07-21T00:00:00Z",
    }), encoding="utf-8")
    return report, sidecar, references


def _v3_failures(report, sidecar):
    return [message for level, message in VERIFY.evaluate(report, sidecar) if level == "FAIL"]


def _assert_v3_contract_failure(report, sidecar, phrase):
    assert any(phrase in message for message in _v3_failures(report, sidecar)), phrase


def test_tc_201_dod_23_accepts_hash_bound_v3_runtime_scope_and_test_evidence(tmp_path):
    """TC-201: accept a complete trusted v3 review package.

    Steps: 1. Create runtime, scope, and test evidence. 2. Bind each artifact by SHA-256.
    3. Verify the v3 report package is accepted. Design: Task 2 DoD-2.3/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("artifact_key, mutation", [
    ("runtimeAttestation", "missing"),
    ("scopeManifest", "tampered"),
    ("testEvidence", "bad-hash"),
])
def test_tc_202_dod_24_rejects_missing_or_untrusted_evidence_artifact(tmp_path, artifact_key, mutation):
    """TC-202: reject missing, changed, or incorrectly hashed evidence.

    Steps: 1. Create a valid package. 2. Break one referenced artifact or hash. 3. Verify rejection.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar, refs = write_v3_case(tmp_path)
    reference = refs[artifact_key]
    artifact = tmp_path / reference["path"]
    if mutation == "missing":
        artifact.unlink()
    elif mutation == "tampered":
        artifact.write_text('{"tampered":true}', encoding="utf-8")
    else:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data[artifact_key]["sha256"] = "0" * 64
        sidecar.write_text(json.dumps(data), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, artifact_key)


@pytest.mark.parametrize("runtime_status", ["blocked", "confirmation-required"])
def test_tc_203_dod_24_rejects_nonpassing_runtime_or_session_preflight(tmp_path, runtime_status):
    """TC-203: block reviews whose trusted preflight did not pass.

    Steps: 1. Create an attestation below policy or confirmation-required. 2. Verify rejection.
    Design: Task 2 DoD-2.1/DoD-2.4.
    """
    report, sidecar, _ = write_v3_case(tmp_path, runtime_status=runtime_status)
    _assert_v3_contract_failure(report, sidecar, "runtime attestation status is pass")


def test_tc_204_dod_23_requires_existing_session_override_and_accepts_recorded_override(tmp_path):
    """TC-204: require an override for existing sessions and honor a recorded override.

    Steps: 1. Create an existing-session package without override. 2. Verify rejection. 3. Record override and verify acceptance.
    Design: Task 2 DoD-2.3.
    """
    report, sidecar = write_strict_v3_case(
        tmp_path, session_status="existing", override_recorded=False,
    )
    _assert_v3_contract_failure(report, sidecar, "existing session requires recorded override")
    report, sidecar = write_strict_v3_case(
        tmp_path / "override", session_status="existing", override_recorded=True,
    )
    assert not _v3_failures(report, sidecar)


def test_tc_205_dod_24_uses_attested_runtime_not_optional_launch_argument(tmp_path):
    """TC-205: bind Main Runtime exactly to the attested model and effort.

    Steps: 1. Create a valid attestation. 2. Change the report runtime. 3. Verify attestation mismatch is rejected without a launch argument.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar, _ = write_v3_case(tmp_path)
    report.write_text(report.read_text(encoding="utf-8").replace("gpt-5.6-terra / medium", "gpt-5.6-sol / high"), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, "Main Runtime matches attested modelId / effort")


def test_tc_206_dod_22_validates_scope_lists_and_reviewed_production_allowlist(tmp_path):
    """TC-206: ensure report scope lists are complete and reviewed files are production-only.

    Steps: 1. Create scope evidence. 2. Drift reviewed files from production files. 3. Verify rejection.
    Design: Task 2 DoD-2.2/DoD-2.4.
    """
    report, sidecar, _ = write_v3_case(tmp_path)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["reviewedFiles"] = ["tests/test_service.py"]
    data["excludedFiles"] = []
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, "reviewedFiles exactly match scope productionFiles")


def test_tc_207_dod_22_rejects_semantic_agents_or_findings_for_no_production_code(tmp_path):
    """TC-207: no-production-code reviews must not emit semantic review work.

    Steps: 1. Create an evidence-only scope. 2. Add a semantic agent and finding. 3. Verify rejection.
    Design: Task 2 DoD-2.2.
    """
    report, sidecar, _ = write_v3_case(
        tmp_path, profile="No-production-code", findings=[{"file": "tests/test_service.py"}],
        agents=["Security Reviewer(gpt-5.6-terra / medium; auth-security-boundary)"],
    )
    _assert_v3_contract_failure(report, sidecar, "no-production-code has no semantic findings or agents")


@pytest.mark.parametrize("path", ["tests/test_service.py", "docs/design.md", "dist/bundle.js", "vendor/lib.js", "assets/logo.png"])
def test_tc_208_dod_22_rejects_findings_against_evidence_or_excluded_files(tmp_path, path):
    """TC-208: findings may target only a production file; citations may name evidence.

    Steps: 1. Create a finding against a non-production file. 2. Verify rejection. Design: Task 2 DoD-2.2.
    """
    report, sidecar, _ = write_v3_case(tmp_path, findings=[{"file": path, "evidence": ["tests/test_service.py"]}])
    _assert_v3_contract_failure(report, sidecar, "finding file is in scope productionFiles")


def test_tc_209_dod_22_accepts_production_finding_with_evidence_citation(tmp_path):
    """TC-209: allow a production finding that cites a test as supporting evidence.

    Steps: 1. Create a production finding with test evidence. 2. Verify acceptance. Design: Task 2 DoD-2.2.
    """
    report, sidecar = write_strict_v3_case(
        tmp_path, findings=[{"file": "src/service.py", "evidence": ["tests/test_service.py"]}],
    )
    assert not _v3_failures(report, sidecar)


def test_tc_210_dod_23_requires_exact_advisory_accepts_routed_failure_and_rejects_malformed_evidence(tmp_path):
    """TC-210: missing tests are advisory, routed failures are reportable, and malformed evidence is rejected.

    Steps: 1. Verify missing direct tests use only an advisory. 2. Verify a routed failing run is accepted as blocking evidence.
    3. Verify malformed test evidence is rejected.
    Design: Task 2 DoD-2.3/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(
        tmp_path, direct_tests=[], advisory="use-unit-testing",
    )
    assert "Must Fix" not in report.read_text(encoding="utf-8")
    assert not _v3_failures(report, sidecar)
    report, sidecar = write_strict_v3_case(tmp_path / "failing", run_statuses=("fail",))
    assert not _v3_failures(report, sidecar)
    report, sidecar, refs = write_v3_case(tmp_path / "malformed")
    (tmp_path / "malformed" / refs["testEvidence"]["path"]).write_text("not json", encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, "testEvidence")


# Strict Task 2 regression registry: TC-211 through TC-223.
# These cases extend, and do not replace, TC-201 through TC-210 above.


def _rewrite_bound_artifact(root, sidecar, key, payload):
    """Rewrite one referenced artifact and keep its sidecar digest authoritative."""
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    reference = data[key]
    artifact = root / reference["path"]
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    data[key]["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    return artifact


def _read_bound_artifact(root, sidecar, key):
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    return json.loads((root / data[key]["path"]).read_text(encoding="utf-8"))


def write_strict_v3_case(tmp_path, *, profile="Tiny", run_statuses=("pass",),
                         direct_tests=None, advisory=None, findings=None,
                         blocking_validations=None, session_status="fresh",
                         override_recorded=False):
    """Create a complete v3 package including retained provenance and multi-run evidence."""
    # Arrange
    findings = [] if findings is None else findings
    blocking_validations = [] if blocking_validations is None else blocking_validations
    direct_tests = ["tests/test_service.py"] if direct_tests is None else direct_tests
    repo_names = ["repo" if index == 1 else f"repo-{index}" for index, _ in enumerate(run_statuses, start=1)]
    if profile == "No-production-code":
        agents = []
        skipped = ALL_CHILDREN + ["Branch Work Item Gate(no created PR or branch scope)"]
        production_files = []
        risk_triggers = []
        specialist_triggers = {}
    elif profile == "Pro":
        agents = [
            *[f"Build Validator[{repo}](gpt-5.6-luna / low; code build)" for repo in repo_names],
            "Requirement Validator(gpt-5.6-sol / high; work-item)",
            "Security Reviewer(gpt-5.6-terra / medium; auth-security-boundary)",
        ]
        skipped = [
            "Performance Reviewer(no performance trigger)",
            "Philosophy Reviewer(no design trigger)",
            "Standard Reviewer(no standards trigger)",
            "Branch Work Item Gate(no created PR or branch scope)",
        ]
        production_files = ["src/service.py"]
        risk_triggers = ["auth-security-boundary"]
        specialist_triggers = {"Security Reviewer": ["auth-security-boundary"]}
    else:
        agents = [
            "Main(Tiny all-lens)",
            *[f"Build Validator[{repo}](gpt-5.6-luna / low; code build)" for repo in repo_names],
        ]
        skipped = TINY_SKIPS + ["Branch Work Item Gate(no created PR or branch scope)"]
        production_files = ["src/service.py"]
        risk_triggers = []
        specialist_triggers = {}

    report, sidecar, _ = write_v3_case(
        tmp_path, profile=profile, findings=findings, agents=agents,
        direct_tests=direct_tests, advisory=advisory,
        session_status=session_status, override_recorded=override_recorded,
    )
    scope_files = [
        *([{"path": "src/service.py", "classification": "production", "reasonCode": "production_code"}]
          if production_files else []),
        {"path": "tests/test_service.py", "classification": "evidence", "reasonCode": "test_file"},
        {"path": "dist/bundle.js", "classification": "excluded", "reasonCode": "generated_output"},
    ]
    scope = {
        "status": "no-production-code" if not production_files else "pass",
        "files": scope_files,
        "productionFiles": production_files,
        "evidenceFiles": ["tests/test_service.py"],
        "excludedFiles": ["dist/bundle.js"],
    }
    executions = []
    for index, status in enumerate(() if profile == "No-production-code" else run_statuses, start=1):
        repo = repo_names[index - 1]
        exit_code = 0 if status == "pass" else 124 if status == "timeout" else 1
        executions.append({
            "repo": repo,
            "status": status,
            "command": ["python", "-m", "pytest", f"tests/{repo}"],
            "exitCode": exit_code,
            "durationMs": 10 * index,
            "counts": {
                "passed": 1 if status == "pass" else 0,
                "failed": 1 if status == "fail" else 0,
                "skipped": 0,
            },
            "stdout": "1 passed" if status == "pass" else "1 failed" if status == "fail" else "",
            "stderr": "command timed out" if status == "timeout" else "",
            "logsTruncated": False,
        })
    overall = (
        "not-applicable" if profile == "No-production-code"
        else "pass" if all(run["status"] == "pass" for run in executions)
        else "blocked"
    )
    tests = {
        "status": overall,
        "discovery": {
            "status": "not-applicable" if profile == "No-production-code" else "advisory" if advisory else "pass",
            "advisory": advisory,
            "changedSymbols": [] if profile == "No-production-code" else ["Service.run"],
            "directTests": [] if profile == "No-production-code" else direct_tests,
            "affectedTests": [],
        },
        "executions": executions,
    }
    _rewrite_bound_artifact(tmp_path, sidecar, "scopeManifest", scope)
    _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)

    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data.update({
        "classifier": {
            "filesChanged": len(scope_files),
            "changedLines": 20,
            "scopeStatus": scope["status"],
            "riskTriggers": risk_triggers,
            "specialistTriggers": specialist_triggers,
        },
        "productionFiles": scope["productionFiles"],
        "evidenceFiles": scope["evidenceFiles"],
        "excludedFiles": scope["excludedFiles"],
        "reviewedFiles": scope["productionFiles"],
        "triggered": agents,
        "skipped": skipped,
        "reposReviewed": [] if not production_files else [run["repo"] for run in executions],
        "requirementMode": "work-item" if profile == "Pro" else "not-applicable" if not production_files else "inline",
        "workItemId": 123 if profile == "Pro" else None,
        "testGate": {
            "status": "NOT-APPLICABLE" if overall == "not-applicable" else "PASS" if overall == "pass" else "BLOCKED",
            "blocking": overall == "blocked",
        },
        "blockingValidations": blocking_validations,
    })
    sidecar.write_text(json.dumps(data), encoding="utf-8")

    risk_text = " | ".join(risk_triggers) or "None"
    specialist_text = " | ".join(
        f"{reviewer}={trigger}"
        for reviewer, triggers in specialist_triggers.items()
        for trigger in triggers
    ) or "None"
    must_fix = [
        *[f"- Must Fix: {item['file']}:1 — contract finding" for item in findings],
        *[f"- Must Fix: {item['gate']} — {item['reason']}" for item in blocking_validations],
    ] or ["None."]
    report.write_text("\n".join([
        "# Code Review: strict v3 contract",
        "",
        "**Skill**: code-review-pro v3.0.0",
        f"**Review Profile**: {profile}",
        "**Main Runtime**: gpt-5.6-terra / medium",
        f"**Agents Triggered**: {' | '.join(agents) if agents else 'None'}",
        f"**Agents Skipped**: {' | '.join(skipped) if skipped else 'None'}",
        "",
        "## Runtime Evidence",
        "- **Status**: PASS",
        "## Scope Evidence",
        f"- **Status**: {scope['status']}",
        "## Test Evidence",
        f"- **Status**: {'NOT-APPLICABLE' if overall == 'not-applicable' else 'PASS' if overall == 'pass' else 'BLOCKED'}",
        f"- **Advisory**: {advisory or 'None'}",
        "## Review Classification",
        f"- **Files Changed**: {len(scope_files)}",
        "- **Changed Lines**: 20",
        f"- **Scope Status**: {scope['status']}",
        f"- **Risk Triggers**: {risk_text}",
        "- **Risk Evidence**: None",
        f"- **Specialist Triggers**: {specialist_text}",
        "## Branch Work Item Gate",
        "- **Status**: SKIPPED",
        "- **Branch**: None",
        "- **Prefix**: None",
        "- **Work Item ID**: None",
        "- **Expected Type**: None",
        "- **Actual Type**: None",
        "- **Title**: None",
        "- **State**: None",
        "- **Source**: working",
        "- **Reason**: Scope has no created PR or branch to validate",
        "## Build Status",
        "PASS.",
        "## Semantic Review",
        "Production allowlist reviewed." if production_files else "Not run: no production code.",
        "## Requirement Validation",
        "Validated." if production_files else "Not applicable.",
        "### Scope Drift",
        "- **Scope Drift**: None",
        "## Summary",
        "Strict v3 package.",
        "## Detailed Findings",
        *must_fix,
    ]), encoding="utf-8")
    return report, sidecar


def _configure_strict_v3_branch_gate_stop(report, sidecar, *, profile="Pro"):
    """Model a review stopped by a failing branch/work-item gate before dispatch."""
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    runtime = data["runtime"]
    gate = {
        "status": "FAIL",
        "branch": "US/123-invalid-type",
        "prefix": "US",
        "workItemId": "123",
        "expectedType": "User Story",
        "actualType": "Task",
        "title": "Invalid task branch",
        "state": "Active",
        "source": "branch",
        "reason": "ADO work item type does not match branch prefix",
    }
    reason = "branch work item gate failed"
    repos = data["reposReviewed"]
    gate_actor = f"Branch Work Item Gate({runtime['build']}; branch work item convention)"
    data["branchWorkItemGate"] = gate
    data["triggered"] = [gate_actor]
    data["skipped"] = [
        *([f"Main(Tiny all-lens; {reason})"] if profile == "Tiny" else []),
        *[f"Build Validator[{repo}]({reason})" for repo in repos],
        f"Requirement Validator({reason})",
        *[f"{name} Reviewer({reason})" for name in ("Security", "Performance", "Philosophy", "Standard")],
    ]
    data["blockingValidations"] = [{
        "gate": "Branch Work Item Gate",
        "reason": gate["reason"],
    }]
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _set_report_field(report, "Agents Triggered", " | ".join(data["triggered"]))
    _set_report_field(report, "Agents Skipped", " | ".join(data["skipped"]))
    for label, key in {
        "Status": "status", "Branch": "branch", "Prefix": "prefix", "Work Item ID": "workItemId",
        "Expected Type": "expectedType", "Actual Type": "actualType", "Title": "title", "State": "state",
        "Source": "source", "Reason": "reason",
    }.items():
        _set_report_section_bullet(report, "## Branch Work Item Gate", label, gate[key])
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "None.\n", f"- Must Fix: Branch Work Item Gate — {gate['reason']}\n",
        ),
        encoding="utf-8",
    )


def test_tc_224_no_production_code_v3_accepts_not_applicable_test_evidence_without_execution(tmp_path):
    """TC-224: evidence-only reviews record no test or repository execution.

    Steps: 1. Create a No-production-code package. 2. Verify it uses not-applicable test evidence.
    3. Verify the complete package is accepted. Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="No-production-code")
    tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert tests["status"] == "not-applicable"
    assert tests["executions"] == []
    assert data["reposReviewed"] == []
    assert data["triggered"] == []
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("mutation", ["execution", "repository"])
def test_tc_225_no_production_code_v3_rejects_test_or_repository_execution(tmp_path, mutation):
    """TC-225: evidence-only reviews must not claim test execution or reviewed repositories.

    Steps: 1. Create a valid No-production-code package. 2. Add execution evidence or a reviewed repository.
    3. Verify the package is rejected. Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="No-production-code")
    if mutation == "execution":
        tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
        tests["executions"] = [{
            "repo": "repo", "status": "pass", "command": ["python", "-m", "pytest"],
            "exitCode": 0, "durationMs": 10, "counts": {"passed": 1, "failed": 0, "skipped": 0},
            "stdout": "1 passed", "stderr": "", "logsTruncated": False,
        }]
        _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)
    else:
        _update_sidecar(sidecar, reposReviewed=["repo"])
    _assert_v3_contract_failure(
        report, sidecar,
        "No-production-code test evidence is not-applicable with no executions or repositories",
    )


def test_tc_226_pro_branch_gate_fail_stops_dispatch_and_accepts_blocking_validation(tmp_path):
    """TC-226: a failing branch gate stops Pro semantic/build dispatch but remains a valid package.

    Steps: 1. Create a Pro package. 2. Record a failing branch gate and its blocking validation.
    3. Verify only the gate is triggered and the verifier accepts the stopped package.
    Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    _configure_strict_v3_branch_gate_stop(report, sidecar)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["triggered"] == [
        "Branch Work Item Gate(gpt-5.6-luna / low; branch work item convention)",
    ]
    assert any(actor.startswith("Requirement Validator(branch work item gate failed)") for actor in data["skipped"])
    assert data["blockingValidations"] == [{
        "gate": "Branch Work Item Gate",
        "reason": "ADO work item type does not match branch prefix",
    }]
    assert not _v3_failures(report, sidecar)


def test_tc_227_pro_branch_gate_fail_requires_blocking_validation(tmp_path):
    """TC-227: a stopped Pro review cannot omit its branch-gate blocking validation.

    Steps: 1. Create a gate-stop Pro package. 2. Remove its blocking validation. 3. Verify rejection.
    Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    _configure_strict_v3_branch_gate_stop(report, sidecar)
    _update_sidecar(sidecar, blockingValidations=[])
    _assert_v3_contract_failure(report, sidecar, "Branch Work Item Gate failure records blocking validation")


@pytest.mark.parametrize("gate_status", ["PASS", "SKIPPED"])
def test_tc_228_pro_nonfailing_branch_gate_requires_requirement_validator(tmp_path, gate_status):
    """TC-228: Pro keeps its normal Requirement Validator contract unless the branch gate fails.

    Steps: 1. Create a Pro package with a passing or skipped branch gate. 2. Remove the Requirement Validator.
    3. Verify rejection. Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    if gate_status == "PASS":
        _configure_v3_branch_gate(report, sidecar, "WARN")
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["branchWorkItemGate"]["status"] = "PASS"
        sidecar.write_text(json.dumps(data), encoding="utf-8")
        _set_report_section_bullet(report, "## Branch Work Item Gate", "Status", "PASS")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["triggered"] = [
        actor for actor in data["triggered"] if not actor.startswith("Requirement Validator(")
    ]
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _set_report_field(report, "Agents Triggered", " | ".join(data["triggered"]))
    _assert_v3_contract_failure(report, sidecar, "Pro triggers dedicated Requirement Validator")


@pytest.mark.parametrize("field", [
    "status", "host", "sessionId", "modelId", "effort", "thinkingEnabled", "source",
    "crossChecks", "freshness", "sessionStatus", "overrideRecorded",
])
def test_tc_229_runtime_attestation_requires_every_lite_parity_field(tmp_path, field):
    """TC-229: Pro requires the full v3 runtime-attestation schema used by Lite.

    Steps: 1. Create a hash-bound Pro package. 2. Remove one required runtime field and rebind its hash.
    3. Verify the verifier rejects the otherwise trusted artifact. Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    runtime = _read_bound_artifact(tmp_path, sidecar, "runtimeAttestation")
    runtime.pop(field)
    _rewrite_bound_artifact(tmp_path, sidecar, "runtimeAttestation", runtime)
    _assert_v3_contract_failure(report, sidecar, "runtime attestation is complete")


@pytest.mark.parametrize("field, value, expected", [
    ("status", "blocked", "runtime attestation status is pass"),
    ("thinkingEnabled", False, "runtime attestation meets shared runtime policy"),
    ("crossChecks", [], "runtime attestation identifies a current cross-checked host session"),
    ("freshness", "stale", "runtime attestation identifies a current cross-checked host session"),
])
def test_tc_230_runtime_attestation_requires_pass_current_cross_checked_policy(tmp_path, field, value, expected):
    """TC-230: Pro applies pass/current cross-check runtime semantics, not just artifact hashing.

    Steps: 1. Create a valid Pro package. 2. Rebind an invalid runtime value. 3. Verify policy rejection.
    Design: final Pro verifier regression findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    runtime = _read_bound_artifact(tmp_path, sidecar, "runtimeAttestation")
    runtime[field] = value
    _rewrite_bound_artifact(tmp_path, sidecar, "runtimeAttestation", runtime)
    _assert_v3_contract_failure(report, sidecar, expected)


def test_tc_231_current_codex_attestation_accepts_nullable_thinking_enabled(tmp_path):
    """TC-231: current Codex evidence may explicitly report unknown thinking state.

    Steps: 1. Create a complete current Codex attestation. 2. Set mandatory thinkingEnabled to null and rebind.
    3. Verify the complete package is accepted. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro")
    runtime = _read_bound_artifact(tmp_path, sidecar, "runtimeAttestation")
    assert runtime["host"] == "codex"
    runtime["thinkingEnabled"] = None
    _rewrite_bound_artifact(tmp_path, sidecar, "runtimeAttestation", runtime)
    assert not _v3_failures(report, sidecar)


def test_tc_232_tiny_branch_gate_fail_stops_all_dispatch_and_accepts_blocker(tmp_path):
    """TC-232: a failing branch gate stops Tiny main, build, and semantic dispatch.

    Steps: 1. Create a Tiny package. 2. Record the failing gate, all skipped actors, and its blocker.
    3. Verify only the gate ran and the stopped package is accepted. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Tiny")
    _configure_strict_v3_branch_gate_stop(report, sidecar, profile="Tiny")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["triggered"] == [
        "Branch Work Item Gate(gpt-5.6-luna / low; branch work item convention)",
    ]
    assert "Main(Tiny all-lens; branch work item gate failed)" in data["skipped"]
    assert "Build Validator[repo](branch work item gate failed)" in data["skipped"]
    assert data["blockingValidations"] == [{
        "gate": "Branch Work Item Gate",
        "reason": "ADO work item type does not match branch prefix",
    }]
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("mutation, expected", [
    ("main", "Branch Work Item Gate failure skips Tiny main review"),
    ("build", "Branch Work Item Gate failure skips every Build Validator"),
    ("requirement", "Branch Work Item Gate failure skips Requirement Validator"),
    ("security", "Branch Work Item Gate failure skips Security Reviewer"),
    ("performance", "Branch Work Item Gate failure skips Performance Reviewer"),
    ("philosophy", "Branch Work Item Gate failure skips Philosophy Reviewer"),
    ("standard", "Branch Work Item Gate failure skips Standard Reviewer"),
    ("blocker", "Branch Work Item Gate failure records blocking validation"),
])
def test_tc_233_tiny_branch_gate_fail_requires_all_skips_and_blocker(tmp_path, mutation, expected):
    """TC-233: every actor suppressed by a Tiny gate failure remains traceable.

    Steps: 1. Create a valid Tiny gate-stop package. 2. Remove one required skip or blocker.
    3. Verify the verifier rejects it. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Tiny")
    _configure_strict_v3_branch_gate_stop(report, sidecar, profile="Tiny")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if mutation == "blocker":
        data["blockingValidations"] = []
    else:
        prefix = {
            "main": "Main(",
            "build": "Build Validator[",
            "requirement": "Requirement Validator(",
            "security": "Security Reviewer(",
            "performance": "Performance Reviewer(",
            "philosophy": "Philosophy Reviewer(",
            "standard": "Standard Reviewer(",
        }[mutation]
        data["skipped"] = [actor for actor in data["skipped"] if not actor.startswith(prefix)]
        _set_report_field(report, "Agents Skipped", " | ".join(data["skipped"]))
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, expected)


def test_tc_234_fail_status_accepts_exit_124_when_failed_count_is_positive(tmp_path):
    """TC-234: exit 124 may be an ordinary reported test failure when failed tests exist.

    Steps: 1. Create routed failing test evidence. 2. Set its process exit code to 124 and rebind.
    3. Verify it remains a valid blocked review package. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro", run_statuses=("fail",))
    tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
    tests["executions"][0]["exitCode"] = 124
    assert tests["executions"][0]["counts"]["failed"] > 0
    _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("field, value", [("exitCode", 1), ("failed", 1)])
def test_tc_235_timeout_status_retains_exit_124_and_zero_failed_count(tmp_path, field, value):
    """TC-235: timeout remains distinct from a normal failed test process.

    Steps: 1. Create valid timeout evidence. 2. Contradict its exit code or failed-test count.
    3. Verify malformed execution rejection. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile="Pro", run_statuses=("timeout",))
    tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
    if field == "failed":
        tests["executions"][0]["counts"][field] = value
    else:
        tests["executions"][0][field] = value
    _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)
    _assert_v3_contract_failure(report, sidecar, "test execution records are complete and consistent")


@pytest.mark.parametrize("session_status, override_recorded, should_pass", [
    ("fresh", False, True),
    ("fresh", True, False),
    ("existing", True, True),
    ("existing", False, False),
])
def test_tc_236_session_status_requires_exact_override_pairing(
        tmp_path, session_status, override_recorded, should_pass):
    """TC-236: session override evidence is false for fresh and true for existing sessions.

    Steps: 1. Create a package for one session/override pairing. 2. Verify valid pairs pass.
    3. Verify contradictory pairs fail. Design: final Pro verifier re-review findings.
    """
    report, sidecar = write_strict_v3_case(
        tmp_path, profile="Pro", session_status=session_status,
        override_recorded=override_recorded,
    )
    failures = _v3_failures(report, sidecar)
    if should_pass:
        assert not failures
    elif session_status == "fresh":
        assert "fresh session requires overrideRecorded false" in failures
    else:
        assert "existing session requires recorded override" in failures


def _update_sidecar(sidecar, **updates):
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data.update(updates)
    sidecar.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("record_version, skill_version", [(1, "1.0.0"), (2, "2.2.0")])
def test_tc_211_dod_24_rejects_every_pre_v3_report_and_sidecar(tmp_path, record_version, skill_version):
    """TC-211: only code-review-pro v3.0.0 with recordVersion 3 is accepted.

    Steps: 1. Create a legacy report and sidecar. 2. Verify the verifier rejects the legacy contract.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar = write_legacy_rejection_case(
        tmp_path, "Tiny",
        {"filesChanged": 1, "changedLines": 10, "docsOnly": False, "riskTriggers": [], "specialistTriggers": {}},
        ["Main(Tiny all-lens)", "Build Validator[repo](gpt-5.6-luna / low; code build)"], "inline", gate_status="SKIPPED",
    )
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["recordVersion"] = record_version
    data["skillVersion"] = skill_version
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    report.write_text(report.read_text(encoding="utf-8").replace("v2.2.0", f"v{skill_version}"), encoding="utf-8")
    assert _v3_failures(report, sidecar), "legacy contracts must be rejected"


def test_tc_212_dod_24_cli_removes_expected_runtime_and_requires_v3_sidecar(tmp_path, capsys):
    """TC-212: CLI derives runtime from mandatory v3 evidence, never an optional launch argument.

    Steps: 1. Inspect API and CLI help. 2. Verify no expected-runtime parameter. 3. Verify inferred and explicit sidecars.
    Design: Task 2 DoD-2.4.
    """
    assert "expected_main_runtime" not in inspect.signature(VERIFY.evaluate).parameters
    with pytest.raises(SystemExit) as stopped:
        VERIFY.main(["--help"])
    assert stopped.value.code == 0
    assert "--expected-main-runtime" not in capsys.readouterr().out
    report, sidecar = write_strict_v3_case(tmp_path)
    assert not _v3_failures(report, sidecar)
    assert not [message for level, message in VERIFY.evaluate(report) if level == "FAIL"]
    sidecar.unlink()
    assert any("sidecar exists" in message for message in _v3_failures(report, sidecar))


@pytest.mark.parametrize("field, invalid, expected", [
    ("reviewedCommit", "", "reviewedCommit is populated"),
    ("targetBranch", "", "targetBranch is populated"),
    ("scopeType", "invalid", "scopeType is valid"),
    ("diffFingerprint", "not-sha", "diffFingerprint is populated SHA-256"),
    ("jsDepsStrategy", "invalid", "jsDepsStrategy is valid"),
    ("iteration", 0, "iteration is a positive integer"),
    ("reviewKind", "invalid", "reviewKind is initial or follow-up"),
])
def test_tc_213_dod_24_v3_retains_provenance_pr_dependency_and_followup_validation(tmp_path, field, invalid, expected):
    """TC-213: artifact success never bypasses retained provenance validation.

    Steps: 1. Create a valid v3 package. 2. Corrupt one retained field. 3. Verify its legacy guard still fails.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    _update_sidecar(sidecar, **{field: invalid})
    _assert_v3_contract_failure(report, sidecar, expected)


def test_tc_214_dod_22_v3_retains_branch_classifier_actor_and_child_runtime_validation(tmp_path):
    """TC-214: v3 retains branch, classifier, actor parity, and child-runtime checks.

    Steps: 1. Create a valid package. 2. Corrupt retained records. 3. Verify every retained guard reports failure.
    Design: Task 2 DoD-2.2/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["branchWorkItemGate"]["status"] = "PASS"
    data["classifier"]["filesChanged"] = 99
    data["runtime"]["build"] = ""
    data["triggered"] = []
    data["skipped"] = []
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    failures = _v3_failures(report, sidecar)
    assert "Branch Work Item Gate report fields match sidecar" in failures
    assert "report Files Changed matches sidecar classifier" in failures
    assert "sidecar runtime contains populated v3 child roles" in failures
    assert "Triggered report records match sidecar" in failures
    assert "Skipped report records match sidecar" in failures


def test_tc_215_dod_22_classifier_requires_scope_status_and_no_deprecated_docs_only(tmp_path):
    """TC-215: classification is driven by scopeStatus and profile branch semantics.

    Steps: 1. Create a valid Tiny package. 2. Replace scopeStatus with docsOnly. 3. Verify rejection.
    Design: Task 2 DoD-2.2.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["classifier"].pop("scopeStatus")
    data["classifier"]["docsOnly"] = False
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, "classifier uses scopeStatus and excludes docsOnly")


@pytest.mark.parametrize("profile", ["No-production-code", "Tiny", "Pro"])
def test_tc_216_dod_22_accepts_scope_driven_no_production_tiny_and_pro_profiles(tmp_path, profile):
    """TC-216: No-production-code, Tiny, and Pro follow their distinct scope-driven rules.

    Steps: 1. Create each valid profile. 2. Verify its agents, classification, and scope are accepted.
    Design: Task 2 DoD-2.2.
    """
    report, sidecar = write_strict_v3_case(tmp_path, profile=profile)
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("mutation, expected", [
    ("arrays-drift", "scope arrays exactly recompute from files entries"),
    ("overlap", "scope arrays have no overlap"),
    ("duplicate-entry", "scope files contain no duplicate paths"),
])
def test_tc_217_dod_22_recomputes_nonoverlapping_unique_scope_arrays(tmp_path, mutation, expected):
    """TC-217: scope arrays are a unique, non-overlapping projection of files entries.

    Steps: 1. Create a scope manifest. 2. Introduce drift, overlap, or duplication. 3. Verify rejection.
    Design: Task 2 DoD-2.2/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    scope = _read_bound_artifact(tmp_path, sidecar, "scopeManifest")
    if mutation == "arrays-drift":
        scope["productionFiles"] = []
        _update_sidecar(sidecar, productionFiles=[], reviewedFiles=[])
    elif mutation == "overlap":
        scope["evidenceFiles"].append("src/service.py")
        _update_sidecar(sidecar, evidenceFiles=scope["evidenceFiles"])
    else:
        scope["files"].append(dict(scope["files"][0]))
    _rewrite_bound_artifact(tmp_path, sidecar, "scopeManifest", scope)
    _assert_v3_contract_failure(report, sidecar, expected)


@pytest.mark.parametrize("changed_symbols, direct_tests, advisory, should_fail", [
    (["Service.run"], [], None, True),
    (["Service.run"], [], "use-unit-testing", False),
    (["Service.run"], ["tests/test_service.py"], None, False),
    ([], ["tests/test_service.py"], None, True),
])
def test_tc_218_dod_23_enforces_changed_symbols_and_exact_direct_test_advisory(
        tmp_path, changed_symbols, direct_tests, advisory, should_fail):
    """TC-218: changed symbols require direct tests or exactly use-unit-testing advice.

    Steps: 1. Create discovery evidence. 2. Vary symbols, direct tests, and advisory. 3. Verify strict validation.
    Design: Task 2 DoD-2.3/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path, direct_tests=direct_tests, advisory=advisory)
    tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
    tests["discovery"]["changedSymbols"] = changed_symbols
    _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)
    failures = _v3_failures(report, sidecar)
    if should_fail:
        assert "changed symbols and direct-test advisory contract is valid" in failures
    else:
        assert not failures


@pytest.mark.parametrize("run_statuses", [("fail",), ("timeout",), ("pass", "fail"), ("pass", "timeout")])
def test_tc_219_dod_23_accepts_routed_blocking_and_multi_repo_test_runs(tmp_path, run_statuses):
    """TC-219: deterministic fail/timeout runs are reportable blocking evidence, including multiple repos.

    Steps: 1. Create one or more deterministic runs. 2. Route non-pass outcomes as BLOCKED. 3. Verify acceptance.
    Design: Task 2 DoD-2.3/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path, run_statuses=run_statuses)
    assert not _v3_failures(report, sidecar)


@pytest.mark.parametrize("mutation", ["missing-command", "status-exit", "count-status", "duplicate-repo"])
def test_tc_220_dod_24_rejects_malformed_or_internally_inconsistent_test_runs(tmp_path, mutation):
    """TC-220: every test run must be complete and internally deterministic.

    Steps: 1. Create valid multi-run evidence. 2. Introduce one schema or result contradiction. 3. Verify rejection.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path, run_statuses=("pass", "fail"))
    tests = _read_bound_artifact(tmp_path, sidecar, "testEvidence")
    if mutation == "missing-command":
        tests["executions"][0].pop("command")
    elif mutation == "status-exit":
        tests["executions"][0]["exitCode"] = 1
    elif mutation == "count-status":
        tests["executions"][1]["counts"]["failed"] = 0
    else:
        tests["executions"][1]["repo"] = tests["executions"][0]["repo"]
    _rewrite_bound_artifact(tmp_path, sidecar, "testEvidence", tests)
    _assert_v3_contract_failure(report, sidecar, "test execution records are complete and consistent")


def test_tc_221_dod_22_matches_report_findings_but_allows_nonfile_gate_blockers(tmp_path):
    """TC-221: semantic findings stay production-only while validation gates may block without files.

    Steps: 1. Create a production finding and gate blocker. 2. Verify acceptance. 3. Retarget report Must Fix to evidence and verify rejection.
    Design: Task 2 DoD-2.2/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(
        tmp_path,
        findings=[{"file": "src/service.py", "evidence": ["tests/test_service.py"]}],
        blocking_validations=[
            {"gate": "Branch Gate", "reason": "work item mismatch"},
            {"gate": "Build Gate", "reason": "build failed"},
            {"gate": "Test Gate", "reason": "deterministic tests failed"},
        ],
    )
    assert not _v3_failures(report, sidecar)
    report.write_text(
        report.read_text(encoding="utf-8").replace("src/service.py:1", "tests/test_service.py:1"),
        encoding="utf-8",
    )
    _assert_v3_contract_failure(report, sidecar, "Detailed Findings targets match sidecar production findings")


@pytest.mark.parametrize("heading", [
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
])
def test_tc_222_dod_23_requires_every_v3_report_section(tmp_path, heading):
    """TC-222: v3 reports expose runtime, scope, tests, gates, semantic review, and findings.

    Steps: 1. Create a complete v3 report. 2. Remove one required section. 3. Verify rejection.
    Design: Task 2 DoD-2.3/DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    report.write_text(report.read_text(encoding="utf-8").replace(heading, f"## Removed {heading[3:]}"), encoding="utf-8")
    _assert_v3_contract_failure(report, sidecar, f"{heading} section exists")


@pytest.mark.parametrize("updates, expected", [
    ({"scopeType": "pr", "mergePreviewStrategy": "invalid"}, "mergePreviewStrategy is valid for pr scope"),
    ({"scopeType": "branch", "prOnlyMode": True}, "PR-only mode requires pr scopeType"),
    ({"jsDepsStrategy": "skip"}, "Build Status table contains JS-SKIPPED row"),
])
def test_tc_223_dod_24_v3_retains_pr_only_merge_preview_and_dependency_routing(tmp_path, updates, expected):
    """TC-223: v3 retains PR-only, merge-preview, and skipped-dependency routing guards.

    Steps: 1. Create a valid v3 package. 2. Introduce invalid PR or dependency routing. 3. Verify rejection.
    Design: Task 2 DoD-2.4.
    """
    report, sidecar = write_strict_v3_case(tmp_path)
    _update_sidecar(sidecar, **updates)
    _assert_v3_contract_failure(report, sidecar, expected)


if __name__ == "__main__":
    unittest.main()
