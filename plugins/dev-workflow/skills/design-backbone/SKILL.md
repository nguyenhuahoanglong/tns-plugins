---
name: design-backbone
description: "Design senior-owned, runtime-ready code backbones. Use when locking requirements, reusing existing flow, wiring local mock returns, and defining junior-owned detail seams."
version: 2.1.0
---

# Design Backbone

Create a senior-owned executable backbone that constrains where junior developers add detail logic. Define workflow, ownership, touchpoints, contracts, wiring, and local mock returns. Do not treat backbone as permission to create files or methods.

## Non-negotiable outcome

- Run the complete workflow locally with deterministic hardcoded returns where unfinished detail would block downstream steps; never stop at an intentional stub.
- Reuse or modify existing responsibility owners before adding abstractions.
- Keep production wiring real. Enable mocks only through explicit local/backbone configuration and reject them outside that mode.
- Add concise junior-action comments that state expected behavior, business requirement, or key design decision without prescribing an algorithm.
- Ask whether unit tests are selected or skipped; never create tests by default.
- Map every normative design requirement to runtime touchpoints. When tests are selected, also map requirements to tests.
- Write no junior-owned detail business logic and do not commit.

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

## Phase 3 — Design touchpoints and decide testing

Write these exact `##` sections in the backbone design document:

1. `Requirements` — table: `Requirement ID | Requirement | Required Coverage`.
2. `Existing Flow` — current and proposed call chain, responsibility owners, and boundary evidence.
3. `Touchpoint Matrix` — table: `Requirement IDs | Path | Symbol | Action | Justification`; action must be `reuse`, `modify`, `extract`, or `new`.
4. `Runtime Readiness` — table: `Concern | Decision | Verification | Evidence Path | Evidence Symbol`; include `entrypoint`, `dependency wiring`, `local mock`, `production isolation`, and `end-to-end workflow`.
5. `Testing Decision` — table: `Decision | Rationale | Verification`; decision must be `selected` or `skipped`, confirmed explicitly by the user.
6. When selected, `Test Coverage Matrix` — table: `Requirement ID | Test Path | Test Name | Category | Initial State | Coverage`; classify readiness tests as `green` and completion tests as `red`. When skipped, omit this section.

Use runtime source files for touchpoints, runtime/config source for readiness evidence, and—when selected—project-native test source for test evidence; documentation is never execution evidence. Map every requirement to at least one runtime touchpoint. Every `extract` or `new` needs evidence that existing ownership cannot safely serve the design. Mark requirements intentionally deferred or `N/A` only with user approval. Read `references/runtime-backbone-patterns.md` for mock/wiring patterns.

Present proposed flow, touchpoint matrix, mock-return strategy, file changes, and testing decision. Require explicit plan approval before editing code.

## Phase 4 — Build executable backbone

Apply approved touchpoints only:

- preserve existing ownership and style;
- add real DI/config/entrypoint wiring;
- implement workflow order and data handoff only—no calculations, mappings, validation decisions, persistence behavior, or other junior-owned detail;
- in unfinished backbone methods, hardcode deterministic contract-valid expected returns where needed to let later steps run locally;
- place a concise TODO-style comment beside each hardcoded return, stating expected behavior, business requirement, or key design decision without prescribing implementation steps;
- isolate hardcoded behavior behind explicit local/backbone configuration and fail startup/configuration if it reaches non-local runtime;
- leave junior-owned detail executable through local mock returns, without `NotImplemented*`, throwing placeholders, or dead call paths.

Update design paths and symbols if implementation reveals a mismatch. Architecture changes require renewed approval.

## Phase 5 — Follow testing decision

- If skipped, create no test matrix, test registry, or test code. Verify project build and complete real local happy-path execution.
- If selected, invoke `unit-testing` in spec-first mode and follow its review gate. After approval, create project-native readiness tests plus completion tests covering every normative requirement and documented case.
- For selected tests, run readiness tests green and confirm completion-test RED failures assert missing detail behavior, not skips, imports, setup, fixtures, compilation, or infrastructure failures.
- Do not weaken tests to fit backbone output. Junior finishes detail logic by making completion tests green.

## Verify Output and hand off

As the final guardrail, run project build and complete real local happy path. When tests are selected, also run readiness and completion tests. Then run:

```powershell
python scripts/verify_output.py <project-root> --design <backbone-design.md>
```

Verifier proves static runtime traceability and, when tests are selected, referenced test symbols. Project commands prove build, workflow, and test execution. Fix failures. Report locked design, reused/modified/new touchpoints, runtime command, local-backbone guard, hardcoded returns and comments, testing decision/evidence, and remaining junior-owned logic. Do not stage, commit, review, or create a PR unless requested.

## References

- `references/design-principles.md` — flow tracing, ownership, reuse-first decisions, SOLID/DRY checks.
- `references/runtime-backbone-patterns.md` — local-only deterministic mocks and executable-backbone patterns.
- `scripts/verify_output.py` — mechanical design/backbone contract verifier.
