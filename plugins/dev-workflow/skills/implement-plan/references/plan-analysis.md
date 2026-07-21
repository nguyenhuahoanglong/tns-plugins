# Plan Exploration, Feasibility & Decomposition

Phase 0 is read-only; the only Phase 1 write is the plan. Resolve Context fields using
`quality-assessment.md`, including its path matrix. Discovered backlog context never redirects.

## Exploration and design scaling

Use the minimum explorers that cover scope: one for known isolated files; two or three parallel,
distinct focuses for uncertain or multi-area work. Personally read every critical file they identify
before decomposition. Use zero architect agents for trivial one-file work, one for standard scope, and
up to three distinct read-only perspectives for complex scope; reconcile one approach.

## Readiness checks

1. Resolve path evidence, recommendations, decisions, sources, reasons, and top-level Depth exactly.
2. Confirm each file, pattern, signature, AC mapping, dependency, and mechanical Done when.
3. Check cross-task symbols have identical names/signatures; scan for `TBD`, `TODO`, `appropriate`, or
   vague cross-task shorthand. Any hit blocks writing.
4. Run `scripts/verify_output.py` before approval.

## Per-task Actionability Gate

A task is admitted only when files exist (or a confirmed target folder for a marked new file), the
pattern/signature was personally read, description is zero-context executable, Done when is mechanical,
and `Depends on` is `none` or an exact task. It includes exactly:

```text
Risk: routine|risky
Risk reason: <non-empty>
Depth: simplify|TDD
Mode: existing-method|simple-new|complex-backbone
Existing-method baseline: <existing suite command/result, or not applicable>
Scaffold: <named signatures/control-flow wiring, or not applicable>
```

Only risky user-approved tasks use TDD. No two tasks share a file: merge overlapping work. Separate
files may parallelize; imports/contracts create explicit dependency edges, and changed shared interfaces
precede all consumers. Agent scaling is 1 implementer for 1-3 files, 2 for 4-6, 3 for 7-9, and
dependency-ordered batches for 10+ files. The plan records waves and each agent's file scope, task
contract, Done-when evidence, and requirement to report changed files plus verification.

## Mode-specific execution

- `existing-method`: record exact existing-suite GREEN baseline; reuse/add characterization tests GREEN;
  make RED assertions only for changed/new behavior; implement to GREEN.
- `simple-new`: only when Depth is TDD, after approval create compile-ready named signatures and
  control-flow wiring without business logic, record `Scaffold`, add assertion-level RED tests, then
  implement to GREEN. With `simplify`, implement directly and use `Scaffold: not applicable`.
- `complex-backbone`: use unchanged `design-backbone` independent decision/approval locks, verified
  handoff, resume the same task, and create no duplicate tests.
