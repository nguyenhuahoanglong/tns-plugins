"""Spec-first tests for the code-review-lite v3 report verifier.

Requirement mapping:
- AC-1 profiles: Docs/Code Tiny, Lite, branch failure, build failure/gap.
- AC-5 gates: deterministic gate records, no gate-as-agent, build-row parity.
- AC-5 agents: triggered/usage parity and exact token visibility values.
- AC-3/AC-5 evidence: Lite behavior preservation and collateral impact.
"""

import json
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


def write_report(
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
    """Write one otherwise-valid v3 report with selected contract variations."""
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


class VerifyOutputV3Tests(unittest.TestCase):
    def failures(self, path, profile):
        return [
            message
            for level, message in evaluate(
                path, profile, "gpt-5.6-sol / xhigh"
            )
            if level == "FAIL"
        ]

    def assert_valid(self, path, profile):
        self.assertEqual([], self.failures(path, profile))

    def assert_contract_failure(self, path, profile, expected_message):
        self.assertIn(expected_message, self.failures(path, profile))

    # AC-1: profile child counts and deterministic-gate routing.
    def test_docs_tiny_accepts_zero_semantic_agents(self):
        with tempfile.TemporaryDirectory() as root:
            self.assert_valid(write_report(root, "Docs Tiny"), "Docs Tiny")

    def test_docs_tiny_rejects_semantic_agent(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Docs Tiny", triggered=["Requirement Validator"])
            self.assert_contract_failure(
                path, "Docs Tiny", "Docs Tiny triggers zero semantic agents"
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
                "Non-doc profiles report deterministic build gate rows",
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
                "Lite passing builds trigger every selected semantic agent",
            )

    def test_lite_rejects_missing_requirement_validator(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(root, "Lite", triggered=["Performance Reviewer"])
            self.assert_contract_failure(
                path, "Lite", "Lite triggers the mandatory Requirement Validator"
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
                path, "Lite", "Lite triggers at most one named specialist"
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
                path, "Lite", "Lite build failure triggers Requirement Validator only"
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
                path, "Lite", "Lite build gap triggers Requirement Validator only"
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

    def test_lite_accepts_build_rows_matching_context_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_valid(path, "Lite")

    def test_lite_rejects_fabricated_build_row_not_in_context_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            fabricated = (
                "repo",
                "PASS WITH WARNINGS",
                "python -m unittest",
                "0",
                "0",
                "1",
                "C:/repo/.CodeReview/build.log / fabricated warning",
            )
            path = write_report(
                root,
                "Lite",
                build_rows=[fabricated],
                manifest_build_rows=[DEFAULT_BUILD_ROW],
                triggered=["Requirement Validator", "Performance Reviewer"],
            )
            self.assert_contract_failure(
                path, "Lite", "Build gate rows match context manifest"
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
            path = write_report(root, "Docs Tiny")
            path.write_text(
                path.read_text(encoding="utf-8").replace("3.0.0", "2.2.0"),
                encoding="utf-8",
            )
            self.assert_contract_failure(
                path, "Docs Tiny", "Skill is exactly code-review-lite v3.0.0"
            )


if __name__ == "__main__":
    unittest.main()
