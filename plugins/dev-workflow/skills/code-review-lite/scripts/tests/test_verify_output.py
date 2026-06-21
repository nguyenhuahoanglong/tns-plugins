import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_output import evaluate  # noqa: E402


def write_report(root, profile, triggered, skipped):
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
    path.write_text(
        "\n".join(
            (
                "# Code Review (Lite): Test",
                "",
                "**Skill**: code-review-lite v2.0.0",
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
                path.read_text(encoding="utf-8").replace("2.0.0", "1.0.0"),
                encoding="utf-8",
            )
            failures = [message for level, message in evaluate(path) if level == "FAIL"]
            self.assertIn("Skill is exactly code-review-lite v2.0.0", failures)

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


if __name__ == "__main__":
    unittest.main()
