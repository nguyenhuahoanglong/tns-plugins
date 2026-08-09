# Implementation Agent Prompts

Use only after approval. Main agent owns plan status and working-tree-aware scope verification.

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
Constraints, your task, and scoped tests. Follow its Depth/Mode/Done-when. Complex-backbone pauses this
same task for unchanged design-backbone, honors independent locks, verifies handoff, resumes, and avoids
duplicate tests. Run scoped verification.
Statuses: DONE; DONE_WITH_CONCERNS (criteria met, list risks); NEEDS_CONTEXT (question and changes);
BLOCKED (reason and attempts).
{mandatory writable-dispatch footer}
```

Main agent accepts DONE only after diff, scope, and Done-when evidence. One fresh blocker retry carries
the decision and prior progress; a second blocker becomes `blocked`.

## Verification and review rework

Use a fresh implementer for red tests, unmet Done-when, scope violation, evidence mismatch, or all
must-fix findings for affected tasks. Require exact correction, re-run Done-when verification, then append
the mandatory writable-dispatch footer. Selected review dispatches say `Run code-review-lite ... Escalation
Policy: ask` and include `Global Constraints (verbatim from plan): {exact block}`. Re-verify/re-review at
most twice. Skipped review has no dispatch, offer, or verdict.

## Supporting docs

Update or offer supporting docs only when an AC, project rule, or verified code impact requires them.
Keep each affected document with its owning code task when practical. If a separate final sync is needed,
use one cheap agent per independent documentation file with final diff-stat, request surgical updates,
then append the mandatory writable-dispatch footer.
