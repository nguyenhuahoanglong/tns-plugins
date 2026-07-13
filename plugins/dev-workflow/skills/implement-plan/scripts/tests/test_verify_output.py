#!/usr/bin/env python3
"""Representative contract tests for implement-plan output verifier."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def plan(unit="selected", review="selected"):
    depth = "TDD" if unit == "selected" else "simplify"
    qa = "| pre-1 | tests | qa-engineer | scaffold tests red |\n" if unit == "selected" else ""
    review_line = "- Code review: code-review-lite\n" if review == "selected" else ""
    return f"""# Plan: Fixture

## Context
Unit tests: {unit}
Unit tests source: auto-assessment
Unit tests reason: Target service has meaningful seams and runnable xUnit harness.
Code review: {review}
Code review source: auto-assessment
Code review reason: Change affects shared production service.
Depth: {depth}

## Tasks
### Task 1: Change behavior
- Status: pending
- Depends on: none
- Files: `src/service.cs`
- Description: Add defined behavior.
- Done when: Build and scoped tests pass.
- ACs: AC-1

## Agent Assignment
| Wave | Task | Agent | Verified by |
|---|---|---|---|
{qa}| 1 | Task 1 | code-implementer | diff and evidence |

## Verification
- Build: `dotnet build`
- Existing tests: `dotnet test`
{review_line}"""


class VerifyOutputTests(unittest.TestCase):
    def assert_clean(self, text):
        self.assertFalse([item for item in VERIFY.evaluate(text) if item[0] == "FAIL"])

    def test_modern_selected_contract(self):
        self.assert_clean(plan())

    def test_modern_skipped_contract(self):
        self.assert_clean(plan("skipped", "skipped"))

    def test_complete_legacy_contract(self):
        text = plan().replace("Unit tests: selected", "Unit tests: requested")
        text = text.replace("Code review: selected", "Code review: requested")
        text = "\n".join(line for line in text.splitlines() if " source:" not in line and " reason:" not in line)
        self.assert_clean(text)

    def test_inconsistent_depth_fails(self):
        failures = VERIFY.evaluate(plan().replace("Depth: TDD", "Depth: simplify"))
        self.assertTrue(any("Depth must be TDD" in message for _, message in failures))

    def test_task_prose_does_not_replace_agent_assignment(self):
        text = plan().replace("## Agent Assignment", "## Dispatch Notes")
        text = text.replace("Add defined behavior.", "Use qa-engineer and scaffold before work.")
        failures = VERIFY.evaluate(text)
        self.assertTrue(any("require ## Agent Assignment" in message for _, message in failures))

    def test_names_only_in_task_prose_do_not_satisfy_sections(self):
        text = plan().replace("| pre-1 | tests | qa-engineer | scaffold tests red |\n", "")
        text = text.replace("- Code review: code-review-lite\n", "")
        text = text.replace(
            "Add defined behavior.", "Mention qa-engineer, scaffold, and code-review-lite here only."
        )
        failures = VERIFY.evaluate(text)
        messages = "\n".join(message for _, message in failures)
        self.assertIn("qa-engineer assignment", messages)
        self.assertIn("scaffold evidence", messages)
        self.assertIn("code-review-lite in Verification", messages)

    def test_plain_todo_and_undecided_fail(self):
        failures = VERIFY.evaluate(plan().replace("Add defined behavior.", "TODO and undecided"))
        messages = "\n".join(message for _, message in failures)
        self.assertIn("task-decision marker", messages)
        self.assertIn("undecided marker", messages)

    def test_cli_rejects_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "plan.md"
            fixture.write_text(plan().replace("Add defined behavior.", "TBD"), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(fixture)], capture_output=True, text=True, check=False
            )
            self.assertEqual(1, completed.returncode)
            self.assertIn("placeholder/vague text detected", completed.stdout)


if __name__ == "__main__":
    unittest.main()
