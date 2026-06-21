# Unit Testing Best Practices (cross-stack)

Shared rules that apply regardless of language. The per-stack references show the syntax; this is the *judgment*.

## What makes a good unit test

- **Tests behavior, not implementation.** Assert observable outcomes (return values, calls to boundaries, rendered output), not private internals. A correctness-preserving refactor must keep tests green — otherwise the test is testing the code's shape, not its contract.
- **One logical behavior per test.** Multiple `assert`s are fine if they verify one behavior; if a test needs "and also" in its name, split it.
- **Fast and isolated.** No shared mutable state between tests; no ordering dependency; each test sets up its own world.
- **Deterministic.** Inject the clock, IDs, and randomness. Never assert against `DateTime.Now` / `Date.now()` / `Guid.NewGuid()` / `Math.random()` produced inside the code under test.

## AAA structure

Every test reads as **Arrange** (set up inputs + mocks), **Act** (invoke the one thing under test), **Assert** (verify the outcome). Keep the three visually separated. Exactly one "Act" — if there are two, it is two tests.

## Naming

Use a name that states behavior and condition so a failure is self-describing:

- C#: `Should_<ExpectedBehavior>_When_<Condition>` (method name) or `Method_State_Expected`.
- JS/TS: `it('returns 0 when the cart is empty', ...)` — full sentence under a `describe('<unit>')`.

A reader should know what broke from the test name alone, without opening the body.

## Mock at the boundary — not internal collaborators

Mock things the unit *talks to the outside world* through: databases, HTTP/APIs, message buses, the PCF host context, the filesystem, the clock. Do **not** mock the class's own helper methods or value objects — that couples the test to internal structure and makes refactors fail for no real reason. Over-mocking is the most common way unit tests become a maintenance tax.

Prefer real collaborators when they are cheap and deterministic (pure functions, in-memory stores). Use [fakes](https://martinfowler.com/bliki/TestDouble.html) (in-memory implementations) over heavy mock setups when a fake exists (e.g. EF Core in-memory, MSW for HTTP, FakeXrmEasy for Dataverse).

## Coverage philosophy

Coverage is a *gap finder*, not a goal. Chase **branches and edge cases**, not a percentage:
- Happy path (P0)
- Each error/validation branch (P1)
- Boundaries: empty, null, zero, max, off-by-one, duplicates (P2)
- Concurrency/ordering only where the code actually depends on it

Do not write tests purely to raise a number — a test with no meaningful assertion is worse than no test.

## Requirement → test traceability

Maintain a mapping so coverage is auditable and gaps are visible. Put it at the top of the test file (comment) or in the QA report:

```
| Requirement / Behavior            | Test(s)                          | Strategy     |
|-----------------------------------|----------------------------------|--------------|
| AC-1: reject order past cutoff    | Rejects_Order_When_PastCutoff    | spec-first   |
| AC-2: apply 10% loyalty discount  | Applies_LoyaltyDiscount          | behavior     |
| (legacy) current rounding output  | Characterize_RoundingBehavior    | legacy/pin   |
```

Every acceptance criterion should map to at least one test. Every legacy "pin" should be labeled so reviewers know it captures *current* behavior, not necessarily *correct* behavior.

## Maintaining an existing suite

New tests live next to old ones — reconcile, don't just append. Before adding tests for a target:

1. **Find what's already there.** Search the test files for the unit/symbol under test; the framework detector only samples filenames, it doesn't tell you which behaviors are already covered.
2. **Establish a green baseline.** Run the suite first. A test that was already failing is not your regression; a test that *starts* failing after your change probably is.
3. **Decide per behavior:** covered+correct → leave; covered but spec changed → **update that test in place** (one source of truth per behavior, not two divergent ones); uncovered → add; existing test contradicts the current spec → **flag it for a human**, since "the test is wrong" and "the code is wrong" look identical from here.

Rules that keep the suite trustworthy:
- **Never** delete or loosen a *passing* test to make something else go green — that erases a guarantee. If a test is genuinely obsolete (the behavior was intentionally removed), remove it deliberately and say so.
- A red test is **evidence**, not an obstacle. Read it before changing it; the most expensive bug is the one whose failing test you "fixed" by editing the assertion.
- **Don't duplicate.** Two tests asserting the same behavior double the maintenance and drift apart over time. Prefer one clear test, or a `[Theory]`/`it.each` parameterization.
- **Characterization tests are load-bearing.** A red characterization test means current behavior changed — confirm that was intended before re-pinning the baseline.

## Anti-patterns to avoid

- Asserting on log messages or call order when the behavior doesn't depend on them.
- Tests that pass whether or not the code is correct (no real assertion, or assertion always true).
- Giant setup shared across unrelated tests ("mystery guest").
- Sleeping/real timers for async — use fake timers or awaited promises.
- Snapshotting whole pages/objects so any change "breaks" the test — snapshot small, intentional surfaces only (see `legacy-characterization.md`).
