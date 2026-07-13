# Interview Guide

Phase 0 interview stays lean: 1-2 rounds, about five criteria questions. Skip anything input,
existing plan, or repository evidence already resolves. Output feeds plan; implementation waits for
approval.

## Quality decisions first

Run `quality-assessment.md` after exploration. Do not ask unit-test/review questions by default.

- Explicit request or decline resolves choice with source `user`.
- Conclusive project evidence resolves choice with source `auto-assessment`.
- Missing or conflicting evidence leaves only that choice unresolved.
- Ask unresolved choices through multiple-choice UI, together when both remain:
  - **Write unit tests?** `No (Recommended)` or `Yes - use TDD flow`.
  - **Run code review?** `No (Recommended)` or `Yes - use code-review-lite`.

User answer overrides prior automatic result. Existing modern fields resolve choices. Legacy flags
map per `quality-assessment.md`; do not ask again after successful mapping.

## Required interview outcome

Before planning, state:

1. Scope in and explicit non-goals.
2. Design location, contracts, and verified patterns.
3. Observable Acceptance Criteria.
4. Mechanically checkable Done-when for every task.
5. Unit-test and code-review decisions, sources, and non-empty reasons.

If one item remains unknown, ask one targeted question. If more than about five criteria questions
across two rounds are needed, narrow scope or state explicit user-approved assumptions.

## Question bank

Choose only questions that change plan.

### Scope

- What smallest change solves problem?
- What must remain untouched?

### Design and contracts

- Extend existing module or add new module?
- What inputs, outputs, and compatibility constraints apply?
- Which libraries/services must be used or avoided?

### Criteria

- What concrete input produces what expected output?
- Which error/edge scenarios matter, and what result should each produce?
- Which build, test, static, or manual check proves completion?

## Technique

- Round 1: ask 3-5 highest-value unresolved questions, weighted toward criteria.
- Round 2: fill exposed gaps and confirm task Done-when statements.
- Convert subjective prose into observable criteria. Example: "fast" becomes a stated response-time
  threshold for a named workload.
- Approval comes after plan writing, not during interview.
