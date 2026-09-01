#!/usr/bin/env python3
"""Contract, preflight-consistency, and normalization tests for the v4 plan verifier."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "verify_output.py"
SPEC = importlib.util.spec_from_file_location("verify_output", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)

SAFETY = ("Delegation is working-tree-aware with scoped diff comparison: agents write only task-listed "
          "files, never delete or move files, never git reset, restore, or checkout, and never stash, "
          "stage, commit, push, publish, or install anything.")


def plan(unit="selected", review="selected", context=None, preflight=None, tasks=None, assignment=None,
         verification=None):
    context = context if context is not None else f"""Plan path: .plans/fixture.md
Plan path origin: generated-project-root
Plan path evidence: Inline request resolves to .plans/fixture.md.
Unit tests: {unit}
Unit tests source: user
Unit tests reason: Explicit consent for shared behavior.
Code review: {review}
Code review source: flag
Code review reason: Invoked with --review."""
    preflight = preflight if preflight is not None else """
| ID | Kind | Target | Expect | Blocks |
|---|---|---|---|---|
| PF-1 | command | `python` | resolves on PATH | Task 1 |

### Preflight results
Run: 2026-09-01T00:00:00Z scripts/preflight.py
- PF-1 ready: C:\\Python\\python.exe
- derived path Task 1 `src/cache.ts` ready: file exists
Autonomy: verified-ready"""
    depth = "" if unit != "selected" else """- Depth: TDD
- TDD reason: Shared export behavior regressed twice before.
- Existing-method baseline: npm test is GREEN at 214 passing.
"""
    tasks = tasks if tasks is not None else f"""
### Task 1: Harden the export path
- Status: pending
- Depends on: none
- Files: `src/cache.ts`
- Mode: existing-method
{depth}- Description: Return an empty CSV header row when the report has no rows.
- Done when: npm test -- cache.spec.ts passes with the new empty-report case.
- ACs: AC-1"""
    assignment = assignment if assignment is not None else (
        "\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
        "| 1 | Task 1 | qa-engineer then code-implementer | RED then GREEN plus diff |")
    review_line = "- Code review: `code-review-lite` over changed files, `Escalation Policy: ask`\n" if review == "selected" else ""
    verification = verification if verification is not None else (
        "\n- Build: `npm run build`\n- Existing tests: `npm test`\n" + review_line)
    return f"""# Plan: Fixture

## Context
{context}

## Goal
Empty reports export a header-only CSV.

## Global Constraints
{SAFETY}

## Acceptance Criteria
- [ ] AC-1: Exporting an empty report yields a CSV with only the header row.

## Preflight
{preflight}

## Tasks
{tasks}

## Agent Assignment
{assignment}

## Verification
{verification}
"""


def levels(text, plan_path=None):
    return [level for level, _ in VERIFY.evaluate(text, plan_path)]


def messages(text, plan_path=None):
    return " | ".join(message for level, message in VERIFY.evaluate(text, plan_path) if level != "PASS")


class TestHappyPath(unittest.TestCase):
    def test_compliant_plan_has_no_fail_or_block(self):
        self.assertNotIn("FAIL", levels(plan()), messages(plan()))
        self.assertNotIn("BLOCK", levels(plan()))

    def test_review_only_plan_needs_no_depth_field(self):
        text = plan(unit="skipped")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "plan.md"
            path.write_text(plan(), encoding="utf-8")
            self.assertEqual(VERIFY.main([str(path)]), 0)


class TestContextContract(unittest.TestCase):
    def test_missing_field_fails(self):
        text = plan().replace("Unit tests source: user\n", "")
        self.assertIn("missing Context field: Unit tests source", messages(text))

    def test_origin_and_evidence_must_agree(self):
        text = plan().replace("Plan path evidence: Inline request resolves to .plans/fixture.md.",
                              "Plan path evidence: nothing in particular")
        self.assertIn("generated path origin requires .plans evidence", messages(text))

    def test_host_plan_mode_must_name_its_draft(self):
        good = plan().replace("Plan path origin: generated-project-root", "Plan path origin: host-plan-mode") \
                     .replace("Plan path evidence: Inline request resolves to .plans/fixture.md.",
                              "Plan path evidence: promoted from C:/Users/LN/.claude/plans/draft-1.md")
        self.assertNotIn("FAIL", levels(good), messages(good))
        bad = good.replace("promoted from C:/Users/LN/.claude/plans/draft-1.md", "promoted from a host draft")
        self.assertIn("host-plan-mode origin must name the host draft", messages(bad))

    def test_source_must_be_user_or_flag(self):
        text = plan().replace("Unit tests source: user", "Unit tests source: auto-assessment")
        self.assertNotIn("FAIL", levels(text), messages(text))
        text = plan().replace("Unit tests source: user", "Unit tests source: guessed")
        self.assertIn("Unit tests source must be user or flag", messages(text))


class TestNormalization(unittest.TestCase):
    def test_legacy_requested_flags_are_accepted(self):
        legacy = """Plan path: .plans/legacy.md
Plan path origin: generated-project-root
Plan path evidence: Inline request resolves to .plans/legacy.md.
Unit tests: requested
Code review: requested"""
        text = plan(context=legacy)
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_pre_v4_context_normalizes_without_fail(self):
        old = """Plan path origin: generated-project-root
Plan path evidence: Inline request resolves to .plans/old.md.
TDD recommendation: recommended
TDD recommendation reason: Runnable harness covers risky shared behavior.
TDD decision: selected
Unit tests: selected
Unit tests source: auto-assessment
Unit tests reason: Assessed as risky.
Code review recommendation: recommended
Code review recommendation reason: Shared contract regression.
Code review decision: selected
Code review: selected
Code review source: user
Code review reason: User selected review.
Depth: TDD"""
        text = plan(context=old)
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_pre_v4_task_risk_reason_satisfies_the_tdd_reason_rule(self):
        text = plan().replace("- TDD reason: Shared export behavior regressed twice before.",
                              "- Risk: risky\n- Risk reason: Shared export behavior regressed twice before.")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_missing_origin_is_treated_as_existing_input(self):
        text = plan(unit="skipped", review="skipped", context="""Plan path: .plans/bare.md
Unit tests: skipped
Unit tests source: user
Unit tests reason: Declined.
Code review: skipped
Code review source: user
Code review reason: Declined.""")
        self.assertNotIn("FAIL", levels(text, Path(".plans/bare.md")), messages(text, Path(".plans/bare.md")))


class TestTaskContract(unittest.TestCase):
    def test_mode_is_required_at_every_depth(self):
        text = plan(unit="skipped").replace("- Mode: existing-method\n", "")
        self.assertIn("missing Task 1 field: Mode", messages(text))

    def test_tdd_depth_requires_selected_unit_tests(self):
        text = plan(unit="skipped").replace("- Mode: existing-method",
                                            "- Mode: existing-method\n- Depth: TDD\n- TDD reason: risky")
        self.assertIn("Depth TDD requires Unit tests: selected", messages(text))

    def test_tdd_depth_requires_a_reason(self):
        text = plan().replace("- TDD reason: Shared export behavior regressed twice before.\n", "")
        self.assertIn("requires a non-empty TDD reason", messages(text))

    def test_existing_method_tdd_requires_a_baseline(self):
        text = plan().replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertIn("requires Existing-method baseline", messages(text))

    def test_simple_new_tdd_requires_a_scaffold(self):
        text = plan().replace("- Mode: existing-method", "- Mode: simple-new") \
                     .replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertIn("simple-new TDD requires Scaffold", messages(text))

    def test_complex_backbone_semantics_must_be_present(self):
        text = plan().replace("- Mode: existing-method", "- Mode: complex-backbone") \
                     .replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertIn("complex-backbone semantics are incomplete", messages(text))

    def test_invalid_status_fails(self):
        text = plan().replace("- Status: pending", "- Status: nearly-done")
        self.assertIn("Task 1 Status is invalid", messages(text))


class TestPreflightContract(unittest.TestCase):
    def test_missing_section_fails(self):
        text = plan().replace("## Preflight", "## Prelaunch")
        self.assertIn("missing ## Preflight section", messages(text))

    def test_unknown_kind_fails(self):
        text = plan().replace("| PF-1 | command |", "| PF-1 | sudo |")
        self.assertIn("unknown probe kind", messages(text))

    def test_row_must_name_an_existing_task(self):
        text = plan().replace("| resolves on PATH | Task 1 |", "| resolves on PATH | Task 9 |")
        self.assertIn("blocks Task 9, which does not exist", messages(text))

    def test_declared_row_needs_a_recorded_result(self):
        text = plan().replace("- PF-1 ready: C:\\Python\\python.exe\n", "")
        self.assertIn("PF-1 has no recorded preflight result", messages(text))

    def test_derived_file_probe_needs_a_recorded_result(self):
        text = plan().replace("- derived path Task 1 `src/cache.ts` ready: file exists\n", "")
        self.assertIn("missing recorded result for derived path Task 1", messages(text))

    def test_run_line_is_required(self):
        text = plan().replace("Run: 2026-09-01T00:00:00Z scripts/preflight.py\n", "")
        self.assertIn("need a Run: line", messages(text))

    def test_unverifiable_requires_a_fallback(self):
        rows = plan().replace("| PF-1 | command | `python` | resolves on PATH | Task 1 |",
                              "| PF-1 | command | `python` | resolves on PATH | Task 1 |\n"
                              "| PF-2 | manual | MCP list-tables | returns rows | Task 1 |")
        bare = rows.replace("- PF-1 ready: C:\\Python\\python.exe",
                            "- PF-1 ready: C:\\Python\\python.exe\n- PF-2 unverifiable: manual probe") \
                   .replace("Autonomy: verified-ready", "Autonomy: unverifiable-with-fallback")
        self.assertIn("unverifiable without a Fallback", messages(bare))
        withfallback = bare.replace("- PF-2 unverifiable: manual probe",
                                    "- PF-2 unverifiable: manual probe - Fallback: Task 1 stops and is "
                                    "marked blocked; never prompt.")
        self.assertNotIn("FAIL", levels(withfallback), messages(withfallback))

    def test_autonomy_must_match_the_recorded_results(self):
        text = plan().replace("- PF-1 ready: C:\\Python\\python.exe",
                              "- PF-1 blocked: python does not resolve on PATH")
        self.assertIn("recorded results aggregate to verified-blocked", messages(text))

    def test_verified_blocked_is_a_block_not_a_fail(self):
        text = plan().replace("- PF-1 ready: C:\\Python\\python.exe",
                              "- PF-1 blocked: python does not resolve on PATH") \
                     .replace("Autonomy: verified-ready", "Autonomy: verified-blocked")
        result = levels(text)
        self.assertNotIn("FAIL", result, messages(text))
        self.assertIn("BLOCK", result)

    def test_blocked_plan_exits_three(self):
        text = plan().replace("- PF-1 ready: C:\\Python\\python.exe",
                              "- PF-1 blocked: python does not resolve on PATH") \
                     .replace("Autonomy: verified-ready", "Autonomy: verified-blocked")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "plan.md"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(VERIFY.main([str(path)]), 3)

    def test_malformed_plan_exits_one(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "plan.md"
            path.write_text(plan().replace("- Status: pending", "- Status: nearly-done"), encoding="utf-8")
            self.assertEqual(VERIFY.main([str(path)]), 1)


class TestCrossSection(unittest.TestCase):
    def test_tdd_requires_a_qa_engineer_assignment(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | code-implementer | diff plus Done-when evidence |")
        self.assertIn("TDD requires qa-engineer assignment", messages(text))

    def test_verification_requires_build_and_tests(self):
        text = plan(verification="\n- Manual/static checks: read the diff\n")
        self.assertIn("Verification requires build and existing tests", messages(text))

    def test_selected_review_requires_lite_and_ask_policy(self):
        text = plan(verification="\n- Build: `npm run build`\n- Existing tests: `npm test`\n"
                                 "- Code review: `code-review-lite` over changed files\n")
        self.assertIn("selected review requires Escalation Policy: ask", messages(text))

    def test_skipped_review_must_not_invoke_lite(self):
        text = plan(review="skipped", verification="\n- Build: `npm run build`\n- Existing tests: `npm test`\n"
                                                   "- Code review: `code-review-lite` anyway\n")
        self.assertIn("skipped code review must not invoke code-review-lite", messages(text))

    def test_delegation_safety_vocabulary_is_required(self):
        text = plan().replace(SAFETY, "Keep changes small.")
        self.assertIn("delegation safety/working-tree-aware contract is incomplete", messages(text))

    def test_placeholders_block(self):
        text = plan().replace("Return an empty CSV header row when the report has no rows.",
                              "Handle the export cases as needed, details T" + "BD.")
        self.assertIn("placeholder/vague text detected", messages(text))


if __name__ == "__main__":
    unittest.main()
