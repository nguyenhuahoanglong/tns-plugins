import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def write_case(root, profile, classifier, triggered, requirement_mode, gate_status="PASS"):
    risk_text = " | ".join(classifier["riskTriggers"]) or "None"
    specialist_text = " | ".join(
        f"{reviewer}={trigger}"
        for reviewer, triggers in classifier["specialistTriggers"].items()
        for trigger in triggers
    ) or "None"
    runtime = {
        "main": "gpt-test / high",
        "build": "gpt-5.4-mini / low",
        "requirement": "inherited current model / high",
        "specialists": "inherited current model / medium",
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
            "**Skill**: code-review-pro v2.1.1",
            f"**Review Profile**: {profile}",
            "**Main Runtime**: gpt-test / high",
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
        "skillVersion": "2.1.1",
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
    "Docs-only": ALL_CHILDREN,
    "Tiny": TINY_SKIPS,
    "Pro": [
        "Performance Reviewer(no performance trigger)",
        "Philosophy Reviewer(no design trigger)",
        "Standard Reviewer(no standards trigger)",
    ],
}


class VerifyOutputTests(unittest.TestCase):
    def test_docs_only_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Docs-only",
                {"filesChanged": 1, "changedLines": 10, "docsOnly": True, "riskTriggers": [], "specialistTriggers": {}},
                ["Main(docs-only inline)"], "not-applicable",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertFalse([item for item in results if item[0] == "FAIL"])

    def test_tiny_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 2, "changedLines": 80, "docsOnly": False, "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertFalse([item for item in results if item[0] == "FAIL"])

    def test_docs_only_rejects_child_agents_except_branch_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Docs-only",
                {"filesChanged": 1, "changedLines": 10, "docsOnly": True, "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(docs-only inline)",
                    "Build Validator[repo](gpt-5.4-mini / low; invalid)",
                ],
                "not-applicable",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "optional branch gate only" in message
                for level, message in results if level == "FAIL"
            ))

    def test_pro_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertFalse([item for item in results if item[0] == "FAIL"])

    def test_expected_main_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
            )
            results = VERIFY.evaluate(report, sidecar, "gpt-test / high")
            self.assertFalse([item for item in results if item[0] == "FAIL"])
            mismatch = VERIFY.evaluate(report, sidecar, "gpt-other / low")
            self.assertTrue(any(
                "matches expected launch runtime" in message
                for level, message in mismatch if level == "FAIL"
            ))

    def test_branch_gate_skipped_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
                gate_status="SKIPPED",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertFalse([item for item in results if item[0] == "FAIL"])

    def test_branch_gate_report_sidecar_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
            )
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["branchWorkItemGate"]["status"] = "FAIL"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "Branch Work Item Gate report fields match sidecar" in message
                for level, message in results if level == "FAIL"
            ))

    def test_branch_gate_requires_build_runtime_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": [], "specialistTriggers": {}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
            )
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "Branch Work Item Gate(gpt-5.4-mini / low; branch work item convention)",
                    "Branch Work Item Gate(gpt-other / low; branch work item convention)",
                ),
                encoding="utf-8",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "Triggered report records match sidecar" in message
                for level, message in results if level == "FAIL"
            ))

    def test_pro_requires_requirement_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["api-contract"],
                 "specialistTriggers": {"Philosophy Reviewer": ["api-contract"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; inline)",
                    "Security Reviewer(inherited current model / medium; auth)",
                ],
                "inline",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any("requirement mode" in message for level, message in results if level == "FAIL"))

    def test_tiny_rejects_risk_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Tiny",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Main(Tiny all-lens)",
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                ],
                "inline",
            )
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any("Tiny obeys" in message for level, message in results if level == "FAIL"))


    def test_pr_merge_preview_strategy_valid(self):
        """pr scope with valid mergePreviewStrategy → no failures."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            # Override sidecar to use pr scopeType + server-merge
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["scopeType"] = "pr"
            data["mergePreviewStrategy"] = "server-merge"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            results = VERIFY.evaluate(report, sidecar)
            self.assertFalse([item for item in results if item[0] == "FAIL"])

    def test_pr_requires_merge_preview_strategy(self):
        """pr scope with missing/invalid mergePreviewStrategy → FAIL mentioning mergePreviewStrategy."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["scopeType"] = "pr"
            data["mergePreviewStrategy"] = "invalid-value"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "mergePreviewStrategy" in message
                for level, message in results if level == "FAIL"
            ))

    def test_pr_only_requires_pr_scope(self):
        """prOnlyMode=true with scopeType=branch → FAIL mentioning PR-only."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["prOnlyMode"] = True
            # scopeType remains "branch" (not "pr") → should fail
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "PR-only" in message
                for level, message in results if level == "FAIL"
            ))

    def test_js_deps_skip_requires_build_row(self):
        """jsDepsStrategy=skip with no JS-SKIPPED build row → FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            data["jsDepsStrategy"] = "skip"
            sidecar.write_text(json.dumps(data), encoding="utf-8")
            # Report has no JS-SKIPPED row in Build Status
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "JS-SKIPPED" in message
                for level, message in results if level == "FAIL"
            ))

    def test_scope_drift_required_for_pro(self):
        """Pro report missing Scope Drift marker → FAIL."""
        import re as _re
        with tempfile.TemporaryDirectory() as tmp:
            report, sidecar = write_case(
                Path(tmp), "Pro",
                {"filesChanged": 1, "changedLines": 20, "docsOnly": False,
                 "riskTriggers": ["auth-security-boundary"],
                 "specialistTriggers": {"Security Reviewer": ["auth-security-boundary"]}},
                [
                    "Build Validator[repo](gpt-5.4-mini / low; code build)",
                    "Requirement Validator(inherited current model / high; work-item)",
                    "Security Reviewer(inherited current model / medium; auth-security-boundary)",
                ],
                "work-item",
            )
            # Strip out Scope Drift marker
            text = report.read_text(encoding="utf-8")
            text = _re.sub(r"### Scope Drift\s*", "", text)
            text = _re.sub(r"- \*\*Scope Drift\*\*: None\s*", "", text)
            report.write_text(text, encoding="utf-8")
            results = VERIFY.evaluate(report, sidecar)
            self.assertTrue(any(
                "Scope Drift" in message
                for level, message in results if level == "FAIL"
            ))


if __name__ == "__main__":
    unittest.main()
