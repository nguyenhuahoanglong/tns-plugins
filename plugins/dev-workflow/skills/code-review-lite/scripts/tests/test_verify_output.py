"""Spec-first tests for the code-review-lite v4 report verifier.

Requirement mapping:
- AC-1 profiles: Docs/Code Tiny, Lite, branch failure, build failure/gap.
- AC-5 gates: deterministic gate records, no gate-as-agent, build-row parity.
- AC-5 agents: triggered/usage parity and exact token visibility values.
- AC-3/AC-5 evidence: Lite behavior preservation and collateral impact.
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_output import evaluate  # noqa: E402


RUNTIMES = {
    "Requirement Validator": "gpt-5.6-sol / high",
    "Security Reviewer": "gpt-5.6-terra / medium",
    "Performance Reviewer": "gpt-5.6-terra / medium",
    "Philosophy Reviewer": "gpt-5.6-terra / medium",
    "Standard Reviewer": "gpt-5.6-terra / medium",
}

DEFAULT_BUILD_ROW = (
    "repo",
    "PASS",
    "python -m unittest",
    "0",
    "0",
    "0",
    "C:/repo/.CodeReview/build.log / completed",
)


def _write_report_body(
    root,
    profile,
    *,
    branch_status="PASS",
    build_rows=None,
    triggered=(),
    usage_rows=None,
    specialist_triggers=None,
    include_behavior=True,
    include_collateral=True,
    include_scope_drift=True,
    manifest_build_rows=None,
    include_requirement_row=True,
):
    """Write the report body used by strict v4 fixtures and the v3 rejection case."""
    classification = {
        "Docs Tiny": (7, 500, "true", "None"),
        "Code Tiny": (1, 42, "false", "None"),
        "Lite": (6, 200, "false", "async-lifecycle"),
    }[profile]
    if specialist_triggers is None:
        specialist_triggers = (
            "Performance Reviewer=async-lifecycle" if profile == "Lite" else "None"
        )
    if build_rows is None:
        build_rows = [] if profile == "Docs Tiny" else [DEFAULT_BUILD_ROW]
    triggered = list(triggered)
    if usage_rows is None:
        usage_rows = [
            (
                agent,
                RUNTIMES.get(agent, "deterministic"),
                "isolated manifest",
                "120",
                "not exposed",
                "0",
                "45",
            )
            for agent in triggered
        ]

    gate = {
        "Status": branch_status,
        "Branch": "US/123-valid-branch" if branch_status != "SKIPPED" else "None",
        "Work Item": (
            "US/123; expected User Story; actual User Story; Valid story (Active)"
            if branch_status in {"PASS", "WARN"}
            else "None"
        ),
        "Source": "branch" if branch_status != "SKIPPED" else "working",
        "Reason": {
            "PASS": "Branch prefix and ADO work item type match",
            "WARN": "Branch prefix is non-standard; ADO work item exists",
            "FAIL": "Branch prefix and ADO work item type do not match",
            "SKIPPED": "Scope has no created PR or branch to validate",
        }[branch_status],
    }

    triggered_lines = (
        [f"- {agent} (`{RUNTIMES.get(agent, 'deterministic')}`) - fixture reason" for agent in triggered]
        if triggered
        else ["- None"]
    )
    known_semantic_agents = set(RUNTIMES)
    skipped_agents = sorted(known_semantic_agents - set(triggered))
    skipped_lines = (
        [f"- {agent} - profile or gate outcome" for agent in skipped_agents]
        if skipped_agents
        else ["- None"]
    )

    if usage_rows:
        usage_lines = [
            "| Agent | Runtime | Context Mode | Input Tokens | Cache Read | Cache Write | Output Tokens |",
            "|---|---|---|---:|---:|---:|---:|",
            *[
                f"| {agent} | `{runtime}` | {context_mode} | {input_tokens} | "
                f"{cache_read} | {cache_write} | {output_tokens} |"
                for (
                    agent,
                    runtime,
                    context_mode,
                    input_tokens,
                    cache_read,
                    cache_write,
                    output_tokens,
                ) in usage_rows
            ],
        ]
    else:
        usage_lines = ["None"]

    if build_rows:
        build_lines = [
            "| Repo | Status | Command | Exit | Errors | Warnings | Log / Reason |",
            "|---|---|---|---:|---:|---:|---|",
            *[
                f"| `{repo}` | {status} | `{command}` | {exit_code} | {errors} | "
                f"{warnings} | {log_reason} |"
                for repo, status, command, exit_code, errors, warnings, log_reason in build_rows
            ],
        ]
    else:
        build_lines = ["Build Gates: Not applicable"]

    manifest_path = Path(root) / "feature.context.json"
    if profile == "Lite":
        source_rows = build_rows if manifest_build_rows is None else manifest_build_rows
        manifest_records = []
        for repo, status, command, exit_code, errors, warnings, log_reason in source_rows:
            log_path, separator, reason = log_reason.partition(" / ")
            if not separator:
                log_path, reason = "", log_reason
            manifest_records.append(
                {
                    "repo": repo,
                    "status": status,
                    "command": command,
                    "commandExitCode": None if exit_code == "n/a" else int(exit_code),
                    "totalErrorCount": int(errors),
                    "totalWarningCount": int(warnings),
                    "logPath": log_path,
                    "reason": reason,
                }
            )
        manifest_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "code-review-lite.context.v1",
                    "requirements": {
                        "mode": "work-item",
                        "directSource": "user",
                        "direct": "preserve retry behavior",
                        "parentContext": "",
                    },
                    "buildResults": manifest_records,
                }
            ),
            encoding="utf-8",
        )

    evidence_lines = []
    if include_behavior:
        evidence_lines.extend(
            [
                "## Behavior Preservation and Collateral Impact",
                "",
                "| Behavior | Classification | Base -> New | Impact Trace | Preservation Evidence | Status |",
                "|---|---|---|---|---|---|",
                "| retry behavior | Necessary collateral | one -> bounded | caller/event | `tests/test_retry.py:20` | Preserved |",
                "",
            ]
        )
        if include_collateral:
            evidence_lines.extend(["- **Collateral Impact**: None", ""])
        if include_scope_drift:
            evidence_lines.extend(["- **Scope Drift**: None", ""])

    path = Path(root) / "feature.lite.md"
    path.write_text(
        "\n".join(
            [
                "# Code Review (Lite): Test",
                "",
                "**Date**: 2026-07-13",
                "**Source**: US/123-valid-branch",
                "**Target**: master",
                f"**Files Reviewed**: {classification[0]}",
                "**Skill**: code-review-lite v3.0.0",
                f"**Review Profile**: {profile}",
                "**Main Runtime**: gpt-5.6-sol / xhigh",
                "**PR-Only**: false",
                "**Merge Preview**: n/a",
                f"**Context Manifest**: {manifest_path if profile == 'Lite' else 'n/a'}",
                "",
                "## Classification",
                "",
                f"- **Files Changed**: {classification[0]}",
                f"- **Changed Lines**: {classification[1]}",
                f"- **Documentation Only**: {classification[2]}",
                f"- **Risk Triggers**: {classification[3]}",
                f"- **Specialist Triggers**: {specialist_triggers}",
                "- **Decision**: fixture",
                "",
                "## Deterministic Gates",
                "",
                "### Branch Work Item Gate",
                f"- **Status**: {gate['Status']}",
                f"- **Branch**: {gate['Branch']}",
                f"- **Work Item**: {gate['Work Item']}",
                f"- **Source**: {gate['Source']}",
                f"- **Reason**: {gate['Reason']}",
                "",
                "### Build Gates",
                *build_lines,
                "",
                "## Semantic Agents",
                "",
                "### Triggered",
                *triggered_lines,
                "",
                "### Skipped",
                *skipped_lines,
                "",
                "### Agent Usage",
                *usage_lines,
                "",
                "## Requirement Evidence",
                "",
                "| Requirement | Status | Evidence |",
                "|---|---|---|",
                *(
                    ["| preserve retry behavior | Addressed | `src/retry.py:10` bounds retries |"]
                    if include_requirement_row
                    else []
                ),
                "",
                *evidence_lines,
                "## Must Fix Before Merge",
                "None.",
                "",
                "## Detailed Findings",
                "None.",
                "",
                "## Recommendation",
                "Merge after deterministic and semantic evidence is verified.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_report(root, profile, **options):
    """Write one strict v4 fixture while preserving selectable gate variations."""
    report, *_ = _write_v4_contract(Path(root), profile=profile, **options)
    return report


class VerifyOutputV4GateTests(unittest.TestCase):
    def failures(self, path, profile):
        return [
            message
            for level, message in evaluate(
                path, profile
            )
            if level == "FAIL"
        ]

    def assert_valid(self, path, profile):
        self.assertEqual([], self.failures(path, profile))

    def assert_contract_failure(self, path, profile, expected_message):
        self.assertIn(expected_message, self.failures(path, profile))

    # AC-1: profile child counts and deterministic-gate routing.
    def test_no_production_code_accepts_zero_semantic_agents(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = _write_no_production_contract(Path(root))
            self.assert_valid(path, "No Production Code")

    def test_no_production_code_rejects_semantic_agent(self):
        with tempfile.TemporaryDirectory() as root:
            path, _ = _write_no_production_contract(Path(root))
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "### Triggered\n- None",
                    "### Triggered\n- Requirement Validator (`gpt-5.6-sol / high`) - invalid",
                ),
                encoding="utf-8",
            )
            self.assert_contract_failure(
                path,
                "No Production Code",
                "No Production Code has no semantic execution",
            )

    def test_code_tiny_accepts_zero_semantic_agents_and_deterministic_build(self):
        with tempfile.TemporaryDirectory() as root:
            self.assert_valid(write_report(root, "Code Tiny"), "Code Tiny")

    def test_code_tiny_rejects_semantic_agent(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Code Tiny", triggered=["Performance Reviewer"])
            self.assert_contract_failure(
                path, "Code Tiny", "Code Tiny triggers zero semantic agents"
            )

    def test_code_tiny_rejects_missing_deterministic_build(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Code Tiny", build_rows=[])
            self.assert_contract_failure(
                path,
                "Code Tiny",
                "Production profiles report deterministic build gate rows",
            )

    def test_lite_accepts_requirement_and_one_classified_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_valid(path, "Lite")

    def test_lite_accepts_requirement_without_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                specialist_triggers="None",
            )
            self.assert_valid(path, "Lite")

    def test_lite_rejects_omitted_selected_specialist_after_passing_builds(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
            )
            self.assert_contract_failure(
                path,
                "Lite",
                "Lite passing gates trigger every selected semantic agent",
            )

    def test_lite_rejects_missing_requirement_validator(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Lite", triggered=["Performance Reviewer"])
            self.assert_contract_failure(
                path, "Lite", "Lite passing gates trigger every selected semantic agent"
            )

    def test_lite_rejects_more_than_one_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=[
                    "Requirement Validator",
                    "Performance Reviewer",
                    "Security Reviewer",
                ],
                specialist_triggers=(
                    "Performance Reviewer=async-lifecycle | Security Reviewer=auth"
                ),
            )
            self.assert_contract_failure(
                path, "Lite", "Lite classifies at most one specialist"
            )

    def test_lite_rejects_unclassified_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Security Reviewer"],
            )
            self.assert_contract_failure(
                path, "Lite", "Lite triggers only the classified specialist"
            )

    def test_branch_fail_accepts_zero_semantic_agents(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Lite", branch_status="FAIL", triggered=[])
            self.assert_valid(path, "Lite")

    def test_branch_fail_rejects_any_semantic_agent(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                branch_status="FAIL",
                triggered=["Requirement Validator"],
            )
            self.assert_contract_failure(
                path, "Lite", "Branch FAIL triggers zero semantic agents"
            )

    def test_lite_build_fail_accepts_requirement_only(self):
        with tempfile.TemporaryDirectory() as root:
            failed_build = [(
                "repo", "FAIL", "python -m unittest", "1", "2", "0",
                "C:/repo/.CodeReview/build.log / tests failed",
            )]
            path = write_report(
                root,
                "Lite",
                build_rows=failed_build,
                triggered=["Requirement Validator"],
            )
            self.assert_valid(path, "Lite")

    def test_lite_build_fail_rejects_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            failed_build = [(
                "repo", "FAIL", "python -m unittest", "1", "2", "0",
                "C:/repo/.CodeReview/build.log / tests failed",
            )]
            path = write_report(
                root,
                "Lite",
                build_rows=failed_build,
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_contract_failure(
                path, "Lite", "Blocking build or test outcome routes Requirement Validator only"
            )

    def test_lite_build_gaps_accept_requirement_only(self):
        gap_rows = (
            ("NOT RUN (environment)", "n/a", "tool missing"),
            ("NOT RUN (timeout)", "n/a", "build timed out"),
            ("JS-SKIPPED", "n/a", "no lockfile"),
        )
        for status, exit_code, reason in gap_rows:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                path = write_report(
                    root,
                    "Lite",
                    build_rows=[(
                        "repo", status, "python -m unittest", exit_code, "0", "0", reason,
                    )],
                    triggered=["Requirement Validator"],
                )
                self.assert_valid(path, "Lite")

    def test_lite_build_gap_rejects_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                build_rows=[(
                    "repo", "NOT RUN (environment)", "python -m unittest", "n/a", "0", "0",
                    "tool missing",
                )],
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_contract_failure(
                path, "Lite", "Blocking build or test outcome routes Requirement Validator only"
            )

    # AC-5: gate/agent separation and complete deterministic records.
    def test_rejects_gate_in_semantic_trigger_list(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Code Tiny", triggered=["Build Gate"])
            self.assert_contract_failure(
                path, "Code Tiny", "Deterministic gates never appear as semantic agents"
            )

    def test_rejects_gate_in_agent_usage(self):
        with tempfile.TemporaryDirectory() as root:
            gate_usage = [(
                "Branch Work Item Gate", "deterministic", "gate", "0", "0", "0", "0",
            )]
            path = write_report(root, "Code Tiny", usage_rows=gate_usage)
            self.assert_contract_failure(
                path, "Code Tiny", "Deterministic gates never appear in Agent Usage"
            )

    def test_rejects_duplicate_build_rows_for_repo(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root, "Code Tiny", build_rows=[DEFAULT_BUILD_ROW, DEFAULT_BUILD_ROW]
            )
            self.assert_contract_failure(
                path, "Code Tiny", "Build gate rows have one record per repo"
            )

    def test_lite_accepts_build_rows_matching_sidecar_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_valid(path, "Lite")

    def test_lite_rejects_invalid_build_status(self):
        with tempfile.TemporaryDirectory() as root:
            invalid = (
                "repo",
                "FABRICATED",
                "python -m unittest",
                "0",
                "0",
                "0",
                "C:/repo/.CodeReview/build.log / invalid status",
            )
            path = write_report(
                root,
                "Lite",
                build_rows=[invalid],
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_contract_failure(
                path, "Lite", "Build gate rows contain valid deterministic values"
            )

    def test_rejects_incomplete_build_row(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Code Tiny")
            text = path.read_text(encoding="utf-8").replace(
                "| `repo` | PASS | `python -m unittest` | 0 | 0 | 0 | C:/repo/.CodeReview/build.log / completed |",
                "| `repo` | PASS | `python -m unittest` | 0 | 0 |",
            )
            path.write_text(text, encoding="utf-8")
            self.assert_contract_failure(
                path, "Code Tiny", "Build gate rows are complete deterministic records"
            )

    # AC-5: usage rows must match triggered agents and expose only valid counters.
    def test_agent_usage_accepts_zero_and_not_exposed(self):
        with tempfile.TemporaryDirectory() as root:
            usage = [(
                "Requirement Validator",
                RUNTIMES["Requirement Validator"],
                "isolated manifest",
                "0",
                "not exposed",
                "not exposed",
                "0",
            )]
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                usage_rows=usage,
                specialist_triggers="None",
            )
            self.assert_valid(path, "Lite")

    def test_agent_usage_rejects_invalid_counter_values(self):
        invalid_values = ("-1", "1.5", "Not exposed", "unknown")
        for value in invalid_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as root:
                usage = [(
                    "Requirement Validator",
                    RUNTIMES["Requirement Validator"],
                    "isolated manifest",
                    value,
                    "0",
                    "0",
                    "0",
                )]
                path = write_report(
                    root,
                    "Lite",
                    triggered=["Requirement Validator"],
                    usage_rows=usage,
                    specialist_triggers="None",
                )
                self.assert_contract_failure(
                    path,
                    "Lite",
                    "Agent Usage values are non-negative integers or exact not exposed",
                )

    def test_rejects_missing_usage_row_for_triggered_agent(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                usage_rows=[],
                specialist_triggers="None",
            )
            self.assert_contract_failure(
                path, "Lite", "Agent Usage rows match triggered semantic agents"
            )

    def test_rejects_usage_row_for_untriggered_agent(self):
        with tempfile.TemporaryDirectory() as root:
            usage = [(
                "Performance Reviewer",
                RUNTIMES["Performance Reviewer"],
                "isolated manifest",
                "1",
                "0",
                "0",
                "1",
            )]
            path = write_report(root, "Code Tiny", usage_rows=usage)
            self.assert_contract_failure(
                path, "Code Tiny", "Agent Usage rows match triggered semantic agents"
            )

    # AC-3/AC-5: Lite evidence is mandatory and mechanically visible.
    def test_lite_rejects_missing_behavior_preservation_section(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                specialist_triggers="None",
                include_behavior=False,
            )
            self.assert_contract_failure(
                path,
                "Lite",
                "Lite reports behavior-preservation and collateral-impact evidence",
            )

    def test_lite_rejects_missing_collateral_impact(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                specialist_triggers="None",
                include_collateral=False,
            )
            self.assert_contract_failure(
                path, "Lite", "Lite reports Collateral Impact"
            )

    def test_lite_rejects_missing_scope_drift(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator"],
                specialist_triggers="None",
                include_scope_drift=False,
            )
            self.assert_contract_failure(path, "Lite", "Lite reports Scope Drift")

    def test_work_item_lite_rejects_empty_direct_requirement_table(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Performance Reviewer"],
                include_requirement_row=False,
            )
            self.assert_contract_failure(
                path,
                "Lite",
                "Work-item Lite reports evidence for direct requirements",
            )

    def test_rejects_wrong_version(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace("4.0.0", "3.0.0"),
                encoding="utf-8",
            )
            self.assert_contract_failure(
                path, "Lite", "Only code-review-lite v4.0.0 reports are accepted"
            )


if __name__ == "__main__":
    unittest.main()


# Strict v4 contract tests. Source: .plans/code-review-runtime-scope-test-harness.md,
# Task 3 / AC-1 through AC-5 / DoD-3.1 through DoD-3.4.


def _v4_failures(path):
    """Return verifier failures without the retired expected-launch-runtime input."""
    return [message for level, message in evaluate(path, "Lite") if level == "FAIL"]


def _write_json_artifact(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _write_v4_contract(
    tmp_path,
    *,
    session=None,
    scope=None,
    tests=None,
    profile="Lite",
    **report_options,
):
    """Create a valid v4 Lite review plus its independently hashable evidence."""
    session = session or {
        "status": "pass",
        "sessionStatus": "fresh",
        "overrideRecorded": False,
    }
    runtime_payload = {
        "status": "pass",
        "host": "codex",
        "sessionId": "thread-123",
        "modelId": "gpt-5.6-terra",
        "effort": "medium",
        "thinkingEnabled": True,
        "source": "codex-rollout",
        "crossChecks": ["threadId", "duplicate-runtime-fields"],
        "freshness": "current",
        "sessionStatus": session["sessionStatus"],
        "overrideRecorded": session["overrideRecorded"],
    }
    runtime_path, runtime_hash = _write_json_artifact(
        tmp_path,
        "runtime-attestation.json",
        runtime_payload,
    )
    scope_path, scope_hash = _write_json_artifact(
        tmp_path,
        "scope-manifest.json",
        scope
        or {
            "status": "pass",
            "productionFiles": ["src/retry.py"],
            "evidenceFiles": ["tests/test_retry.py"],
            "excludedFiles": ["dist/retry.js"],
            "files": [
                {"path": "src/retry.py", "classification": "production", "reasonCode": "production_code"},
                {"path": "tests/test_retry.py", "classification": "evidence", "reasonCode": "test_file"},
                {"path": "dist/retry.js", "classification": "excluded", "reasonCode": "generated_output"},
            ],
        },
    )
    tests_path, tests_hash = _write_json_artifact(
        tmp_path,
        "test-evidence.json",
        tests
        or {
            "status": "pass",
            "blocking": False,
            "advisory": None,
            "changedSymbols": ["RetryPolicy.execute"],
            "directTests": ["tests/test_retry.py"],
            "affectedTests": [],
            "runs": [
                {
                    "status": "pass",
                    "command": ["python", "-m", "pytest"],
                    "exitCode": 0,
                    "counts": {"passed": 1, "failed": 0, "skipped": 0},
                }
            ],
        },
    )
    if "triggered" not in report_options:
        report_options["triggered"] = (
            ["Requirement Validator", "Performance Reviewer"]
            if profile == "Lite"
            else []
        )
    report = _write_report_body(tmp_path, profile, **report_options)
    context_path = tmp_path / "feature.context.json"
    context = (
        json.loads(context_path.read_text(encoding="utf-8"))
        if context_path.is_file()
        else {"requirements": {"mode": "inline", "direct": ""}, "buildResults": []}
    )
    safe_branch = "US_123_valid_branch"
    sidecar = tmp_path / f".{safe_branch}.lite.review-meta.json"
    sidecar.write_text(
        json.dumps(
            {
                "recordVersion": 3,
                "skillName": "code-review-lite",
                "skillVersion": "4.0.0",
                "reviewProfile": profile,
                "runtime": runtime_payload,
                "session": session,
                "productionAllowlist": (scope or {"productionFiles": ["src/retry.py"]}).get("productionFiles"),
                "requirements": context.get("requirements", {}),
                "buildResults": context.get("buildResults", []),
                "artifacts": {
                    "runtime": {"path": str(runtime_path), "sha256": runtime_hash},
                    "scope": {"path": str(scope_path), "sha256": scope_hash},
                    "tests": {"path": str(tests_path), "sha256": tests_hash},
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    report.write_text(
        report.read_text(encoding="utf-8")
        .replace("code-review-lite v3.0.0", "code-review-lite v4.0.0")
        .replace("**Main Runtime**: gpt-5.6-sol / xhigh", "**Main Runtime**: gpt-5.6-terra / medium")
        .replace(f"**Context Manifest**: {context_path}", "**Context Manifest**: n/a")
        + "\n## Runtime, Scope, and Test Evidence\n"
        + f"- **Runtime Attestation**: {runtime_path} / sha256:{runtime_hash}\n"
        + f"- **Scope Manifest**: {scope_path} / sha256:{scope_hash}\n"
        + f"- **Test Evidence**: {tests_path} / sha256:{tests_hash}\n"
        + f"- **Lite Metadata**: {sidecar}\n",
        encoding="utf-8",
    )
    return report, sidecar, runtime_path, scope_path, tests_path


def _rewrite_artifact(report, sidecar, key, path, payload):
    """Replace one JSON artifact and keep report/sidecar SHA-256 references exact."""
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    old_digest = metadata["artifacts"][key]["sha256"]
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    new_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata["artifacts"][key]["sha256"] = new_digest
    if key == "runtime":
        metadata["runtime"] = payload
        metadata["session"] = {
            "status": payload.get("status"),
            "sessionStatus": payload.get("sessionStatus"),
            "overrideRecorded": payload.get("overrideRecorded"),
        }
    sidecar.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            f"{path} / sha256:{old_digest}",
            f"{path} / sha256:{new_digest}",
        ),
        encoding="utf-8",
    )


def _route_requirement_only(report):
    """Project a blocking build/test outcome to Requirement Validator only."""
    text = report.read_text(encoding="utf-8").replace(
        "- Requirement Validator (`gpt-5.6-sol / high`) - fixture reason\n"
        "- Performance Reviewer (`gpt-5.6-terra / medium`) - fixture reason",
        "- Requirement Validator (`gpt-5.6-sol / high`) - fixture reason",
    )
    text = text.replace(
        "| Performance Reviewer | `gpt-5.6-terra / medium` | isolated manifest | "
        "120 | not exposed | 0 | 45 |\n",
        "",
    )
    report.write_text(text, encoding="utf-8")


def _write_no_production_contract(tmp_path):
    """Create the required report/evidence surface without executing review work."""
    scope = {
        "status": "no-production-code",
        "productionFiles": [],
        "evidenceFiles": ["docs/decision.md", "tests/test_retry.py"],
        "excludedFiles": ["dist/retry.js"],
        "files": [
            {"path": "docs/decision.md", "classification": "evidence", "reasonCode": "documentation"},
            {"path": "tests/test_retry.py", "classification": "evidence", "reasonCode": "test_file"},
            {"path": "dist/retry.js", "classification": "excluded", "reasonCode": "generated_output"},
        ],
    }
    tests = {
        "status": "not-applicable",
        "reasonCode": "no-production-code",
        "changedSymbols": [],
        "directTests": [],
        "affectedTests": [],
        "runs": [],
        "advisory": None,
    }
    report, sidecar, *_ = _write_v4_contract(tmp_path, scope=scope, tests=tests)
    text = report.read_text(encoding="utf-8")
    text = text.replace("**Review Profile**: Lite", "**Review Profile**: No Production Code")
    text = re.sub(r"^\*\*Context Manifest\*\*: .+$", "**Context Manifest**: n/a", text, flags=re.MULTILINE)
    text = re.sub(
        r"### Build Gates\n.*?(?=\n## Semantic Agents)",
        "### Build Gates\nBuild Gates: Not applicable\n",
        text,
        flags=re.DOTALL,
    )
    text = text.replace(
        "- Requirement Validator (`gpt-5.6-sol / high`) - fixture reason\n"
        "- Performance Reviewer (`gpt-5.6-terra / medium`) - fixture reason",
        "- None",
    )
    text = re.sub(
        r"\| Requirement Validator \|.*?\n\| Performance Reviewer \|.*?\n",
        "None\n",
        text,
    )
    text = text.replace(
        "| retry behavior | Necessary collateral | one -> bounded | caller/event | "
        "`tests/test_retry.py:20` | Preserved |",
        "",
    )
    text += "- **Test Gate**: NOT APPLICABLE (no-production-code)\n"
    report.write_text(text, encoding="utf-8")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["reviewProfile"] = "No Production Code"
    metadata["buildResults"] = []
    sidecar.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    return report, sidecar


def test_tc_021_accepts_v4_attested_artifacts_and_safe_branch_sidecar(tmp_path):
    """TC-021 / DoD-3.4: a valid v4 review verifies all hashed artifact evidence.

    Steps:
      1. Create runtime, production-scope, and direct-test evidence under tmp_path.
      2. Reference their SHA-256 values from the required safe-branch Lite sidecar.
      3. Verify the v4 report passes without an optional expected-main-runtime input.
    """
    report, *_ = _write_v4_contract(tmp_path)

    assert _v4_failures(report) == []


def test_tc_022_rejects_missing_or_tampered_attested_artifacts(tmp_path):
    """TC-022 / DoD-3.4: missing or altered evidence fails closed.

    Steps:
      1. Create a valid v4 evidence set and then remove its test evidence artifact.
      2. Recreate it with different content while retaining the sidecar hash.
      3. Verify both cases are rejected as missing or tampered deterministic evidence.
    """
    report, _, _, _, tests_path = _write_v4_contract(tmp_path)
    tests_path.unlink()
    assert any("test" in message.lower() and "artifact" in message.lower() for message in _v4_failures(report))

    report, _, _, _, tests_path = _write_v4_contract(tmp_path)
    tests_path.write_text('{"status":"fail"}', encoding="utf-8")
    assert any("sha-256" in message.lower() or "hash" in message.lower() for message in _v4_failures(report))


def test_tc_023_rejects_blocked_runtime_and_unrecorded_existing_session_override(tmp_path):
    """TC-023 / DoD-3.1: runtime/session clearance is mandatory before Lite review.

    Steps:
      1. Mark the runtime artifact blocked and the session as existing without override.
      2. Keep all report formatting otherwise valid.
      3. Verify both preflight failures are rejected by the verifier.
    """
    report, sidecar, runtime_path, _, _ = _write_v4_contract(
        tmp_path,
        session={"status": "confirmation-required", "sessionStatus": "existing", "overrideRecorded": False},
    )
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["status"] = "blocked"
    runtime["reasonCode"] = "effort_below_minimum"
    _rewrite_artifact(report, sidecar, "runtime", runtime_path, runtime)

    failures = _v4_failures(report)
    assert any("runtime" in message.lower() and "pass" in message.lower() for message in failures)
    assert any("existing" in message.lower() and "override" in message.lower() for message in failures)


def test_tc_024_accepts_recorded_existing_session_override(tmp_path):
    """TC-024 / DoD-3.1: an explicit existing-session override remains valid evidence."""
    report, *_ = _write_v4_contract(
        tmp_path,
        session={"status": "pass", "sessionStatus": "existing", "overrideRecorded": True},
    )

    assert _v4_failures(report) == []


def test_tc_025_requires_exact_report_runtime_match_without_cli_runtime_dependency(tmp_path):
    """TC-025 / DoD-3.4: report runtime must equal attested sidecar runtime internally.

    Steps:
      1. Create valid v4 evidence then alter only the report runtime.
      2. Invoke the verifier without the retired expected-main-runtime argument.
      3. Verify the report/attestation mismatch is rejected.
    """
    report, *_ = _write_v4_contract(tmp_path)
    report.write_text(
        report.read_text(encoding="utf-8").replace("gpt-5.6-terra / medium", "gpt-5.6-sol / high", 1),
        encoding="utf-8",
    )

    assert any("runtime" in message.lower() and "match" in message.lower() for message in _v4_failures(report))


def test_tc_026_no_production_code_profile_for_docs_tests_and_excluded_only(tmp_path):
    """TC-026 / DoD-3.2: evidence-only scopes emit no findings or semantic agents."""
    report, _ = _write_no_production_contract(tmp_path)

    assert _v4_failures(report) == []


def test_tc_027_rejects_findings_outside_production_allowlist_but_allows_evidence_citations(tmp_path):
    """TC-027 / DoD-3.2: findings are production-only while tests/docs remain citeable evidence."""
    report, *_ = _write_v4_contract(tmp_path)
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "## Detailed Findings\nNone.",
            "## Detailed Findings\n### F-001\n- **Target**: `tests/test_retry.py:20`\n"
            "- **Evidence**: `docs/decision.md:4`\n### F-002\n"
            "- **Target**: `dist/retry.js:1`",
        ),
        encoding="utf-8",
    )

    failures = _v4_failures(report)
    assert any("production allowlist" in message.lower() for message in failures)


def test_tc_028_requires_exact_missing_direct_test_advisory_but_keeps_specialists_non_blocking(tmp_path):
    """TC-028 / DoD-3.3: absent direct tests require use-unit-testing advisory only.

    Steps:
      1. Supply an advisory test artifact with no direct tests and an affected test.
      2. Retain a compatible non-blocking semantic specialist outcome.
      3. Verify the exact advisory appears without creating a required finding.
    """
    tests = {
        "status": "advisory",
        "advisory": "use-unit-testing",
        "changedSymbols": ["RetryPolicy.execute"],
        "directTests": [],
        "affectedTests": ["tests/test_retry.py"],
        "runs": [
            {
                "status": "pass",
                "command": ["python", "-m", "pytest"],
                "exitCode": 0,
                "counts": {"passed": 1, "failed": 0, "skipped": 0},
            }
        ],
    }
    report, *_ = _write_v4_contract(tmp_path, tests=tests)
    report.write_text(
        report.read_text(encoding="utf-8")
        + "- **Unit-Test Advisory**: use-unit-testing\n",
        encoding="utf-8",
    )
    assert _v4_failures(report) == []


def test_tc_029_routes_test_failure_or_gap_to_requirement_validator_only_and_preserves_build_usage_checks(tmp_path):
    """TC-029 / DoD-3.4: test failures/gaps suppress specialists but retain deterministic checks."""
    tests = {
        "status": "fail",
        "advisory": None,
        "blocking": True,
        "changedSymbols": ["RetryPolicy.execute"],
        "directTests": ["tests/test_retry.py"],
        "affectedTests": [],
        "runs": [
            {
                "status": "fail",
                "command": ["python", "-m", "pytest"],
                "exitCode": 1,
                "counts": {"passed": 0, "failed": 1, "skipped": 0},
            }
        ],
    }
    report, *_ = _write_v4_contract(tmp_path, tests=tests)
    _route_requirement_only(report)
    report.write_text(
        report.read_text(encoding="utf-8") + "- **Test Gate**: BLOCKED (fail)\n",
        encoding="utf-8",
    )

    assert _v4_failures(report) == []


def test_tc_030_rejects_lite_artifacts_for_multi_specialist_escalation(tmp_path):
    """TC-030 / DoD-3.1: multi-specialist scope escalates before Lite artifacts exist.

    Only shared preflight and scope evidence may precede escalation. If a Lite report
    or sidecar claims an Escalate profile, the verifier must reject that impossible state.
    """
    report, *_ = _write_v4_contract(tmp_path)
    text = report.read_text(encoding="utf-8").replace(
        "**Review Profile**: Lite",
        "**Review Profile**: Escalate",
    )
    report.write_text(text, encoding="utf-8")

    failures = _v4_failures(report)
    assert any("Escalate" in message or "supported v4 profile" in message for message in failures)


def test_tc_031_rejects_legacy_v3_reports_even_when_the_old_contract_is_valid(tmp_path):
    """TC-031 / DoD-3.4: public verification accepts v4.0.0/recordVersion 3 only.

    Steps:
      1. Create an otherwise-valid legacy v3 Lite report.
      2. Run the public verifier entry point.
      3. Verify the report is rejected explicitly as a legacy contract.
    """
    report = _write_report_body(
        tmp_path,
        "Lite",
        triggered=["Requirement Validator", "Performance Reviewer"],
    )

    failures = [message for level, message in evaluate(report, "Lite") if level == "FAIL"]

    assert "Only code-review-lite v4.0.0 reports are accepted" in failures


def test_tc_032_rechecks_pass_attestation_against_shared_runtime_policy(tmp_path):
    """TC-032 / AC-1: verifier distrusts a forged pass status on a below-policy runtime."""
    report, sidecar, runtime_path, _, _ = _write_v4_contract(tmp_path)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime.update({"status": "pass", "modelId": "gpt-5.6-luna", "effort": "medium"})
    _rewrite_artifact(report, sidecar, "runtime", runtime_path, runtime)
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "**Main Runtime**: gpt-5.6-terra / medium",
            "**Main Runtime**: gpt-5.6-luna / medium",
        ),
        encoding="utf-8",
    )

    failures = _v4_failures(report)

    assert any("runtime policy" in message.lower() or "below minimum" in message.lower() for message in failures)


def test_tc_033_requires_complete_sidecar_identity_runtime_session_and_artifact_contract(tmp_path):
    """TC-033 / DoD-3.4: sidecar identity and evidence must equal the report artifacts."""
    cases = (
        ("skill-name", lambda value: value.update(skillName="other-skill"), "skillName"),
        ("skill-version", lambda value: value.update(skillVersion="3.0.0"), "skillVersion"),
        ("profile", lambda value: value.update(reviewProfile="Code Tiny"), "reviewProfile"),
        ("runtime", lambda value: value.update(runtime={"modelId": "gpt-5.6-terra", "effort": "medium"}), "runtime"),
        (
            "session",
            lambda value: value.update(
                session={"status": "pass", "sessionStatus": "existing", "overrideRecorded": False}
            ),
            "session",
        ),
        ("artifact", lambda value: value["artifacts"].pop("scope"), "Scope Manifest"),
    )
    for name, mutate, expected in cases:
        case_root = tmp_path / name
        case_root.mkdir()
        report, sidecar, *_ = _write_v4_contract(case_root)
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        mutate(metadata)
        sidecar.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")

        failures = _v4_failures(report)

        assert any(expected.lower() in message.lower() for message in failures), name


def test_tc_034_no_production_code_forbids_worktree_context_build_test_and_review_execution(tmp_path):
    """TC-034 / DoD-3.2: no-production output records evidence but executes no review work."""
    cases = (
        (
            "test-execution",
            "test",
            lambda report, sidecar: _rewrite_no_production_test_as_executed(report, sidecar),
        ),
        (
            "worktree",
            "worktree",
            lambda report, sidecar: _add_sidecar_field(sidecar, "worktreeCreated", True),
        ),
        (
            "context",
            "context",
            lambda report, sidecar: report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "**Context Manifest**: n/a", "**Context Manifest**: C:/repo/context.json"
                ),
                encoding="utf-8",
            ),
        ),
        (
            "build",
            "build",
            lambda report, sidecar: report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "Build Gates: Not applicable",
                    "| `repo` | PASS | `python -m pytest` | 0 | 0 | 0 | executed |",
                ),
                encoding="utf-8",
            ),
        ),
        (
            "semantic",
            "semantic",
            lambda report, sidecar: report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "### Triggered\n- None",
                    "### Triggered\n- Requirement Validator (`gpt-5.6-sol / high`) - invalid",
                ),
                encoding="utf-8",
            ),
        ),
        (
            "finding",
            "finding",
            lambda report, sidecar: report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "## Detailed Findings\nNone.",
                    "## Detailed Findings\n### F-001\n- **Target**: `tests/test_retry.py:20`",
                ),
                encoding="utf-8",
            ),
        ),
    )
    for name, expected, mutate in cases:
        case_root = tmp_path / name
        case_root.mkdir()
        report, sidecar = _write_no_production_contract(case_root)
        mutate(report, sidecar)

        failures = _v4_failures(report)

        assert any(expected in message.lower() for message in failures), name


def _add_sidecar_field(sidecar, name, value):
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata[name] = value
    sidecar.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")


def _rewrite_no_production_test_as_executed(report, sidecar):
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    test_path = Path(metadata["artifacts"]["tests"]["path"])
    payload = {
        "status": "pass",
        "changedSymbols": [],
        "directTests": [],
        "affectedTests": [],
        "runs": [
            {
                "status": "pass",
                "command": ["python", "-m", "pytest"],
                "exitCode": 0,
                "counts": {"passed": 1, "failed": 0, "skipped": 0},
            }
        ],
        "advisory": None,
    }
    _rewrite_artifact(report, sidecar, "tests", test_path, payload)


def test_tc_035_v4_still_enforces_branch_build_usage_and_requirement_evidence_gates(tmp_path):
    """TC-035 / DoD-3.4: v4 evidence cannot bypass preserved Lite report gates."""
    cases = (
        (
            "branch",
            "Branch gate reports required fields",
            lambda text: text.replace("- **Source**: branch\n", "", 1),
        ),
        (
            "build",
            "Build gate rows are complete deterministic records",
            lambda text: text.replace(
                "| `repo` | PASS | `python -m unittest` | 0 | 0 | 0 | "
                "C:/repo/.CodeReview/build.log / completed |",
                "| `repo` | PASS | `python -m unittest` | 0 |",
            ),
        ),
        (
            "usage",
            "Agent Usage values are non-negative integers or exact not exposed",
            lambda text: text.replace("| 120 | not exposed | 0 | 45 |", "| -1 | not exposed | 0 | 45 |", 1),
        ),
        (
            "requirement",
            "Work-item Lite reports evidence for direct requirements",
            lambda text: text.replace(
                "| preserve retry behavior | Addressed | `src/retry.py:10` bounds retries |",
                "",
            ),
        ),
        (
            "behavior",
            "Lite reports behavior-preservation and collateral-impact evidence",
            lambda text: text.replace(
                "| retry behavior | Necessary collateral | one -> bounded | caller/event | "
                "`tests/test_retry.py:20` | Preserved |",
                "",
            ),
        ),
        (
            "collateral",
            "Lite reports Collateral Impact",
            lambda text: text.replace("- **Collateral Impact**: None\n", ""),
        ),
        (
            "scope-drift",
            "Lite reports Scope Drift",
            lambda text: text.replace("- **Scope Drift**: None\n", ""),
        ),
    )
    for name, expected, mutate in cases:
        case_root = tmp_path / name
        case_root.mkdir()
        report, *_ = _write_v4_contract(case_root)
        report.write_text(mutate(report.read_text(encoding="utf-8")), encoding="utf-8")

        failures = _v4_failures(report)

        assert expected in failures, name


def test_tc_036_accepts_consistent_blocking_test_outcomes_and_multiple_runs(tmp_path):
    """TC-036 / DoD-3.3: fail, timeout, and gap evidence are valid blocking outcomes."""
    cases = (
        (
            "fail",
            [
                {"status": "fail", "command": ["python", "-m", "pytest"], "exitCode": 1,
                 "counts": {"passed": 2, "failed": 1, "skipped": 0}},
                {"status": "pass", "command": ["python", "-m", "pytest", "tests/unit"], "exitCode": 0,
                 "counts": {"passed": 2, "failed": 0, "skipped": 0}},
            ],
        ),
        (
            "timeout",
            [{"status": "timeout", "command": ["python", "-m", "pytest"], "exitCode": 124,
              "counts": {"passed": 0, "failed": 0, "skipped": 0}}],
        ),
        ("gap", []),
    )
    for status, runs in cases:
        case_root = tmp_path / status
        case_root.mkdir()
        evidence = {
            "status": status,
            "blocking": True,
            "reasonCode": "test-gap" if status == "gap" else None,
            "changedSymbols": ["RetryPolicy.execute"],
            "directTests": ["tests/test_retry.py"],
            "affectedTests": [],
            "runs": runs,
            "advisory": None,
        }
        report, *_ = _write_v4_contract(case_root, tests=evidence)
        _route_requirement_only(report)
        report.write_text(
            report.read_text(encoding="utf-8") + f"- **Test Gate**: BLOCKED ({status})\n",
            encoding="utf-8",
        )

        assert _v4_failures(report) == [], status


def test_tc_037_rejects_malformed_test_run_status_exit_and_count_combinations(tmp_path):
    """TC-037 / DoD-3.3: every test run has internally consistent status evidence."""
    invalid_runs = (
        ("pass-with-failure", "pass", 1, {"passed": 0, "failed": 1, "skipped": 0}),
        ("fail-with-zero", "fail", 0, {"passed": 0, "failed": 1, "skipped": 0}),
        ("fail-without-count", "fail", 1, {"passed": 1, "failed": 0, "skipped": 0}),
        ("negative-count", "fail", 1, {"passed": 0, "failed": -1, "skipped": 0}),
    )
    for name, run_status, exit_code, counts in invalid_runs:
        case_root = tmp_path / name
        case_root.mkdir()
        evidence = {
            "status": run_status,
            "blocking": run_status != "pass",
            "changedSymbols": ["RetryPolicy.execute"],
            "directTests": ["tests/test_retry.py"],
            "affectedTests": [],
            "runs": [{"status": run_status, "command": ["python", "-m", "pytest"],
                      "exitCode": exit_code, "counts": counts}],
            "advisory": None,
        }
        report, *_ = _write_v4_contract(case_root, tests=evidence)
        if run_status != "pass":
            _route_requirement_only(report)

        failures = _v4_failures(report)

        assert any("test run" in message.lower() and "consistent" in message.lower() for message in failures), name


def test_tc_038_applies_missing_direct_test_advisory_only_to_changed_symbols(tmp_path):
    """TC-038 / DoD-3.3: use-unit-testing is exact, conditional, and non-blocking."""
    cases = (
        ("no-symbols", [], [], "use-unit-testing"),
        ("covered", ["RetryPolicy.execute"], ["tests/test_retry.py"], "use-unit-testing"),
        ("missing-advisory", ["RetryPolicy.execute"], [], None),
    )
    for name, symbols, direct, advisory in cases:
        case_root = tmp_path / name
        case_root.mkdir()
        evidence = {
            "status": "advisory" if advisory else "pass",
            "blocking": False,
            "changedSymbols": symbols,
            "directTests": direct,
            "affectedTests": ["tests/test_retry.py"],
            "runs": [{"status": "pass", "command": ["python", "-m", "pytest"], "exitCode": 0,
                      "counts": {"passed": 1, "failed": 0, "skipped": 0}}],
            "advisory": advisory,
        }
        report, *_ = _write_v4_contract(case_root, tests=evidence)
        if advisory:
            report.write_text(
                report.read_text(encoding="utf-8") + "- **Unit-Test Advisory**: use-unit-testing\n",
                encoding="utf-8",
            )

        failures = _v4_failures(report)

        assert any("changed symbols" in message.lower() and "direct tests" in message.lower() for message in failures), name


def test_tc_039_rejects_overlapping_duplicate_scope_buckets_and_allows_evidence_citations(tmp_path):
    """TC-039 / DoD-3.2: scope partitions are sets; only finding targets are production-only."""
    invalid_scopes = (
        {
            "status": "pass",
            "productionFiles": ["src/retry.py", "src/retry.py"],
            "evidenceFiles": ["tests/test_retry.py"],
            "excludedFiles": [],
            "files": [],
        },
        {
            "status": "pass",
            "productionFiles": ["src/retry.py"],
            "evidenceFiles": ["src/retry.py", "tests/test_retry.py"],
            "excludedFiles": ["tests/test_retry.py"],
            "files": [],
        },
    )
    for index, scope in enumerate(invalid_scopes):
        case_root = tmp_path / f"invalid-{index}"
        case_root.mkdir()
        report, *_ = _write_v4_contract(case_root, scope=scope)
        failures = _v4_failures(report)
        assert any("scope" in message.lower() and ("duplicate" in message.lower() or "overlap" in message.lower())
                   for message in failures)

    citation_root = tmp_path / "citations"
    citation_root.mkdir()
    report, *_ = _write_v4_contract(citation_root)
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "## Detailed Findings\nNone.",
            "## Detailed Findings\n### F-001\n- **Target**: `src/retry.py:10`\n"
            "- **Evidence**: `tests/test_retry.py:20`; `docs/decision.md:4`",
        ),
        encoding="utf-8",
    )
    assert _v4_failures(report) == []


def test_tc_040_cli_uses_only_inferred_or_explicit_sidecar_authority(tmp_path):
    """TC-040 / DoD-3.4: CLI removes runtime/context overrides and supports --sidecar."""
    report, sidecar, *_ = _write_v4_contract(tmp_path)
    verifier = Path(__file__).resolve().parents[1] / "verify_output.py"
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            f"- **Lite Metadata**: {sidecar}",
            "- **Lite Metadata**: n/a",
        ),
        encoding="utf-8",
    )

    help_result = subprocess.run(
        [sys.executable, str(verifier), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    explicit_result = subprocess.run(
        [sys.executable, str(verifier), str(report), "--sidecar", str(sidecar)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "--sidecar" in help_result.stdout
    assert "--expected-main-runtime" not in help_result.stdout
    assert "--context-manifest" not in help_result.stdout
    assert explicit_result.returncode == 0, explicit_result.stdout + explicit_result.stderr
