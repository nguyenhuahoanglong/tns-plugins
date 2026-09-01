---
name: unit-testing
description: Create traceable unit and component tests for new, changed, or existing C# and React/PCF behavior. Use for test requests, coverage gaps, and regression protection.
---

# Unit Testing

## Overview

Produce traceable, deterministic, framework-native unit and component tests. Cover the unit and component layers only; browser E2E belongs to `qa-engineer` and `browser-skill`.

Classify the target before writing tests:

| Target mode | Use when | Test objective |
|---|---|---|
| `New Behavior` | Code is new or the contract is not implemented | Assert the approved requirement or acceptance criteria. |
| `Existing Behavior Preservation` | Running code needs regression protection without an intended behavior change | Characterize current observable behavior and protect meaningful risks. |
| `Existing Behavior Change` | Running code has an approved changed contract | Update the owned tests to assert the approved behavior; preserve unaffected behavior. |
| `Coverage Gap` | Existing tests miss a meaningful behavior | Add the smallest non-duplicate test for that gap. |

Coverage percentage is a gap detector, not a completion target. Inventory observable behavior, meaningful branches, boundaries, errors, and side effects; record a reason for every intentionally uncovered gap. A suspicious current result is a `Known Quirk`: pin it without claiming it is correct or changing production behavior.

## When to use

Use for requests to write, add, or generate unit/component tests; raise useful coverage; protect existing methods before refactoring; or write tests alongside approved implementation. Do not use for browser E2E.

## Step 1: Detect project context and instructions

Run the detector before choosing a framework or test location:

```bash
scripts/detect_test_framework.py <project-or-file-path>
```

Read its instruction candidates and apply precedence: explicit user instructions, nearest scoped project instructions, ancestor project instructions, test documentation, test configuration and observed convention, then skill defaults. Conflicts at one scope or without declared precedence require user direction. Match detected C#, React, or PCF framework conventions; never introduce a competing runner.

For an existing target, follow `references/existing-behavior.md` in its stated order. It defines instruction discovery, ownership, baseline, inventory, risk, reconciliation, approval, verification, and registry rules.

## Step 2: Choose the source of truth and registry

Use an approved design, plan, acceptance criteria, or observable code behavior according to the target mode. Resolve the test-case registry in this order:

1. Existing registry.
2. Approved plan or design artifact.
3. Project convention.
4. Canonical test file.

Registry metadata and test headers are the cross-framework source of truth. Add framework-native tags only when the project already supports them. Do not assume a design document is required for a code-only target.

## Step 3: Prepare the test-case list and approval gate

Create or reconcile a behavior/risk test-case list before direct test requests. Keep stable IDs, show ADD/UPDATE/REMOVED changes, include uncovered gaps with reasons, and wait for user approval before writing code.

An already-approved `implement-plan` task or `design-backbone` Test Coverage Matrix satisfies this gate. Derive the cases from that artifact and do not ask for duplicate approval. See `references/test-case-management.md` for registry format and traceability.

## Step 4: Write owned tests

Reuse the canonical same-subject test ownership: same subject under test, module, fixture, and project convention. If equally valid owners remain, stop and ask the user; never silently create a parallel test file.

Read `references/best-practices.md`, then the relevant stack reference. For mocks, also read `references/testing-anti-patterns.md`.

| Stack | Reference | Framework |
|---|---|---|
| C# .NET | `references/csharp-xunit.md` | Detected xUnit conventions |
| React / TypeScript | `references/react-vitest-jest.md` | Detected Vitest or Jest + RTL conventions |
| PCF | `references/pcf-testing.md` | Existing Jest + RTL conventions |

- Use AAA, deterministic inputs, and behavior-focused assertions.
- Before writing a test body, name the production break it must catch. If the only answer is source text, a constant, private structure, or another intentional decision, redesign the test around observable behavior.
- Derive expected values independently with literals or hand-checked fixtures; never compute both sides with the code under test or its helpers.
- Exercise the owned boundary your code exposes. Reject source-text/change-detector tests and assertions of framework mechanics unless a narrow characterization test records a genuinely surprising upstream assumption.
- Mock external boundaries, not internal implementation details.
- Reconcile existing tests: leave correct coverage, update owned tests for approved changes, add only missing behavior, and flag contradictions for review.
- Label each `Known Quirk` in both registry metadata and test header; it records current behavior, not correctness.

For spec-first work, write RED tests only after the approved gate and verify each fails for the expected assertion reason. Never modify production files.

## Verify Output and back-link

For implemented targets, run the relevant suite and retain the recorded GREEN baseline. For spec-first work, verify compile-ready tests fail only for the expected missing behavior. Before completion, mentally mutate realistic branches, arguments, returns, validations, state changes, and side effects; every in-scope break must fail at least one test or remain recorded as an intentional gap.

Then run:

```bash
scripts/verify_output.py <test-file-or-dir> [--existing <existing-tests-dir>] [--test-cases <registry.md>]
```

Fix failures, reconcile duplicates, and back-link each implemented case from the registry to the owned test file and method. Preserve intentional gaps and their reasons.

## Resources

- `references/existing-behavior.md` — preservation workflow, discovery precedence, ownership, and stop rules
- `references/test-case-management.md` — registry format, approval gate, IDs, headers, and back-links
- `references/best-practices.md` — shared testing principles and maintenance rules
- `references/csharp-xunit.md`, `references/react-vitest-jest.md`, `references/pcf-testing.md` — stack syntax
- `references/legacy-characterization.md` — characterization technique
- `references/testing-anti-patterns.md` — mock failure modes
- `scripts/detect_test_framework.py` — context detection
- `scripts/verify_output.py` — generated-output guardrail
