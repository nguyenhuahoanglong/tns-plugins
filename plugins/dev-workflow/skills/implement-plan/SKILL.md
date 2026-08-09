---
name: implement-plan
description: "Gated code-development workflow. Use only when user explicitly runs `$implement-plan` or `/implement-plan`, or asks to run `implement-plan`; never auto-trigger."
---

# Implement Plan

Plan, approve, delegate, verify code changes. Main agent owns design, plan status, and evidence; agents
own only their allowlisted implementation files.

## Entry gate

Run only after explicit invocation: `$implement-plan`, `/implement-plan`, or a direct request to run or
use `implement-plan`. Similar implementation intent without that explicit call never activates this
skill. After invocation, require a code-development deliverable such as source code, executable scripts,
test code, or runtime/build code tied to a feature, fix, or refactor. For document-only, PRD, research,
planning, spreadsheet, release-note, AI-asset text/metadata, or config-only work, stop this workflow and
route the request normally. Supporting non-code files never establish eligibility.

## Hard rules

1. Before approval, work is read-only except the plan. Main agent never writes production logic after
   approval, except approved compile-ready TDD scaffolds without logic and trivial verification fixes.
   Explicit approval in the current request counts for an unchanged existing plan; ask again only after
   creating or materially revising the plan.
2. Resolve output before discovery: retain existing plan path; explicit `.backlog/<feature>` requirement
   writes `.backlog/<feature>/plan.md`; all other input writes nearest-root `.plans/<feature>.md`.
3. Recommendations advise; only explicit user `Yes` selects TDD/review. Confirm or normalize old-modern
   auto-assessment selections before execution. Keep legacy requested/not-requested as user decisions.

## Phase 0 — understand

Read applicable `AGENTS.md`, requirements, standards, build/test configuration, and critical source.
Use 0–3 read-only explorers: zero for known isolated scope, one for normal discovery, two or three for
uncertain or multi-area work. Personally validate critical evidence, then assess quality. For recommended
risky workflows, state trigger/evidence, workflow/regression risk, and effort; ask only the affected opt-in.

## Phase 1 — design and approve

Use zero architects for trivial one-file work, one for normal work, and up to three perspectives for
complex/multi-area work. Reconcile one design. Write isolated feature-slice tasks with exact task fields,
mechanical Done-when, dependencies, and dependency waves. Assign one implementer per independent,
dependency-ready slice, keep coupled files together, and cap concurrent implementers at three. Run one
fresh-eyes plan quick-check for complex scope or three or more risky tasks.

Top Depth records the Context choice; risky user-approved tasks may use TDD while routine tasks simplify.
Run `python scripts/verify_output.py <plan-path>` and fix every FAIL. Stop for approval only when the plan
was created or materially revised; an explicitly approved unchanged plan proceeds.

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
only when selected. Update or offer supporting docs only when an AC, project rule, or verified code impact
requires them.

## References

- Decisions/interview: `references/quality-assessment.md`, `references/interview-guide.md`
- Task modes/design: `references/definition-criteria.md`, `references/plan-analysis.md`
- Agent dispatch: `references/agent-prompts.md`; schema: `references/plan-template.md`

## Verify Output

Run `python scripts/verify_output.py <plan-path>` before approval and after final updates; zero FAIL.
