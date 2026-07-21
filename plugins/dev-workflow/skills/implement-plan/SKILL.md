---
name: implement-plan
description: "Gated workflow that plans, delegates, and verifies approved work. Use for '/implement-plan'."
---

# Implement Plan

Plan, approve, delegate, verify. Main agent owns design, plan status, and evidence; agents own only
their allowlisted implementation files.

## Hard rules

1. Before approval, work is read-only except the plan. Main agent never writes production logic after
   approval, except approved compile-ready TDD scaffolds without logic and trivial verification fixes.
2. Resolve output before discovery: retain existing plan path; explicit `.backlog/<feature>` requirement
   writes `.backlog/<feature>/plan.md`; all other input writes nearest-root `.plans/<feature>.md`.
3. Recommendations advise; only explicit user `Yes` selects TDD/review. Confirm or normalize old-modern
   auto-assessment selections before execution. Keep legacy requested/not-requested as user decisions.

## Phase 0 — understand

Read applicable `AGENTS.md`, requirements, standards, build/test configuration, and critical source.
Use 1–3 read-only explorers, personally validate their critical evidence, then assess quality. Routine
docs/config/generated/metadata work is not-recommended and skipped without a question. For risky work,
state trigger/evidence, workflow/regression risk, and effort; ask only the affected opt-in.

## Phase 1 — design and approve

Use zero architects for trivial one-file work, one for normal work, and up to three perspectives for
complex/multi-area work. Reconcile one design. Write isolated feature-slice tasks with exact task fields,
mechanical Done-when, dependencies, and dependency waves. Auto-scale implementers by scoped files:
1–3=1, 4–6=2, 7–9=3, 10+=ordered batches. For 3+ tasks, run one fresh-eyes plan quick-check.

Top Depth records the Context choice; risky user-approved tasks may use TDD while routine tasks simplify.
Run `python scripts/verify_output.py <plan-path>` and fix every FAIL. Stop for explicit approval.

## Phase 2 — implement

Dispatch only through the prompt references, recording working-tree-aware status plus scoped diff/file
hashes before each writable dispatch and comparing them after. Main agent alone updates task Status.

- Existing-method TDD: baseline GREEN, characterization GREEN, changed-behavior assertion RED, then GREEN.
- Simple-new TDD: compile-ready named signatures/control-flow wiring only, assertion RED, detailed GREEN.
- Complex-backbone: pause the same task for unchanged `design-backbone`, honor its independent decisions
  and approvals, verify handoff, resume the task, and do not duplicate tests.
- `qa-engineer` uses `unit-testing` traceability/test registry rules. One fresh blocker retry carries the
  decision and prior progress; a second blocker marks the task `blocked`.

## Phase 3 — verify

Verify each Done-when, scoped diff, file scope, build, and existing suite. For selected review, invoke
`code-review-lite` with `Escalation Policy: ask` and Global Constraints verbatim; send all must-fix items
to one fresh implementer, re-verify/re-review, and cap at two loops. Skipped review is never offered,
run, or reported. Tick ACs only from evidence and rerun the verifier after status updates.

## Phase 4 — report

Report plan path, files changed, task/AC status, build/test evidence, manual follow-ups, and review verdict
only when selected. For structural changes, offer optional per-file docs sync.

## References

- Decisions/paths: `references/quality-assessment.md`; task modes: `references/definition-criteria.md`
- Discovery/design: `references/plan-analysis.md`, `references/agent-prompts-planning.md`
- Dispatch/rework: `references/agent-prompts-implementation.md`; schema: `references/plan-template.md`

## Verify Output

Run `python scripts/verify_output.py <plan-path>` before approval and after final updates; zero FAIL.
