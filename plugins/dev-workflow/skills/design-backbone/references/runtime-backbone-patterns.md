# Runtime Backbone Patterns

Backbone must execute complete local workflow without detail business logic. Use existing project composition and test patterns first; examples below show constraints, not required APIs.

## Separate orchestration from missing detail

Implement workflow control, dependency calls, and data handoff needed to reach final step. Put unfinished detail behind narrow existing or approved seams. Local providers return deterministic, contract-valid results so downstream steps execute.

Do not use:

- `NotImplementedException`, `NotImplementedError`, or `throw new Error("Not implemented")`;
- unconditional empty/default returns that make later steps unreachable;
- skipped tests as placeholders;
- production code that silently selects mocks from machine name, debugger state, or missing credentials.

## Explicit local-only provider selection

Select mocks through explicit development/backbone configuration. Validate environment during composition.

```text
if mode == LocalBackbone and environment == Development:
    register deterministic local provider
else if mode == LocalBackbone:
    fail startup
else:
    register production provider
```

Match repository conventions: .NET options/DI, Python dependency factories/fixtures, or TypeScript composition/config modules. Keep guard at composition boundary so business code cannot accidentally choose mock behavior.

## Deterministic mock data

Mock outputs must:

- satisfy same contract as production outputs;
- use fixed identifiers, timestamps, ordering, and values unless test controls them;
- cover data needed by every later workflow step;
- avoid network, database, clock, random, and machine-state dependencies;
- make failures diagnosable through named fixtures or scenarios.

Prefer reusable fixture builders already present. Add minimal local provider only when no existing fake/test host can run the workflow.

## Readiness versus completion tests

**Readiness tests — green at handoff**

- application/test host starts;
- dependency graph resolves;
- explicit local mode selects mock providers;
- non-local mode rejects mock selection;
- complete happy-path workflow reaches final observable outcome.

**Design-completion tests — executable RED at handoff**

- one or more tests map to every normative requirement;
- every documented happy case is covered;
- documented edge/error cases are covered;
- failure comes from missing detail behavior asserted by test;
- no skip, import, setup, fixture, compilation, or infrastructure failure.

Use `unit-testing` in spec-first mode to create completion tests. Junior developer changes production detail logic, not test expectations, unless senior approves a design change.

## Backbone design document contract

Use exact section and table names documented in `SKILL.md`. Keep paths project-relative. `scripts/verify_output.py` validates:

- required sections and table columns;
- every requirement maps to a known runtime touchpoint;
- eligible runtime touchpoint path/symbol existence, permitted actions, and justification for `extract`/`new`;
- required runtime-readiness concerns, mock isolation wording, and eligible runtime/config evidence path/symbol existence;
- complete requirement-to-completion-test coverage and project-native test path/name existence;
- readiness `green` and completion `red` classification;
- obvious skipped-test markers.

These are static checks. They do not prove build, workflow, or test execution. Run project-native build and test commands separately and record actual output.
