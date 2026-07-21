# Interview Guide

Keep Phase 0 to one or two rounds. Explore first; do not ask facts already resolved by input, an
existing plan, or repository evidence. Implementation waits for written-plan approval.

## Record resolved facts

Use the exact Context contract in `quality-assessment.md`. Apply its path matrix: existing plan retains
its supplied path; an explicit requirement file/folder under `.backlog/<feature>/` writes that feature's
`plan.md`; inline, no-argument, and non-backlog input write nearest project-root `.plans/<feature>.md`.
Discovered backlog context never redirects.

## Quality questions

Record recommendation and decision fields separately. Routine doc/config/generated/metadata work is
`not-recommended` and `skipped` for TDD and review without questions. For risky work, first state
trigger/evidence, workflow or regression risk, and effort, then ask only the affected choice:

- **Use TDD?** `No (Recommended)` or `Yes`.
- **Run code review?** `No (Recommended)` or `Yes`.

Only explicit `Yes` selects. Recommendation, silence, or existing modern `selected` with
`source: auto-assessment` is not consent; ask before execution. Preserve modern source `user` and legacy
`requested`/`not requested` explicit choices, normalizing legacy fields on rewrite.

## Required outcome

Before planning state scope/non-goals, design location and verified contracts, observable ACs, and a
mechanical Done when for every task. Each task includes exactly:

```text
Risk: routine|risky
Risk reason: <non-empty>
Depth: simplify|TDD
Mode: existing-method|simple-new|complex-backbone
Existing-method baseline: <existing suite command/result, or not applicable>
Scaffold: <named signatures/control-flow wiring, or not applicable>
```

Only user-approved risky tasks use TDD. Ask one targeted question for any remaining required fact; if
more than five criteria questions are needed across two rounds, narrow scope or obtain assumptions.

## Question bank

- What smallest change solves the problem, and what remains untouched?
- Which contract, library, or compatibility rule constrains it?
- Which input/output/error result proves it?
- For risky work, is the stated risk and effort worth selecting TDD or review?

Approval follows the written plan, not the interview.
