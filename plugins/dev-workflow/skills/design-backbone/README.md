# Design Backbone

## Purpose

`design-backbone` lets a senior define an executable workflow guardrail before junior detail implementation. It locks requirements, traces existing ownership, identifies exact methods/files to reuse or change, wires complete local execution with deterministic mocks, and creates tests that measure design completion.

Backbone is not a file generator. New files, methods, and abstractions require evidence that existing responsibility owners cannot satisfy the design.

## Output

- approved backbone design document with requirement, flow, touchpoint, readiness, and test matrices;
- static traceability from every requirement to real runtime symbols and named tests;
- real entrypoint, DI/config, orchestration, and boundary wiring;
- complete local workflow using explicit local-only deterministic mock providers where detail is absent;
- green readiness tests;
- executable RED completion tests covering all normative requirements, at minimum every happy case;
- no detail business logic, placeholder throws, commits, or PR operations.

## Pain Points Addressed

- Junior developers editing wrong ownership boundary or inventing parallel solutions.
- Scaffold-only code that builds but cannot run through production entrypoints.
- New interfaces/services created without caller, DI registration, or reuse analysis.
- Skipped tests that do not define completion criteria.
- Design requirements without traceable code and test coverage.

## Related Skills

- `brainstorming` for broader pre-design exploration.
- `unit-testing` for spec-first design-completion tests; readiness uses project-native smoke/integration conventions.
- `implement-plan` when user wants complete detail implementation after backbone approval.
- `azdevops-operations` for resolving work-item inputs.

## Changelog

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
