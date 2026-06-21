import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def write_case(root, profile, classifier, triggered, requirement_mode):
    risk_text = " | ".join(classifier["riskTriggers"]) or "None"
    specialist_text = " | ".join(
        f"{reviewer}={trigger}"
        for reviewer, triggers in classifier["specialistTriggers"].items()
        for trigger in triggers
    ) or "None"
    report = root / "feature.md"
    report.write_text(
        "\n".join([
            "# Code Review: Test",
            "",
            "**Skill**: code-review-pro v2.0.0",
            f"**Review Profile**: {profile}",
            "**Main Runtime**: gpt-test / high",
            "**Agents Triggered**: None" if not triggered else f"**Agents Triggered**: {' | '.join(triggered)}",
            f"**Agents Skipped**: {' | '.join(SKIPPED[profile]) if SKIPPED[profile] else 'None'}",
            "",
            "## Review Classification",
            f"- **Files Changed**: {classifier['filesChanged']}",
            f"- **Changed Lines**: {classifier['changedLines']}",
            f"- **Docs Only**: {str(classifier['docsOnly']).lower()}",
            f"- **Risk Triggers**: {risk_text}",
            "- **Risk Evidence**: None",
            f"- **Specialist Triggers**: {specialist_text}",
            "## Build Status",
            "Test.",
            "## Requirement Validation",
            "Test.",
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
        "skillVersion": "2.0.0",
        "reviewProfile": profile,
        "reviewKind": "initial",
        "classifier": classifier,
        "runtime": {
            "main": "gpt-test / high",
            "build": "gpt-5.4-mini / low",
            "requirement": "inherited current model / high",
            "specialists": "inherited current model / medium",
        },
        "triggered": triggered,
        "skipped": SKIPPED[profile],
        "reposReviewed": [] if profile == "Docs-only" else ["repo"],
        "requirementMode": requirement_mode,
        "scopeType": "branch",
        "scopeBase": "origin/main",
        "diffFingerprint": "sha256:abc123",
        "reviewedCommit": "abc123",
        "targetBranch": "main",
        "workItemId": 123 if requirement_mode == "work-item" else None,
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

    def test_docs_only_requires_zero_agents(self):
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
            self.assertTrue(any("zero child agents" in message for level, message in results if level == "FAIL"))

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


if __name__ == "__main__":
    unittest.main()
