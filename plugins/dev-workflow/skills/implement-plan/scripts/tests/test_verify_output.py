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
        "| 1 | Task 1 | code-implementer | RED then GREEN plus diff |")
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
    def test_optional_source_may_be_omitted(self):
        text = plan().replace("Unit tests source: user\n", "")
        self.assertNotIn("FAIL", levels(text), messages(text))

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
        self.assertIn("Unit tests source is invalid", messages(text))


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
    def test_mode_is_optional_at_every_depth(self):
        text = plan(unit="skipped").replace("- Mode: existing-method\n", "")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_tdd_depth_requires_selected_unit_tests(self):
        text = plan(unit="skipped").replace("- Mode: existing-method",
                                            "- Mode: existing-method\n- Depth: TDD\n- TDD reason: risky")
        self.assertIn("Depth TDD requires Unit tests: selected", messages(text))

    def test_tdd_depth_requires_a_reason(self):
        text = plan().replace("- TDD reason: Shared export behavior regressed twice before.\n", "")
        self.assertIn("requires a non-empty TDD reason", messages(text))

    def test_existing_method_tdd_needs_no_baseline_ceremony(self):
        text = plan().replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_simple_new_tdd_needs_no_scaffold_ceremony(self):
        text = plan().replace("- Mode: existing-method", "- Mode: simple-new") \
                     .replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_legacy_complex_mode_needs_no_word_soup(self):
        text = plan().replace("- Mode: existing-method", "- Mode: complex-backbone") \
                     .replace("- Existing-method baseline: npm test is GREEN at 214 passing.\n", "")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_invalid_status_fails(self):
        text = plan().replace("- Status: pending", "- Status: nearly-done")
        self.assertIn("Task 1 Status is invalid", messages(text))


class TestPreflightContract(unittest.TestCase):
    def test_missing_preflight_cannot_claim_ready(self):
        text = plan().replace("## Preflight", "## Prelaunch")
        self.assertIn("verified-ready requires recorded Preflight results", messages(text))

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
    def test_tdd_requires_a_code_implementer_assignment(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | advisor | assessment only |")
        self.assertIn("TDD Task 1 requires implementation-role assignment", messages(text))

    def test_tdd_rejects_qa_engineer_as_unit_test_owner(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | qa-engineer then code-implementer | RED then GREEN plus diff |")
        self.assertIn("TDD Task 1 must not assign qa-engineer", messages(text))

    def test_tdd_allows_separate_qa_e2e_assignment(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | code-implementer | RED then GREEN plus diff |\n"
                               "| 2 | E2E verification | qa-engineer | requirement trace plus E2E result |")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_tdd_rejects_qa_task_row_when_other_implementer_row_exists(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | qa-engineer | TDD tests |\n"
                               "| 2 | Task 2 | code-implementer | diff |")
        self.assertIn("TDD Task 1 must not assign qa-engineer", messages(text))

    def test_negative_qa_prose_does_not_change_tdd_assignment(self):
        text = plan(assignment="\n| Wave | Task(s) | Agent | Verified by main agent |\n|---|---|---|---|\n"
                               "| 1 | Task 1 | code-implementer | qa-engineer does not own unit tests |")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_verification_requires_build_and_tests(self):
        text = plan(verification="\n- Manual/static checks: read the diff\n")
        self.assertIn("missing Verification field: Build", messages(text))

    def test_selected_review_needs_no_ask_policy(self):
        text = plan(verification="\n- Build: `npm run build`\n- Existing tests: `npm test`\n"
                                 "- Code review: `code-review-lite` over changed files\n")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_skipped_review_must_not_invoke_lite(self):
        text = plan(review="skipped", verification="\n- Build: `npm run build`\n- Existing tests: `npm test`\n"
                                                   "- Code review: `code-review-lite` anyway\n")
        self.assertIn("skipped code review must not invoke a reviewer", messages(text))

    def test_delegation_needs_no_magic_safety_vocabulary(self):
        text = plan().replace(SAFETY, "Keep changes small.")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_prose_is_not_a_universal_schema(self):
        text = plan().replace("Return an empty CSV header row when the report has no rows.",
                              "Handle the export cases as needed, details T" + "BD.")
        self.assertNotIn("FAIL", levels(text), messages(text))



class TestFlexibleStructuredPlans(unittest.TestCase):
    def local(self, **kwargs):
        return plan(preflight="", **kwargs).replace("## Preflight\n", "")

    def test_minimal_context_and_extra_task_model_fields(self):
        text = self.local(context="Plan path: .plans/local.md\nUnit tests: selected\nCode review: selected")
        text = text.replace("- Mode: existing-method", "- Model: gpt-6.1-sol\n- Effort: medium")
        self.assertNotIn("FAIL", levels(text), messages(text))
        self.assertFalse(any("preflight results recorded" in msg for _, msg in VERIFY.evaluate(text)))

    def test_missing_minimal_context_and_invalid_decisions(self):
        for key in ("Plan path", "Unit tests", "Code review"):
            context = "\n".join(f"{name}: {value}" for name, value in
                (("Plan path", ".plans/local.md"), ("Unit tests", "skipped"), ("Code review", "skipped")) if name != key)
            self.assertIn(f"missing Context field: {key}", messages(self.local(context=context)))
        for label in ("Unit tests", "Code review"):
            self.assertIn(f"{label} must be selected or skipped", messages(plan().replace(f"{label}: selected", f"{label}: maybe")))

    def test_assessment_provenance_is_never_user_consent(self):
        for source in ("project", "assessment", "auto-assessment"):
            data = VERIFY.normalize({"Unit tests": ["selected"], "Unit tests source": [source]})
            self.assertEqual(data["Unit tests source"], [source])
            self.assertNotIn("FAIL", levels(self.local().replace("Unit tests source: user", f"Unit tests source: {source}")))

    def test_lawful_json_todo_and_appropriate_are_accepted(self):
        text = self.local().replace("Return an empty CSV header row when the report has no rows.",
            'Preserve TODO comments and emit appropriate JSON: {"empty": true}.')
        self.assertNotIn("FAIL", levels(text), messages(text))

    def pair(self, depends="none", files="src/other.ts"):
        first = VERIFY.section(self.local(unit="skipped", review="skipped"), "Tasks")
        second = first.replace("Task 1:", "Task 7:").replace("Depends on: none", f"Depends on: {depends}").replace("src/cache.ts", files)
        return self.local(unit="skipped", review="skipped", tasks=first + second)

    def test_disjoint_independent_tasks_are_accepted(self):
        self.assertNotIn("FAIL", levels(self.pair()), messages(self.pair()))

    def test_shared_files_need_direct_or_transitive_ordering(self):
        good = self.pair("Task 1", "src/cache.ts")
        self.assertNotIn("FAIL", levels(good), messages(good))
        self.assertIn("overlap Files without dependency ordering", messages(self.pair(files="src/cache.ts")))
        second = VERIFY.section(self.pair("Task 1"), "Tasks")
        third = VERIFY.section(self.local(unit="skipped", review="skipped"), "Tasks")
        third = third.replace("Task 1:", "Task 9:").replace("Depends on: none", "Depends on: Task 7")
        text = self.local(unit="skipped", review="skipped", tasks=second + third)
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_duplicate_unknown_self_and_cyclic_task_dependencies_fail(self):
        self.assertIn("duplicate Task 1", messages(self.pair().replace("Task 7:", "Task 1:")))
        self.assertIn("depends on unknown Task 9", messages(self.pair("Task 9")))
        self.assertIn("depends on itself", messages(self.pair("Task 7")))
        cyclic = self.pair("Task 1").replace("Depends on: none", "Depends on: Task 7")
        self.assertIn("dependencies contain a cycle", messages(cyclic))

    def test_undefined_acceptance_reference_fails(self):
        self.assertIn("references undefined AC-9", messages(self.local().replace("- ACs: AC-1", "- ACs: AC-9")))

    def test_task_needs_an_actual_acceptance_reference(self):
        self.assertIn("ACs must reference at least one AC-N", messages(self.local().replace("- ACs: AC-1", "- ACs: none")))

    def test_nonsequential_tdd_task_id_is_checked(self):
        text = self.local().replace("Task 1:", "Task 7:")
        self.assertIn("TDD Task 7 requires implementation-role assignment", messages(text))

    def test_flexible_implementation_roles_and_qa_boundary(self):
        for role in ("worker (implementation role)", "default carrying implementation role", "main (tiny task)"):
            text = self.local().replace("| code-implementer |", f"| {role} |")
            self.assertNotIn("FAIL", levels(text), messages(text))
        text = self.local().replace("| code-implementer |", "| worker |")
        self.assertIn("requires implementation-role assignment", messages(text))

    def test_qa_description_excluding_unit_tests_is_not_keyword_audited(self):
        text = self.local(unit="skipped").replace("| code-implementer |", "| qa-engineer |")
        text = text.replace("Return an empty CSV header row when the report has no rows.", "E2E only; do not write unit tests.")
        self.assertNotIn("FAIL", levels(text), messages(text))

    def test_review_pro_and_named_scoped_reviewer_are_accepted(self):
        for evidence in ("code-review-pro over changed files", "Reviewer: Jane; scope: changed parser",
                         "scoped code-reviewer over changed parser files"):
            text = self.local().replace("`code-review-lite` over changed files, `Escalation Policy: ask`", evidence)
            self.assertNotIn("FAIL", levels(text), messages(text))

    def test_evidence_requires_values_and_na_reasons(self):
        text = self.local().replace("`npm run build`", "N/A: no buildable product").replace("`npm test`", "N/A: no existing suite")
        self.assertNotIn("FAIL", levels(text), messages(text))
        self.assertIn("N/A requires a reason", messages(text.replace("N/A: no buildable product", "N/A")))
        self.assertIn("must be non-empty: Build", messages(text.replace("N/A: no buildable product", "")))

    def test_malformed_preflight_result_fails(self):
        self.assertIn("malformed Preflight result", messages(plan().replace("- PF-1 ready:", "- PF-1 success:")))

    def test_explicit_empty_preflight_is_malformed(self):
        self.assertIn("provided Preflight section is empty", messages(plan(preflight="")))

class TestTemplateSelfConsistency(unittest.TestCase):
    """The fill-in template documents probe grammar without inventing ready evidence."""

    TEMPLATE = Path(__file__).parents[2] / "references" / "plan-template.md"

    def _preflight_lines(self):
        return [line.rstrip() for line in self.TEMPLATE.read_text(encoding="utf-8").splitlines()
                if line.startswith("- PF-") or "derived path" in line]

    def _filled_preflight_lines(self):
        return [line.replace("<ready|blocked|unverifiable>", "ready").replace("<state>", "ready")
                for line in self._preflight_lines()]

    def test_filled_example_result_lines_match_the_verifier_grammar(self):
        unmatched = [line for line in self._filled_preflight_lines() if not VERIFY.RESULT_RE.match(line)]
        self.assertEqual(unmatched, [], "template result lines the verifier cannot parse")

    def test_template_requires_actual_aggregate_instead_of_claiming_ready(self):
        text = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Autonomy: <aggregate from recorded results>", text)
        self.assertNotIn("Autonomy: verified-ready", text)

    def test_template_documents_unverifiable_fallback_on_the_same_line(self):
        explicit = [line for line in self._preflight_lines() if line.startswith("- PF-")]
        self.assertTrue(explicit)
        for line in explicit:
            self.assertIn("unverifiable", line)
            self.assertIn("fallback:", line.lower())

    def test_every_declared_example_probe_kind_is_in_the_closed_set(self):
        preflight = VERIFY.section(self.TEMPLATE.read_text(encoding="utf-8"), "Preflight")
        kinds = [cells[1] for cells in VERIFY.rows(preflight) if len(cells) == 5]
        self.assertTrue(kinds)
        for kind in kinds:
            self.assertIn(kind, VERIFY.PROBE_KINDS)


if __name__ == "__main__":
    unittest.main()
