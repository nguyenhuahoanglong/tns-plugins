# Implementation Agent Prompts

Use only after Approval Gate. Main agent owns plan status and verification.

## TDD qa-engineer

Skip when `Unit tests: skipped`.

```text
Generate failing unit tests in spec-first mode.
Project: {project-root}. Read applicable AGENTS.md and test conventions.
Plan: {plan-path}. Read each task Definition of Done.
Scaffold signatures/stubs already exist. Bind tests to real surfaces. Tests must fail for missing
behavior, not compile/import errors.

Rules:
- Use unit-testing skill and detected project framework.
- The approved plan satisfies the unit-testing test-case-list gate; derive cases from task
  Definition-of-Done items without stopping for approval. If a .docs design document drives the
  work, maintain its {design-doc}.test-cases.md registry per the skill's test-case-management.md.
- Modify tests only; do not implement production code or edit plan.
- Map each test to task and Definition-of-Done item, and give every test the skill's QA-readable
  header (TC/DoD id, one-line summary, numbered steps, plan or design ref) plus xUnit Trait or
  TC id in the JS test name.
- For non-unit-testable tasks, write no test; report exact build/manual/static check.
- Return test files, mapping, command, and expected-red evidence.
```

## Code implementer

Dispatch independent tasks together; sequence dependencies.

```text
Implement task: {task-name}
Project: {project-root}. Read applicable AGENTS.md.
Plan: {plan-path}
Task heading: ### Task {N}: {task-name}
Read Goal, Global Constraints, ACs, and your task only.
Pattern: {verified Phase 0 pattern}
Done when: {task Done-when or TDD checklist}

Workflow:
1. Read plan and scoped tests when TDD.
2. Modify only task-listed files; replace scaffolds when present.
3. Run scoped verification until Done-when is met.
4. Do not edit plan. End with one status plus files changed and evidence.

Statuses:
- DONE: all criteria met.
- DONE_WITH_CONCERNS: criteria met; list risks/assumptions.
- NEEDS_CONTEXT: ask specific questions and report changes.
- BLOCKED: report reason and attempts.
```

Main agent handles DONE only after diff, Done-when, and file-scope evidence pass. Resolve concerns
before completion. NEEDS_CONTEXT and BLOCKED use fresh agent after fixing input.

## Blocker retry

```text
Continue task: {task-name} after prior blocker.
Project: {project-root}; plan: {plan-path}; task: ### Task {N}.
Blocker and decision: {question} -> {decision}
Prior progress: {summary}

Finish task under decision; meet Done-when; do not edit plan. Return status, files, and evidence.
```

One retry. Second blocker becomes plan Status `blocked`.

## Verification rework

Use fresh implementer for red tests, unmet Done-when, scope violation, or evidence mismatch:

```text
Rework task: {task-name}
Project: {project-root}; plan: {plan-path}; task: ### Task {N}.
Failed evidence: {complete failures}
Required correction: {main-agent decision}

Fix only task-listed files. Re-run Done-when verification. Do not edit plan. Return status, files,
and new evidence.
```

## Review rework

Use only when `Code review: selected`. Send complete must-fix list for affected tasks to one fresh
implementer, not one agent per finding. Initial `code-review-lite` dispatch and every re-review must
receive plan's **Global Constraints block verbatim**; do not summarize, interpret, or pre-rate it.

```text
Run code-review-lite over changed files for {plan-path}.
Global Constraints (verbatim from plan):
{exact Global Constraints block}

Review changed files against plan criteria and constraints. Return must-fix findings with file and
line evidence. Do not edit files and do not pre-rate findings from orchestrator hints.
```

For must-fix findings, dispatch:

```text
Fix review issues for task(s): {task names}
Project: {project-root}; plan: {plan-path}
Findings: {complete must-fix findings from code-review-lite}

Address every finding in listed task files, re-confirm Done-when, and return status/evidence. Do not
edit plan or make unrelated changes.
```

Re-verify then re-review; cap two iterations.

## Docs sync

For structural changes only, dispatch one cheap agent per docs file using final diff-stat. Request
surgical index/path updates only; no unrelated rewrite.
