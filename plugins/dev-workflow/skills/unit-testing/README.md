# Unit Testing

## Purpose

Creates traceable, deterministic unit and component tests for C#/.NET, React/TypeScript, and PCF. The skill treats existing production code as a first-class target: it protects observable behavior and meaningful regression risks while retaining the project’s framework, test ownership, and suite structure. Browser E2E remains out of scope.

## Pain Points Addressed

- **Existing behavior regressions:** running code without a safety net now uses a first-class preservation workflow.
- **Duplicate or split tests:** canonical ownership reuses the same subject, module, fixture, and project convention; ambiguity stops for direction.
- **Framework guessing:** the detector reports the project context and instruction candidates before test analysis.
- **Coverage theatre:** coverage identifies gaps, while behavior/risk inventory drives what must be covered and records intentionally uncovered reasons.
- **Untraceable tests:** registry metadata and test headers link QA-readable cases to owned tests across frameworks.
- **Repeated approval:** a direct request retains the test-case approval gate, while approved `implement-plan` and `design-backbone` artifacts satisfy it once.

## Design Notes

- **Four target modes:** `New Behavior`, `Existing Behavior Preservation`, `Existing Behavior Change`, and `Coverage Gap` select the correct objective before tests are written.
- **Known Quirk is not correctness:** suspicious current behavior can be pinned in registry metadata and test headers without endorsing it or changing production code.
- **Registry hierarchy:** resolve existing registry, approved plan/design, project convention, then canonical test file.
- **Existing behavior order is deliberate:** discover instructions, resolve ownership, baseline GREEN, inventory behavior, map risks, reconcile tests, satisfy the approval gate, verify, then back-link the registry.
- **Scope = unit + component only:** E2E/Playwright stays with `qa-engineer` and `browser-skill`.

## Changelog

### 2026-07-27 - First-class existing behavior workflow
- Replaced the previous narrow decision path with four explicit target modes, including `Existing Behavior Preservation` and `Existing Behavior Change`.
- Added the ordered existing-behavior workflow for instruction discovery, canonical ownership, GREEN baselines, behavior/risk coverage, reconciliation, approval, verification, and registry back-linking.
- Defined coverage as a gap detector, required reasons for intentionally uncovered gaps, and clarified `Known Quirk` characterization semantics.

### 2026-07-12 - Implement-plan quality assessment
- Clarified unit-test generation may be selected automatically from target-project evidence; explicit user choices still override assessment.

### 2026-07-11 - Explicit implement-plan opt-in
- Clarified that `implement-plan` invokes unit-test generation only after user selects it during planning.

### 2026-06-21 - Initial
- Created the unit-testing skill with C#, React, PCF, characterization, test-case management, and verifier support.
