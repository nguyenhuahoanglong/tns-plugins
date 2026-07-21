# Definition Criteria

The interview locks observable ACs and deterministic completion before planning. “Make it work” and
“handle errors properly” are gaps, not criteria.

## Acceptance Criteria

Each plan AC states observable behavior and maps to one or more tasks. Good: `AC-1: Exporting an empty
report yields a CSV with only the header row.` Weak: `AC-1: Export works.`

## Per-task contract

Every task has a mechanical Done when and exactly these fields:

```text
Risk: routine|risky
Risk reason: <non-empty trigger or routine justification>
Depth: simplify|TDD
Mode: existing-method|simple-new|complex-backbone
Existing-method baseline: <exact existing suite command/result, or not applicable>
Scaffold: <named signatures/control-flow wiring, or not applicable>
```

Valid evidence is a named build/test command, deterministic assertion, or exact endpoint I/O. Only a
risky task with explicit user TDD approval uses `Depth: TDD`; all others simplify. Top-level Depth still
follows the Context TDD decision, so mixed plans can retain routine simplify tasks.

## Depth and mode

- `existing-method`: record exact existing-suite GREEN baseline; reuse/add characterization tests GREEN;
  RED assertions cover only changed/new behavior; implementation ends GREEN.
- `simple-new`: when Depth is TDD, after approval create compile-ready named signatures and control-flow
  wiring without business logic, record Scaffold, make assertion-level tests RED, then implement GREEN.
  When simplify, implement directly and use `Scaffold: not applicable`.
- `complex-backbone`: complex workflow, wiring, DI, external integration, or deterministic-local-mock
  work follows unchanged `design-backbone`: independent decision/approval locks, verified handoff,
  resume same task, and no duplicate tests.

Routine doc/config/generated/metadata work is TDD/review `not-recommended` and `skipped` without asking.
Risky recommendation reasons state evidence, risk, and effort before a question. Only user Yes selects;
modern `selected`/`auto-assessment` requires consent before execution. Preserve `user` decisions and map
legacy `requested`/`not requested` to user selected/skipped when rewriting.
