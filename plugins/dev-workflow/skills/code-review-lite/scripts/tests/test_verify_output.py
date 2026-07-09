import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_output import evaluate  # noqa: E402


def write_report(root, profile, triggered, skipped, gate_status="PASS"):
    classification = {
        "Docs Tiny": (7, 500, "true", "None", "None"),
        "Code Tiny": (1, 42, "false", "None", "None"),
        "Lite": (
            6,
            200,
            "false",
            "async-lifecycle",
            "Performance Reviewer=async-lifecycle",
        ),
    }[profile]
    path = Path(root) / "feature.lite.md"
    gate = {
        "Status": gate_status,
        "Branch": "US/123-valid-branch" if gate_status != "SKIPPED" else "None",
        "Prefix": "US" if gate_status != "SKIPPED" else "None",
        "Work Item ID": "123" if gate_status != "SKIPPED" else "None",
        "Expected Type": "User Story" if gate_status != "SKIPPED" else "None",
        "Actual Type": "User Story" if gate_status == "PASS" else "None",
        "Title": "Valid story" if gate_status == "PASS" else "None",
        "State": "Active" if gate_status == "PASS" else "None",
        "Source": "branch" if gate_status != "SKIPPED" else "working",
        "Reason": "Branch prefix and ADO work item type match"
        if gate_status == "PASS"
        else ("Scope has no created PR or branch to validate"
              if gate_status == "SKIPPED"
              else "ADO work item type does not match branch prefix"),
    }
    if gate_status == "WARN":
        gate.update({
            "Branch": "hotfix/123",
            "Prefix": "hotfix",
            "Work Item ID": "123",
            "Expected Type": "None",
            "Actual Type": "User Story",
            "Title": "Valid story",
            "State": "Active",
            "Reason": "Branch prefix is not US, BUG, or ISSUE; ADO work item ID is valid",
        })
    branch_trigger = "Branch Work Item Gate(gpt-5.4-mini / low; branch work item convention)"
    if gate_status == "SKIPPED":
        skipped = f"{skipped}; Branch Work Item Gate(no created PR or branch scope)"
    elif triggered == "None":
        triggered = branch_trigger
    else:
        triggered = f"{branch_trigger}; {triggered}"
    path.write_text(
        "\n".join(
            (
                "# Code Review (Lite): Test",
                "",
                "**Skill**: code-review-lite v2.2.0",
                f"**Review Profile**: {profile}",
                "**Main Runtime**: gpt-test / high",
                f"**Agents Triggered**: {triggered}",
                f"**Agents Skipped**: {skipped}",
                "",
                "## Classification",
                "",
                f"- **Files Changed**: {classification[0]}",
                f"- **Changed Lines**: {classification[1]}",
                f"- **Documentation Only**: {classification[2]}",
                f"- **Risk Triggers**: {classification[3]}",
                f"- **Specialist Triggers**: {classification[4]}",
                "- **Decision**: fixture",
                "",
                "## Branch Work Item Gate",
                "",
                f"- **Status**: {gate['Status']}",
                f"- **Branch**: {gate['Branch']}",
                f"- **Prefix**: {gate['Prefix']}",
                f"- **Work Item ID**: {gate['Work Item ID']}",
                f"- **Expected Type**: {gate['Expected Type']}",
                f"- **Actual Type**: {gate['Actual Type']}",
                f"- **Title**: {gate['Title']}",
                f"- **State**: {gate['State']}",
                f"- **Source**: {gate['Source']}",
                f"- **Reason**: {gate['Reason']}",
                "",
                "## Build Status",
                "",
                "| Repo | Status | Errors | Warnings |",
                "|---|---|---:|---:|",
                "| `repo` | PASS | 0 | 0 |",
                "",
                "## Requirement Evidence",
                "",
                "| Requirement | Status | Evidence |",
                "|---|---|---|",
                "",
                "### Scope Drift",
                "",
                "- **Scope Drift**: None",
            )
        ),
        encoding="utf-8",
    )
    return path


class VerifyOutputTests(unittest.TestCase):
    def assert_valid(self, path, profile):
        failures = [message for level, message in evaluate(path, profile) if level == "FAIL"]
        self.assertEqual([], failures)

    def test_docs_tiny(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Docs Tiny",
                "None",
                "Build Validator(docs-only); Requirement Validator(docs-only); "
                "Security Reviewer(docs-only); Performance Reviewer(docs-only); "
                "Philosophy Reviewer(docs-only); Standard Reviewer(docs-only)",
            )
            self.assert_valid(path, "Docs Tiny")

    def test_code_tiny(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Code Tiny",
                "Build Validator[repo](gpt-5.4-mini / low; code build)",
                "Requirement Validator(Code Tiny); Security Reviewer(Code Tiny); "
                "Performance Reviewer(Code Tiny); Philosophy Reviewer(Code Tiny); Standard Reviewer(Code Tiny)",
            )
            self.assert_valid(path, "Code Tiny")

    def test_lite_one_specialist(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            self.assert_valid(path, "Lite")

    def test_rejects_wrong_version(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Docs Tiny",
                "None",
                "Build Validator; Requirement Validator; Security Reviewer; "
                "Performance Reviewer; Philosophy Reviewer; Standard Reviewer",
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace("2.2.0", "1.0.0"),
                encoding="utf-8",
            )
            failures = [message for level, message in evaluate(path) if level == "FAIL"]
            self.assertIn("Skill is exactly code-review-lite v2.2.0", failures)

    def test_expected_main_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Docs Tiny",
                "None",
                "Build Validator(docs-only); Requirement Validator(docs-only); "
                "Security Reviewer(docs-only); Performance Reviewer(docs-only); "
                "Philosophy Reviewer(docs-only); Standard Reviewer(docs-only)",
            )
            failures = [
                message for level, message in evaluate(
                    path, "Docs Tiny", "gpt-test / high"
                ) if level == "FAIL"
            ]
            self.assertEqual([], failures)
            mismatch = evaluate(path, "Docs Tiny", "gpt-other / low")
            self.assertTrue(any(
                "matches expected launch runtime" in message
                for level, message in mismatch if level == "FAIL"
            ))

    def test_branch_gate_skipped_valid(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Code Tiny",
                "Build Validator[repo](gpt-5.4-mini / low; code build)",
                "Requirement Validator(Code Tiny); Security Reviewer(Code Tiny); "
                "Performance Reviewer(Code Tiny); Philosophy Reviewer(Code Tiny); Standard Reviewer(Code Tiny)",
                gate_status="SKIPPED",
            )
            self.assert_valid(path, "Code Tiny")

    def test_branch_gate_warn_valid(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Code Tiny",
                "Build Validator[repo](gpt-5.4-mini / low; code build)",
                "Requirement Validator(Code Tiny); Security Reviewer(Code Tiny); "
                "Performance Reviewer(Code Tiny); Philosophy Reviewer(Code Tiny); Standard Reviewer(Code Tiny)",
                gate_status="WARN",
            )
            self.assert_valid(path, "Code Tiny")

    def test_branch_gate_requires_lightweight_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Code Tiny",
                "Build Validator[repo](gpt-5.4-mini / low; code build)",
                "Requirement Validator(Code Tiny); Security Reviewer(Code Tiny); "
                "Performance Reviewer(Code Tiny); Philosophy Reviewer(Code Tiny); Standard Reviewer(Code Tiny)",
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Branch Work Item Gate(gpt-5.4-mini / low; branch work item convention)",
                    "Branch Work Item Gate(gpt-other / low; branch work item convention)",
                ),
                encoding="utf-8",
            )
            failures = [message for level, message in evaluate(path, "Code Tiny") if level == "FAIL"]
            self.assertIn("Branch Work Item Gate uses same runtime as Build Validator", failures)


    def test_lite_scope_drift_required(self):
        """Lite report without Scope Drift marker → FAIL."""
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            # Strip out Scope Drift marker from the fixture
            import re as _re
            text = path.read_text(encoding="utf-8")
            text = _re.sub(r"### Scope Drift\s*", "", text)
            text = _re.sub(r"- \*\*Scope Drift\*\*: None\s*", "", text)
            path.write_text(text, encoding="utf-8")
            failures = [message for level, message in evaluate(path, "Lite") if level == "FAIL"]
            self.assertIn(
                "Lite report contains Scope Drift marker (### Scope Drift heading or - **Scope Drift**: bullet)",
                failures,
            )

    def test_js_skipped_build_row_counts(self):
        """A JS-SKIPPED build row satisfies repo/build parity for Lite."""
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            # Replace the PASS row with a JS-SKIPPED row
            text = path.read_text(encoding="utf-8")
            text = text.replace("| `repo` | PASS | 0 | 0 |", "| `repo` | JS-SKIPPED | 0 | 0 |")
            path.write_text(text, encoding="utf-8")
            failures = [message for level, message in evaluate(path, "Lite") if level == "FAIL"]
            self.assertNotIn("Lite triggers one Build Validator runtime per repo", failures)

    def test_not_run_environment_build_row_counts(self):
        """A 'NOT RUN (environment)' build row satisfies repo/build parity for Lite."""
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "| `repo` | PASS | 0 | 0 |", "| `repo` | NOT RUN (environment) | 0 | 0 |"
            )
            path.write_text(text, encoding="utf-8")
            failures = [message for level, message in evaluate(path, "Lite") if level == "FAIL"]
            self.assertNotIn("Lite triggers one Build Validator runtime per repo", failures)

    def test_js_skipped_install_failed_build_row_counts(self):
        """A 'JS-SKIPPED (install failed)' build row satisfies repo/build parity for Lite."""
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "| `repo` | PASS | 0 | 0 |", "| `repo` | JS-SKIPPED (install failed) | 0 | 0 |"
            )
            path.write_text(text, encoding="utf-8")
            failures = [message for level, message in evaluate(path, "Lite") if level == "FAIL"]
            self.assertNotIn("Lite triggers one Build Validator runtime per repo", failures)

    def test_pass_with_warnings_still_counts_after_reorder(self):
        """Reordering alternation to put PASS WITH WARNINGS before PASS must not break it."""
        with tempfile.TemporaryDirectory() as root:
            path = write_report(
                root,
                "Lite",
                "Build Validator[repo](gpt-5.4-mini / low; repo); "
                "Requirement Validator(inherited current model / high; non-Tiny Lite); "
                "Performance Reviewer(inherited current model / medium; async lifecycle)",
                "None",
            )
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "| `repo` | PASS | 0 | 0 |", "| `repo` | PASS WITH WARNINGS | 0 | 1 |"
            )
            path.write_text(text, encoding="utf-8")
            failures = [message for level, message in evaluate(path, "Lite") if level == "FAIL"]
            self.assertNotIn("Lite triggers one Build Validator runtime per repo", failures)


if __name__ == "__main__":
    unittest.main()
