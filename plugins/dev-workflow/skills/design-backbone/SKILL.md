---
name: design-backbone
description: "Design senior-owned, runtime-ready code backbones. Use when locking requirements, reusing existing flow, wiring local mocks, and creating tests before junior implementation."
version: 2.0.0
---

# Design Backbone

Create a senior-owned executable backbone that constrains where junior developers add detail logic. Define workflow, ownership, touchpoints, contracts, wiring, local mocks, and tests. Do not treat backbone as permission to create files or methods.

## Non-negotiable outcome

- Run the complete workflow locally with deterministic mock data; never stop at an intentional stub.
- Reuse or modify existing responsibility owners before adding abstractions.
- Keep production wiring real. Enable mocks only through explicit local/backbone configuration and reject them outside that mode.
- Keep readiness tests green. Make design-completion tests executable RED only because detail behavior is absent—not because tests are skipped or broken.
- Map every normative design requirement to code touchpoints and tests; cover at least every happy case.
- Write no detail business logic and do not commit.

## Phase 0 — Resolve source and local rules

Read project `AGENTS.md`, authoritative design documents, work items, and linked artifacts in full. For numeric Azure DevOps IDs, use `azdevops-operations`. If sources conflict or are ambiguous, stop and ask which source wins.

Summarize goal, scope, non-goals, constraints, assumptions, and unresolved decisions. Do not continue until the user confirms understanding.

## Phase 1 — Interview and lock requirements

Interview only on consequential gaps:

- end-to-end happy path, inputs, outputs, state changes, and completion boundary;
- error/edge behavior stated by the design;
- production callers, external boundaries, data sources, and local-run expectations;
- allowed changes and junior-owned detail logic;
- acceptance evidence for each normative requirement.

Present viable approaches and trade-offs when architecture is unresolved. Recommend one. Record locked decisions in a backbone design document. Require explicit `decisions locked` confirmation before repository design.

## Phase 2 — Explore existing workflow first

Trace real code before proposing files: entrypoint → callers → orchestration → services → repositories/adapters → DI/config → external boundaries. Search symbol usages, registrations, tests, and analogous flows. Read full relevant implementations, not only interfaces or neighboring filenames.

Build a responsibility-owner map. For each required behavior, identify current owner and consumer. Detect duplicate ownership, wrong dependency direction, missing runtime registration, and existing seams that can carry the requirement. Read `references/design-principles.md`.

## Phase 3 — Design touchpoints and tests

Write these exact `##` sections in the backbone design document:

1. `Requirements` — table: `Requirement ID | Requirement | Required Coverage`.
2. `Existing Flow` — current and proposed call chain, responsibility owners, and boundary evidence.
3. `Touchpoint Matrix` — table: `Requirement IDs | Path | Symbol | Action | Justification`; action must be `reuse`, `modify`, `extract`, or `new`.
4. `Runtime Readiness` — table: `Concern | Decision | Verification | Evidence Path | Evidence Symbol`; include `entrypoint`, `dependency wiring`, `local mock`, `production isolation`, and `end-to-end workflow`.
5. `Test Coverage Matrix` — table: `Requirement ID | Test Path | Test Name | Category | Initial State | Coverage`; classify `readiness` tests as `green` and `completion` tests as `red`.

Use runtime source files for touchpoints, runtime/config source for readiness evidence, and project-native test source for test evidence; documentation is never execution evidence. Map every requirement to at least one runtime touchpoint. Every `extract` or `new` needs evidence that existing ownership cannot safely serve the design. Mark requirements intentionally deferred or `N/A` only with user approval. Read `references/runtime-backbone-patterns.md` for mock/wiring patterns.

Present proposed flow, touchpoint matrix, mock strategy, file changes, and test plan. Require explicit plan approval before editing code.

## Phase 4 — Build executable backbone

Apply approved touchpoints only:

- preserve existing ownership and style;
- add real DI/config/entrypoint wiring;
- implement enough orchestration for every workflow step to execute locally;
- return deterministic, contract-valid mock data where missing detail would otherwise block later steps;
- isolate mock providers behind explicit local/backbone configuration;
- fail startup/configuration if mock wiring reaches non-local runtime;
- leave detail business decisions to junior implementation, without `NotImplemented*`, throwing placeholders, or dead call paths.

Update design paths and symbols if implementation reveals a mismatch. Architecture changes require renewed approval.

## Phase 5 — Create tests

- Write project-native smoke/integration tests for startup/DI and complete local happy-path execution; run them green.
- Use the `unit-testing` skill in spec-first mode for completion tests covering every normative requirement and each documented happy case; add specified edge/error cases. The Phase 3-approved Test Coverage Matrix satisfies that skill's test-case-list gate (no second approval stop); derive the `{design-doc}.test-cases.md` registry from it and apply the QA traceability headers and back-linking from the skill's `references/test-case-management.md`, so juniors and QA can map every completion test to its requirement.
- Run completion tests. Confirm RED failures assert missing behavior. Fix skips, imports, setup, fixtures, and infrastructure failures before handoff.
- Do not weaken tests to fit backbone output. Junior finishes detail logic by making completion tests green.

## Verify Output and hand off

As the final guardrail, run project build, readiness tests, and completion tests, then run:

```powershell
python scripts/verify_output.py <project-root> --design <backbone-design.md>
```

Verifier proves static traceability and referenced symbols only; project commands prove build and test execution. Fix failures. Report locked design, reused/modified/new touchpoints, runtime command, mock-mode guard, green readiness evidence, expected RED completion evidence, and remaining junior-owned logic. Do not stage, commit, review, or create a PR unless requested.

## References

- `references/design-principles.md` — flow tracing, ownership, reuse-first decisions, SOLID/DRY checks.
- `references/runtime-backbone-patterns.md` — local-only deterministic mocks and executable-backbone patterns.
- `scripts/verify_output.py` — mechanical design/backbone contract verifier.
