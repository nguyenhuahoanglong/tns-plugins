# Test-Case List Management & QA Traceability

How to derive a reviewable test-case list from a design document, maintain it long-term
without redundancy, and annotate tests so QA can read the code and know exactly which
test case each method covers.

## Source of truth

1. **Primary**: the design document in the project's `.docs/` folder (or the doc the user points at).
2. **Secondary**: ADO work items / design tasks for the same feature.
3. **Conflict rule**: if the `.docs/` design document and an ADO task disagree on a behavior,
   the `.docs/` document **wins** — but **stop and confirm the conflict with the user first**
   (quote both versions). Never silently pick one.

## The test-case file

One file per design document, next to it, named after it:

```
.docs/order-validation.md            <- design document
.docs/order-validation.test-cases.md <- derived test-case registry (this file)
```

This file is the **ID registry and long-lived traceability matrix** for the feature. It is
maintained, never regenerated from scratch.

### Format

```markdown
---
source-design: .docs/order-validation.md
test-project: Tests/OrderValidation.Tests
last-reconciled: 2026-07-15
---

# Test Cases — Order Validation

| ID | Title | Type | Design ref | Covered by |
|----|-------|------|-----------|------------|
| TC-001 | Accept order within credit limit | happy | § 3.1 | `OrderValidatorTests.cs` → `Should_AcceptOrder_When_WithinCreditLimit` |
| TC-002 | Reject order when credit limit is expired | error | § 3.2 | `OrderValidatorTests.cs` → `Should_RejectOrder_When_CreditExpired` |
| TC-003 | Boundary: order total exactly equals credit limit | boundary | § 3.1 | *(not yet implemented)* |

## Not covered / out of scope

- § 5 email notification — integration behavior, covered by E2E suite, not unit tests.
```

- **ID**: `TC-NNN`, auto-numbered per file starting at `TC-001`.
- **Type**: `happy` | `error` | `boundary` | `edge` | `characterization` — makes coverage shape visible at a glance.
- **Design ref**: section/heading in the source design doc the case verifies.
- **Covered by**: test file → test method(s). Empty (`*(not yet implemented)*`) until tests are green — this doubles as the status column.
- **Not covered / out of scope**: design aspects deliberately excluded, with the reason. Gaps must be explicit, never silent.

## ID rules (non-negotiable)

- IDs are **stable forever**: never renumber, never reuse a retired ID, never reorder to "clean up".
- New cases always take the **next unused number**, even if earlier cases were removed.
- An ID that appears in test code is a public contract with QA — breaking it breaks their mapping.

## Generating the list (first run)

1. Read the design document end-to-end. Extract every testable aspect: stated behaviors,
   validation rules, error branches, boundaries, state transitions, calculations.
2. Draft one test case per aspect (split "and also" cases). Assign IDs sequentially.
3. Fill **Not covered / out of scope** for aspects that are not unit-testable (E2E flows,
   infra behavior) with the reason.
4. Write the file, then **hard stop**: present the list in chat and wait for the user to
   review/edit/approve. **No test code is written before explicit approval.**
   Exception — gate delegation: inside a workflow whose test plan the user already explicitly
   approved (`implement-plan` approval gate, `design-backbone` Phase 3), derive the cases from the
   approved artifact and continue without a second stop; registry, headers, and back-linking
   still apply.

## Reconciling the list (re-runs)

When the file already exists (design changed, new methods added, coverage extended):

1. **Load the existing file first.** It is the baseline; the design doc is the target.
2. **Dedup before adding**: for each candidate new case, check semantic overlap with existing
   rows (same behavior, same branch, same boundary). Prefer **updating the existing row**
   (title/design-ref wording) over adding a near-duplicate with a new ID.
3. Classify every change as one of:
   - **ADD** — genuinely new aspect → next unused `TC-NNN`.
   - **UPDATE** — existing aspect whose wording/design-ref changed → same ID, edited row.
   - **REMOVED FROM DESIGN** — the design no longer contains the aspect → do **not** delete the
     row silently; flag it in the diff and let the user decide (delete row + its tests, or keep).
4. **Show the diff before saving**: present ADD/UPDATE/REMOVED tables in chat and wait for
   approval, then write the file and bump `last-reconciled`.

## QA-readable traceability in test code

Every generated test carries the mapping **in the code itself**, in natural language a QA
engineer can read without opening the design doc.

### File-level header — which registry generated this file

Top of every generated test file:

```csharp
// Test cases: .docs/order-validation.test-cases.md
// Design doc: .docs/order-validation.md
```

```typescript
// Test cases: .docs/order-validation.test-cases.md
// Design doc: .docs/order-validation.md
```

### Per-test header — one-line summary + numbered steps

Plain English, written for QA (no jargon, no implementation detail). State what is set up,
what is done, and what is verified — as a test script.

**C# / xUnit** — XML doc comment + `Trait` (machine-filterable: `dotnet test --filter "TestCase=TC-004"`):

```csharp
/// <summary>
/// TC-004: Reject order when credit limit is expired
/// Steps:
///   1. Create customer with credit approval expired yesterday
///   2. Submit a new order for that customer
///   3. Verify order rejected with error CREDIT_EXPIRED
/// Design: .docs/order-validation.md § 3.2
/// </summary>
[Fact]
[Trait("TestCase", "TC-004")]
public void Should_RejectOrder_When_CreditExpired() { ... }
```

**Vitest / Jest (React, PCF)** — JSDoc block + TC ID in the test name (the name is the trait;
it shows in runner output and supports `--testNamePattern "TC-004"`):

```typescript
/**
 * TC-004: Reject order when credit limit is expired
 * Steps:
 *   1. Create customer with credit approval expired yesterday
 *   2. Submit a new order for that customer
 *   3. Verify order rejected with error CREDIT_EXPIRED
 * Design: .docs/order-validation.md § 3.2
 */
it('TC-004: rejects the order when the credit limit is expired', () => { ... });
```

Rules:
- **One TC per test** is the default. A `[Theory]`/`it.each` may cover several boundary TCs —
  list every covered ID in the header and one `Trait` per ID (`[Trait("TestCase","TC-003")]
  [Trait("TestCase","TC-005")]`) or all IDs in the test name.
- Steps describe **observable behavior**, not mocks or internals ("Create customer with expired
  credit", not "Setup NSubstitute ICreditRepo to return...").
- The header is for QA; the test name is for developers. Both carry the TC ID.

## Back-linking (after tests are green)

Once the suite passes, update the registry so traceability works in both directions:

1. For each implemented TC, fill **Covered by** with `<test file>` → `<method/test name(s)>`.
2. Leave unimplemented rows as `*(not yet implemented)*` so remaining work is visible.
3. If a test method is later renamed, the Covered-by entry must be updated in the same change.

Verification (`scripts/verify_output.py --test-cases <registry.md>`) checks:
- every `TC-NNN` referenced in test code exists in the registry (**FAIL** on unknown ID),
- every registry TC has at least one referencing test (**WARN** — may be intentionally pending),
- generated test files carry the file-level registry header (**WARN** if missing).
