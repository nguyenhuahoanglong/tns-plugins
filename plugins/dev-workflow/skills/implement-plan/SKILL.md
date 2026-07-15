---
name: implement-plan
description: "Gated workflow that assesses project quality needs, writes an approved plan, delegates implementation, and verifies results. Use for '/implement-plan'."
---

# Implement Plan

Plan, approve, delegate, verify. Main agent owns design, plan status, and evidence checks; sub-agents
perform implementation. Workflow is tool-agnostic.

## Hard rules

1. **No changes before approval.** Phases 0-1 are read-only except plan file.
2. **Do not write production logic yourself.** After approval, delegate implementation. Main agent
   may write TDD scaffolds without logic and trivial one-line verification fixes.
3. **User instructions override assessment.** Never replace explicit test/review choice with inference.

## Input and plan path

- Inline idea or no argument: gather missing requirement details.
- Requirement/backlog file or folder: read source; interview only gaps.
- Existing plan: keep its path and resume; do not duplicate it.
- Work-item ID: fetch with `azdevops-operations`.

For new plans, resolve once to project-root `.plans/{kebab-feature-name}.md`. Project root means
nearest target module with applicable `AGENTS.md`, manifest/build files, and test configuration.

## Phase 0 - Understand (read-only)

1. Read applicable `AGENTS.md`, standards, manifests, build/test config, and requirement source.
2. Dispatch 1-3 read-only tool-native explorers per `references/plan-analysis.md`; then personally
   read critical files they identify.
3. Run balanced project quality assessment from `references/quality-assessment.md`.
   - Explicit user choice wins and gets source `user`.
   - Clear project evidence gets source `auto-assessment`.
   - Missing/conflicting evidence triggers only unresolved multiple-choice question(s).
4. Use `references/interview-guide.md` to lock scope, design, Acceptance Criteria, and mechanically
   checkable per-task Done-when. Do not ask resolved questions.

## Phase 1 - Design and write plan

1. Dispatch 0-3 read-only architect agents by complexity and reconcile one approach.
2. Decompose by feature slice. Each task names files, behavior, Done-when, ACs, and dependencies.
   No two tasks share a file; merge tasks that must overlap.
3. Derive depth: `Unit tests: selected` means TDD; `skipped` means simplify. Never derive depth from
   task shape.
   Auto-scale implementers by total scoped files: 1-3 files = 1; 4-6 = 2; 7-9 = 3; 10+ =
   dependency-ordered batches, one batch at a time.
4. Write plan using `references/plan-template.md`; include all six quality-decision fields, Depth,
   Agent Assignment, and verification commands.
5. Run `python scripts/verify_output.py <plan-path>`. Fix every FAIL before approval.
6. For 3+ tasks, run one plan-only fresh-eyes quick-check using
   `references/agent-prompts-planning.md` and fix executability gaps.

## Approval gate

Stop for explicit approval of written plan. Before approval: no scaffolds, tests, implementation,
config edits, or installs. After approval: execute continuously until blocked or complete.

## Phase 2 - Implement

- TDD only: main agent writes compiling signatures/stubs with no logic; dispatch `qa-engineer` via
  `unit-testing` to create tests that fail for expected missing behavior. Compile/import errors are
  invalid red. `Unit tests: skipped` creates no new test files. Plan approval satisfies the
  `unit-testing` test-case-list gate; tests still carry that skill's QA traceability headers
  (TC id, summary, steps, plan/design ref).
- Dispatch `code-implementer` tasks in Agent Assignment dependency order using
  `references/agent-prompts-implementation.md`. Record task base SHA before dispatch.
- After each return, inspect `git diff <base>..HEAD`, verify Done-when evidence, and confirm file
  scope. Only main agent updates task Status. Evidence mismatch goes to fresh-agent rework.
- Resolve blockers with one fresh implementer carrying decision and prior-progress summary. A second
  failure becomes `blocked`.

## Phase 3 - Verify

1. Verify every task Done-when and update Status.
2. Always run project build plus existing test suite once, even when new unit tests are skipped.
   Inspect final diff; record evidence in plan Verification.
3. When `Code review: selected`, run `code-review-lite`; send all must-fix findings for affected
   tasks to one fresh implementer, then re-verify/re-review. Cap at two iterations.
4. When `Code review: skipped`, do not offer, run, or report review verdict.
5. Tick ACs only from evidence. Re-run `scripts/verify_output.py` after final plan status updates.

## Phase 4 - Report

Report plan path, files changed, AC status, build/test results, manual follow-ups, and review verdict
only when selected. For structural changes, offer optional per-file docs sync.

## References

- Quality decisions and legacy mapping: `references/quality-assessment.md`
- Interview: `references/interview-guide.md`
- Exploration/decomposition: `references/plan-analysis.md`
- Plan schema: `references/plan-template.md`
- TDD criteria: `references/definition-criteria.md`
- Planning dispatches: `references/agent-prompts-planning.md`
- Implementation/rework dispatches: `references/agent-prompts-implementation.md`

## Error rules

- Verification unclear: resolve in Phase 0; do not plan vague task.
- Changes about to occur before approval: stop.
- Red tests or unmet Done-when: fresh implementer, then verify; cap two loops.
- 10+ files: dependency-ordered batches.
- Compacted context: trust plan Status and git history; never redispatch complete task.

## Verify Output

Run `python scripts/verify_output.py <plan-path>` before approval and after final status updates.
Zero FAIL required.
