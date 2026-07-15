# Runtime Backbone Patterns

Backbone must execute complete local workflow without junior-owned detail business logic. Use existing project composition patterns first; examples below show constraints, not required APIs.

## Separate orchestration from missing detail

Implement workflow control, dependency calls, and data handoff needed to reach final step. Put unfinished detail behind narrow existing or approved methods. Those backbone methods may return deterministic, contract-valid hardcoded expected values so downstream steps execute.

Keep junior-action comments concise and outcome-focused:

```text
TODO(junior): Replace local-backbone value. Expected result: normalized partner code required by invoice routing. Preserve case-insensitive matching decision.
return "abc"
```

State expected behavior, business requirement, or key design decision. Do not prescribe algorithm, helper structure, or line-by-line implementation.

Do not use:

- `NotImplementedException`, `NotImplementedError`, or `throw new Error("Not implemented")`;
- unconditional empty/default returns that make later steps unreachable;
- production code that silently selects mocks from machine name, debugger state, or missing credentials.

## Explicit local-only selection

Select hardcoded backbone behavior through explicit development/backbone configuration. Validate environment during composition.

```text
if mode == LocalBackbone and environment == Development:
    register or enable deterministic backbone methods
else if mode == LocalBackbone:
    fail startup
else:
    register production behavior
```

Match repository conventions: .NET options/DI, Python dependency factories, or TypeScript composition/config modules. Keep guard at composition boundary so business code cannot accidentally choose hardcoded behavior. A separate mock provider is optional; prefer existing seams and minimal code.

## Deterministic mock data

Mock outputs must:

- satisfy same contract as production outputs;
- use fixed identifiers, timestamps, ordering, and values unless test controls them;
- cover data needed by every later workflow step;
- avoid network, database, clock, random, and machine-state dependencies;
- make failures diagnosable through named fixtures or scenarios.

Prefer direct, readable hardcoded returns inside approved local-backbone seams. Add a provider only when existing architecture already requires one.

## Optional testing

Ask user to select or skip tests during design. Do not infer selection from project conventions.

When skipped, require project build plus complete real local happy-path execution. Create no test matrix, registry, or test code.

When selected, invoke `unit-testing` in spec-first mode and follow its review gate. Then apply these states:

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

Junior developer changes production detail logic, not test expectations, unless senior approves a design change.

## Backbone design document contract

Use exact section and table names documented in `SKILL.md`. Keep paths project-relative. `scripts/verify_output.py` validates:

- required sections and table columns;
- every requirement maps to a known runtime touchpoint;
- eligible runtime touchpoint path/symbol existence, permitted actions, and justification for `extract`/`new`;
- required runtime-readiness concerns, mock isolation wording, and eligible runtime/config evidence path/symbol existence;
- explicit `selected` or `skipped` testing decision;
- when selected, complete requirement-to-completion-test coverage, project-native test path/name existence, readiness `green`, completion `red`, and no obvious skip markers;
- when skipped, absence of contradictory test matrix.

These are static checks. They do not prove build, workflow, or test execution. Run project-native build and local workflow commands separately; run test commands only when selected. Record actual output.
