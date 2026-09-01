# Agent Prompts

Use only after approval. Planning dispatch is the host tool's business, not this skill's. The main agent
owns plan status and working-tree-aware scope verification.

## Shared rules

- Pass the plan path; never inline the full plan or source files. Point agents to applicable `AGENTS.md`.
- The main agent alone edits plan status. Dependency order determines waves, and parallelism never bypasses
  it. Correctness never assumes real concurrency.
- Before every writable dispatch, record working-tree-aware status plus scoped diff and file hashes;
  compare afterward.
- Every writable dispatch carries its exact task-file allowlist and the mandatory footer below.
- Review receives Global Constraints verbatim. Selected review alone uses `Escalation Policy: ask`; never
  pre-rate findings or tell a reviewer what not to flag.

## Mandatory writable-dispatch footer

Append this verbatim to every writable dispatch:

```text
You are not alone in the working tree. Write allowlist: {exact task-listed files only}.
Do not write outside that allowlist; do not delete or move files; do not git reset, restore, or checkout;
do not stash, stage, commit, push, publish, install, or broadly clean/revert other changes. If required
work exceeds the allowlist or any prohibited operation seems needed, stop and report the exact blocker.
Do not edit plan status. Return changed files, commands/results, and Done-when evidence.
```

## QA engineer (TDD only)

```text
Create assertion-level tests for Task {N} at {plan-path}; use project framework and unit-testing
traceability/test-registry rules. Existing-method: baseline GREEN, characterization GREEN, changed RED.
Simple-new: verify compile-ready named signatures/control-flow scaffold without business logic, then RED.
Do not implement production logic or edit the plan.
{mandatory writable-dispatch footer}
```

## Implementer

```text
Implement Task {N}: {task-name}; project: {project-root}; plan: {plan-path}. Read Goal, Global
Constraints, your task, and scoped tests. Follow its Mode, Depth, and Done-when. Run scoped verification.
Never ask the user anything; the plan is your only source of decisions.
Statuses: DONE; DONE_WITH_CONCERNS (criteria met, list risks); NEEDS_CONTEXT (state the missing fact and
return it to the main agent, never to the user); BLOCKED (reason and attempts).
{mandatory writable-dispatch footer}
```

The main agent accepts DONE only after checking diff, file scope, and Done-when evidence. `NEEDS_CONTEXT`
returns to the main agent, which resolves it from the plan or marks the task `blocked` — it is never a user
prompt, because that would break the autonomy guarantee. One fresh blocker retry carries the decision and
prior progress; a second blocker becomes `blocked`.

## Mode choreography

- `existing-method`: record the exact existing-suite GREEN baseline; reuse or add characterization tests
  GREEN; make RED assertions only for changed or new behavior; implement to GREEN.
- `simple-new`: at `Depth: TDD`, create compile-ready named signatures and control-flow wiring without
  business logic, record `Scaffold`, add assertion-level RED tests, then implement to GREEN. At `simplify`,
  implement directly.
- `complex-backbone`: pause the same task for unchanged `design-backbone`, honor its independent decision
  and approval locks, verify the handoff, resume the same task, and create no duplicate tests.

## Verification and review rework

Use a fresh implementer for red tests, unmet Done-when, scope violations, evidence mismatches, or all
must-fix findings for the affected tasks. Require the exact correction, re-run Done-when verification, and
append the mandatory footer. Selected review dispatches say `Run code-review-lite ... Escalation Policy:
ask` and include `Global Constraints (verbatim from plan): {exact block}`. Re-verify and re-review at most
twice. Skipped review has no dispatch, no offer, and no verdict.

## Supporting docs

Update or offer supporting docs only when an AC, project rule, or verified code impact requires them. Keep
each affected document with its owning code task when practical. If a separate final sync is needed, use
one cheap agent per independent documentation file with the final diff-stat, request surgical updates, then
append the mandatory footer.
