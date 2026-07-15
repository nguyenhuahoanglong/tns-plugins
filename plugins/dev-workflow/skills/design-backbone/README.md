# Design Backbone

## Purpose

`design-backbone` lets a senior define an executable workflow guardrail before junior detail implementation. It locks requirements, traces existing ownership, identifies exact methods/files to reuse or change, and wires complete local execution with deterministic hardcoded returns where detail is unfinished. Tests are optional and created only after explicit selection.

Backbone is not a file generator. New files, methods, and abstractions require evidence that existing responsibility owners cannot satisfy the design.

## Output

- approved backbone design document with requirement, flow, touchpoint, readiness, and explicit testing decision;
- static traceability from every requirement to real runtime symbols and, when tests are selected, named tests;
- real entrypoint, DI/config, orchestration, and boundary wiring;
- complete local workflow using explicit local-only deterministic hardcoded returns where detail is absent;
- concise junior-action comments describing expectation, business requirement, or key design decision without prescribing implementation;
- optional tests created through `unit-testing` only when selected;
- no detail business logic, placeholder throws, commits, or PR operations.

## Pain Points Addressed

- Junior developers editing wrong ownership boundary or inventing parallel solutions.
- Scaffold-only code that builds but cannot run through production entrypoints.
- New interfaces/services created without caller, DI registration, or reuse analysis.
- Excessive implementation detail that removes junior-owned work.
- Design requirements without traceable runtime ownership.

## Related Skills

- `brainstorming` for broader pre-design exploration.
- `unit-testing` when the user selects spec-first readiness and design-completion tests.
- `implement-plan` when user wants complete detail implementation after backbone approval.
- `azdevops-operations` for resolving work-item inputs.

## Changelog

### 2026-07-15 — Junior-owned detail and optional tests

- Limited backbone implementation to workflow, contracts, wiring, and data handoff.
- Allowed local-only hardcoded expected returns so downstream workflow steps run before detail implementation.
- Required concise junior-action comments without algorithm-level instructions.
- Made tests an explicit selected/skipped decision.
- Routed selected test creation through `unit-testing` and its review gate.
- Updated verifier contract so skipped-test designs pass while selected-test designs retain full traceability checks.

### 2026-07-14 — Rename and runtime-ready contract

- Renamed `design-scaffold` to `design-backbone`.
- Replaced stub-only output with senior-owned, end-to-end local workflow readiness.
- Made existing-flow and responsibility-owner exploration mandatory.
- Added `reuse | modify | extract | new` touchpoint decisions with justification gates.
- Added explicit plan approval before code changes.
- Added deterministic local-only mock patterns and production isolation checks.
- Added green readiness tests and executable RED design-completion tests.
- Replaced logic-leak guardrail with design/backbone contract verifier.
- Added requirement-to-runtime-symbol, readiness-evidence, and test-name verification; project commands remain execution proof.

### 2026-06-21 — Initial scaffold workflow

- Created `design-scaffold` for interview-gated, structure-only output.
- Added SOLID/DRY/KISS/YAGNI reference, stub idioms, verifier, and evals.
