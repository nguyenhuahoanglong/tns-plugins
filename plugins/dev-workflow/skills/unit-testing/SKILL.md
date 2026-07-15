---
name: unit-testing
description: Generate a reviewable test-case list from a design document, then best-practice unit & component tests for C# (xUnit) and React/PCF (Vitest/Jest+RTL) with QA-readable traceability. Use when asked to write or add unit tests, generate test cases, cover requirements or a design doc, raise coverage, or pin legacy behavior.
---

# Unit Testing

## Overview

Produce unit and component tests that are **traceable** (each test maps to a documented test case QA can read), **deterministic** (no flaky timing or shared state), and **framework-native** (match what the project already uses). The skill covers the unit + component layers of the test pyramid; end-to-end browser flows are out of scope (use the `qa-engineer` `e2e` phase + `browser-skill`).

The hardest part of testing is not syntax — it is choosing *what* to test and *how* to protect existing behavior. This skill leads with that decision, makes it reviewable **before any code is written** (the test-case list gate), then defers stack syntax to per-language references so the core stays small.

Three commitments the output must always honor:

1. **Design coverage** — test cases are derived from the design document systematically, and anything not covered is listed explicitly, never silently dropped.
2. **Review before code** — the user approves the test-case list before a single test is written.
3. **QA readability** — every test carries a natural-language header (TC ID, summary, steps) so QA can open the test file and know which documented test case each method covers.

## When to use

Trigger when asked to: write/add/generate unit or component tests, raise coverage, write tests alongside an in-progress implementation (spec-first), or create a safety net before refactoring legacy code. For full-browser E2E, defer to `qa-engineer`.

## Decision Tree

Pick the strategy *before* writing anything — it changes what "correct" means.

```
What is the target?
|-- Spec/plan exists, code NOT written yet  -> Spec-first (parallel): write RED tests from acceptance criteria
|-- New code already written                -> Behavior + requirement coverage: assert intended behavior
|-- Legacy code, no tests, about to change  -> Characterization FIRST (pin current behavior), then add tests for the change
|-- Existing tests, coverage too low        -> Gap-driven: cover untested branches/edge cases only
```

The legacy path is the key one for your goal of *"future changes won't break current logic."* See `references/legacy-characterization.md` — characterization tests record what the code **does today** (even if arguably wrong), so a later refactor that changes behavior fails loudly.

## Step 1: Detect the project's testing context

Run the detector to avoid guessing the stack, framework, or conventions:

```bash
scripts/detect_test_framework.py <project-or-file-path>
```

It reports the stack (C#/React/PCF), the installed test framework (e.g. Vitest vs Jest — never assume), the test directory/naming convention, and whether a test project/config already exists. **Match what it finds.** If a framework is already present, never introduce a different one. Also read the project's `AGENTS.md` for test conventions.

## Step 2: Audit existing tests (maintain, don't duplicate)

Before writing anything, find and reconcile with tests that already exist — this is what keeps the suite coherent instead of accreting duplicates or leaving stale tests in place.

1. **Locate** existing tests for the target: `grep`/Grep the test files for the unit/class/function name under test (the detector's file list is only a sample, not a content scan).
2. **Baseline**: run the existing suite and record what currently passes. You cannot distinguish "I just caught a regression" from "this was already red" without a known-green starting point.
3. **Map** each behavior you intend to cover to any existing test, then decide per behavior:

| Existing state | Action |
|---|---|
| Covered, test still correct | **Leave it** — do not write a duplicate |
| Covered, but the spec/behavior changed | **Update that test** — do not add a parallel one |
| Not covered | **Add** a new test |
| Existing test now contradicts the current spec | **Flag for human review** — do not silently rewrite it |

Maintenance rules (see `references/best-practices.md` → *Maintaining an existing suite*):
- Never delete or weaken a **passing** test to make code or another test go green.
- A previously-green test that turns red after a change is a **signal** (most often a real regression) — investigate before touching it, don't "fix it away."
- Characterization tests are load-bearing: a red one means behavior changed — confirm that was intended.

## Step 3: Choose strategy and locate the design source

Apply the decision tree. Then find the source of truth for *what good looks like*:

- **Primary**: the design document in the project's `.docs/` folder (or whatever doc the user points at).
- **Secondary**: ADO work items / design tasks. If ADO and the `.docs/` document **conflict**, the `.docs/` document wins — but **confirm the conflict with the user first**, quoting both versions.
- **From code only** (no design doc) — read the target and list its behaviors, branches, and boundaries; these become the test cases.
- **For legacy** — first capture current outputs as the baseline (do not "fix" behavior in the same pass); characterization cases go in the list too, typed `characterization`.

## Step 4: Generate the test-case list — REVIEW GATE (hard stop)

**Never write test code before the user approves the test-case list.** Follow `references/test-case-management.md` for the full format and maintenance rules. In short:

1. Extract every testable aspect from the design document (behaviors, validation rules, error branches, boundaries, calculations). Draft one case per aspect with auto-numbered stable IDs (`TC-001`, `TC-002`, …).
2. Write `{design-doc-name}.test-cases.md` **next to the design document** (e.g. `.docs/order-validation.md` → `.docs/order-validation.test-cases.md`), including a **Not covered / out of scope** section so gaps are explicit.
3. If the file **already exists**, reconcile instead of regenerating: keep IDs stable (never renumber/reuse), dedup new candidates against existing rows (prefer updating a row over adding a near-duplicate), and **show the ADD/UPDATE/REMOVED diff in chat before saving**.
4. **Stop.** Present the list (or diff) and wait for the user to review, edit, and explicitly approve. Only then continue to Step 5.

**Gate delegation**: when this skill runs inside a workflow whose test plan the user already explicitly approved — `implement-plan`'s approval gate (task Definition-of-Done items) or `design-backbone`'s Phase 3 approval (Test Coverage Matrix) — that approval satisfies this gate. Derive the cases from the approved artifact and continue without a second stop. The registry, traceability headers, and back-linking still apply.

This file is a long-lived registry QA relies on — maintain it, don't regenerate it.

## Step 5: Write the tests

Read `references/best-practices.md` (shared rules: AAA, naming, mock-at-boundary, determinism), then the stack reference for syntax. If any test involves a mock, also read `references/testing-anti-patterns.md` first — it covers the failure modes (asserting on mocks instead of behavior, test-only production methods, incomplete mocks, mocking without understanding the real dependency) before you write them.

| Stack | Reference | Framework |
|---|---|---|
| C# .NET (Functions, Dataverse plugins, class libs) | `references/csharp-xunit.md` | xUnit + NSubstitute + FluentAssertions; FakeXrmEasy for plugins |
| React / TypeScript | `references/react-vitest-jest.md` | Vitest *or* Jest (detected) + React Testing Library + MSW |
| PCF (TypeScript control) | `references/pcf-testing.md` | Jest + RTL with mocked PCF context |

Core rules (full detail in `best-practices.md`):
- **AAA** structure; one logical behavior per test; descriptive names like `Should_<behavior>_When_<condition>`.
- **Mock at the boundary** (external services, DB, network, PCF context) — not internal collaborators. Over-mocking couples tests to implementation.
- **Test behavior, not implementation** — tests should survive a refactor that preserves behavior. (This is exactly why characterization tests protect legacy code.)
- **Deterministic** — inject clock/IDs/randomness; no real network, no `Date.now()`/`Guid.NewGuid()` leaking into assertions.

**QA traceability is mandatory** (templates in `references/test-case-management.md`):
- Every test file opens with a header citing the test-case registry and design doc it was generated from.
- Every test method carries a natural-language header: `TC-NNN: <one-line summary>`, numbered **Steps** (setup → action → verification, written for QA — no mocks/internals), and the design-doc reference.
- xUnit additionally gets `[Trait("TestCase", "TC-NNN")]`; Vitest/Jest put the TC ID in the test name (`it('TC-004: rejects ...')`).

## Step 6: Spec-first / parallel mode

When generating tests *while* an implementer builds the function (e.g. dispatched concurrently from `implement-plan`):

- The test-case list gate (Step 4) still applies — derive the cases from the **spec/acceptance criteria**, get approval, then write the RED tests. Not from code that may not exist yet.
- If any test involves a mock, read `references/testing-anti-patterns.md` before writing it — the same failure modes (incomplete mocks, mocking without understanding the real dependency) apply to spec-first tests.
- It is expected and correct for these tests to be **RED** (failing/not-compiling) until the implementation lands — they encode the contract.
- Verify each RED test fails for the **expected reason** — an assertion about missing/incorrect behavior — not a typo, a missing import, or a setup error. A compile error or import error is not a valid RED; fix the test scaffolding until the failure is the assertion itself.
- Never write to the same files the implementer writes. Tests live in the test project/folder only; **never modify source code**.

## Step 7: Verify and back-link (Guardrail)

For already-implemented targets, run the suite and confirm green (xUnit `dotnet test`; Vitest `npx vitest run`; Jest `npx jest`). For spec-first tests, confirm they compile and fail for the *right* reason. Confirm the **baseline** tests from Step 2 are still green (you didn't break or weaken an existing test).

Then run the output guardrail and fix any FAIL:

```bash
scripts/verify_output.py <test-file-or-dir> [--existing <existing-tests-dir>] [--test-cases <registry.md>]
```

It checks the deterministic acceptance criteria: tests exist for the target, follow the naming/AAA convention, and a requirement→test mapping is present. Pass `--existing` to **warn on a generated test name that duplicates an existing one** (Step 2). Pass `--test-cases` to check traceability against the registry: every `TC-NNN` referenced in tests exists (FAIL on unknown IDs), every registry case has a referencing test (WARN if pending), and file headers cite the registry.

Finally, **back-link**: update the registry's *Covered by* column with the test file → method name(s) for every implemented TC, so QA can navigate registry → code and code → registry (see `references/test-case-management.md`).

## Resources

- `references/test-case-management.md` — test-case list format, review gate, ID stability/reconciliation, QA traceability headers, back-linking
- `references/best-practices.md` — shared testing principles and the requirement-mapping format
- `references/csharp-xunit.md`, `references/react-vitest-jest.md`, `references/pcf-testing.md` — per-stack syntax
- `references/legacy-characterization.md` — pinning current behavior as a regression net
- `references/testing-anti-patterns.md` — mock-related failure modes to check before writing tests
- `scripts/detect_test_framework.py` — deterministic stack/framework detection
- `scripts/verify_output.py` — output guardrail
