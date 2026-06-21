---
name: unit-testing
description: Generate best-practice unit & component tests for C# (xUnit) and React/PCF (Vitest/Jest+RTL). Use when asked to write or add unit tests, cover requirements, raise coverage, or pin legacy behavior.
---

# Unit Testing

## Overview

Produce unit and component tests that are **traceable** (each test maps to a requirement or an observed behavior), **deterministic** (no flaky timing or shared state), and **framework-native** (match what the project already uses). The skill covers the unit + component layers of the test pyramid; end-to-end browser flows are out of scope (use the `qa-engineer` `e2e` phase + `browser-skill`).

The hardest part of testing is not syntax — it is choosing *what* to test and *how* to protect existing behavior. This skill leads with that decision, then defers stack syntax to per-language references so the core stays small.

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

## Step 3: Choose strategy and gather requirements

Apply the decision tree. Then establish *what good looks like*:

- **From a spec/plan/PRD** — extract acceptance criteria; each becomes one or more tests, recorded in a requirement→test mapping table.
- **From code only** — read the target, list its behaviors, branches, and boundaries; each observable behavior becomes a test.
- **For legacy** — first capture current outputs as the baseline (do not "fix" behavior in the same pass).

Keep a mapping so coverage is auditable:

| Requirement / Behavior | Test(s) | Strategy |
|---|---|---|
| AC-1: rejects expired order | `Rejects_ExpiredOrder` | spec-first |

## Step 4: Write the tests

Read `references/best-practices.md` (shared rules: AAA, naming, mock-at-boundary, determinism), then the stack reference for syntax:

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

## Step 5: Spec-first / parallel mode

When generating tests *while* an implementer builds the function (e.g. dispatched concurrently from `implement-plan`):

- Derive tests from the **spec/acceptance criteria**, not from code that may not exist yet.
- It is expected and correct for these tests to be **RED** (failing/not-compiling) until the implementation lands — they encode the contract.
- Never write to the same files the implementer writes. Tests live in the test project/folder only; **never modify source code**.

## Verify Output (Guardrail)

This is Step 6 — the final guardrail. For already-implemented targets, run the suite and confirm green (xUnit `dotnet test`; Vitest `npx vitest run`; Jest `npx jest`). For spec-first tests, confirm they compile and fail for the *right* reason. Confirm the **baseline** tests from Step 2 are still green (you didn't break or weaken an existing test).

Then run the output guardrail and fix any FAIL:

```bash
scripts/verify_output.py <test-file-or-dir> [--existing <existing-tests-dir>]
```

It checks the deterministic acceptance criteria: tests exist for the target, follow the naming/AAA convention, and a requirement→test mapping is present. Pass `--existing` to also **warn on a generated test name that duplicates an existing one** (the maintenance check from Step 2).

## Resources

- `references/best-practices.md` — shared testing principles and the requirement-mapping format
- `references/csharp-xunit.md`, `references/react-vitest-jest.md`, `references/pcf-testing.md` — per-stack syntax
- `references/legacy-characterization.md` — pinning current behavior as a regression net
- `scripts/detect_test_framework.py` — deterministic stack/framework detection
- `scripts/verify_output.py` — output guardrail
