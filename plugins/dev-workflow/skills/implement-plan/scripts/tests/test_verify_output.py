#!/usr/bin/env python3
"""Representative new, old-modern, and legacy contract tests."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(VERIFY)


def plan(new=True, unit="selected", review="selected", mode="existing-method"):
    depth = "TDD" if unit == "selected" else "simplify"
    context = f"""Unit tests: {unit}
Unit tests source: user
Unit tests reason: Explicit consent for risky shared behavior.
Code review: {review}
Code review source: user
Code review reason: Explicit consent for shared contract risk.
Depth: {depth}"""
    if new:
        context = f"""Plan path origin: generated-project-root
Plan path evidence: Inline request resolves to .plans/fixture.md.
TDD recommendation: recommended
TDD recommendation reason: Runnable harness covers risky shared behavior.
TDD decision: {unit}
{context}
Code review recommendation: recommended
Code review recommendation reason: Shared contract regression needs independent review.
Code review decision: {review}"""
    task = "" if not new else f"""- Risk: risky
- Risk reason: Shared behavior may regress consumers.
- Depth: {depth}
- Mode: {mode}
- Existing-method baseline: existing suite is GREEN
- Scaffold: not applicable
"""
    qa = "| 1 | Task 1 tests | qa-engineer | scaffold and RED evidence |\n" if unit == "selected" else ""
    review_line = "- Code review: `code-review-lite`; Escalation Policy: ask\n" if review == "selected" else ""
    return f"""# Plan: Fixture

## Context
{context}

## Tasks
### Task 1: Change behavior
- Status: pending
- Depends on: none
- Files: `src/service.cs`
{task}- Description: Add defined behavior.
- Done when: Build and scoped tests pass.
- ACs: AC-1

## Agent Assignment
| Wave | Task | Agent | Verified by |
|---|---|---|---|
{qa}| 1 | Task 1 | code-implementer | working-tree-aware scoped diff and evidence; task-listed only; do not delete or move, reset, restore, checkout, stash, stage, commit, push, publish, install |

## Verification
- Build: `dotnet build`
- Existing tests: `dotnet test`
{review_line}"""


class VerifyOutputTests(unittest.TestCase):
    def clean(self, text): self.assertFalse([item for item in VERIFY.evaluate(text) if item[0] == "FAIL"])
    def test_new_selected_contract(self): self.clean(plan())
    def test_docs_skip_contract(self): self.clean(plan(unit="skipped", review="skipped"))
    def test_old_modern_real_schema_accepts_auto_selected(self):
        text = plan(new=False).replace("Unit tests source: user", "Unit tests source: auto-assessment").replace("Code review source: user", "Code review source: auto-assessment").replace("; Escalation Policy: ask", "")
        self.clean(text)
    def test_legacy_real_schema_accepts_requested(self):
        text = plan(new=False).replace("Unit tests: selected", "Unit tests: requested").replace("Code review: selected", "Code review: requested")
        text = "\n".join(line for line in text.splitlines() if " source:" not in line and " reason:" not in line)
        self.clean(text)
    def test_partial_new_shape_fails(self):
        text = plan(new=False).replace("Unit tests: selected", "Plan path origin: generated-project-root\nUnit tests: selected")
        self.assertTrue(any("missing Context field" in message for _, message in VERIFY.evaluate(text)))
    def test_new_recommendation_spelling_is_exact(self):
        self.assertTrue(any("recommendation must" in message for _, message in VERIFY.evaluate(plan().replace("not-recommended", "not recommended").replace("recommended", "not recommended", 1))))
    def test_new_selected_requires_ask(self):
        self.assertTrue(any("Escalation Policy: ask" in message for _, message in VERIFY.evaluate(plan().replace("; Escalation Policy: ask", ""))))
    def test_new_selected_requires_user_source(self):
        self.assertTrue(any("source is invalid" in message for _, message in VERIFY.evaluate(plan().replace("Unit tests source: user", "Unit tests source: auto-assessment"))))
    def test_mixed_routine_and_risky_depth(self):
        text = plan().replace("### Task 1: Change behavior", "### Task 1: Documentation\n- Status: pending\n- Depends on: none\n- Files: `docs/a.md`\n- Risk: routine\n- Risk reason: Wording only.\n- Depth: simplify\n- Mode: simple-new\n- Existing-method baseline: not applicable\n- Scaffold: not applicable\n- Description: Update wording.\n- Done when: Static check passes.\n- ACs: AC-0\n\n### Task 2: Change behavior")
        self.clean(text)
    def test_backbone_semantics_required(self):
        text = plan(mode="complex-backbone")
        self.assertTrue(any("complex-backbone" in message for _, message in VERIFY.evaluate(text)))
    def test_safety_required_for_new_shape(self):
        self.assertTrue(any("delegation safety" in message for _, message in VERIFY.evaluate(plan().replace("working-tree-aware", "baseline"))))
    def test_placeholder_cli_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.md"; path.write_text(plan().replace("defined behavior", "TBD"), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(1, result.returncode); self.assertIn("placeholder", result.stdout)


if __name__ == "__main__": unittest.main()
