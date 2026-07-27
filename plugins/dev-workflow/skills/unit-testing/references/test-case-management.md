# Test-Case Registry and Traceability

Use one registry for each testable change or preservation target. It is the
cross-framework source of truth; framework-native tags are optional additions
only when the project already supports them.

## Resolve the registry and owner

Resolve the registry in this order:

1. Existing registry for the target.
2. Approved plan or design artifact.
3. Project convention.
4. Canonical test file.

Do not assume a design artifact exists for code-only or Existing Behavior work.
Reuse the canonical test owner for the same subject, module, fixture, and
project convention. If equally valid owners remain, stop for user direction;
never create a parallel test file silently.

## Approval gate

For a direct unit-test request, present the behavior/risk case list and wait
for approval before changing test code. An approved `implement-plan` task or
`design-backbone` Test Coverage Matrix already satisfies this gate: derive the
cases from it and do not request approval again.

## Registry format

Use stable IDs and record both intent and implementation state:

```markdown
# Test Cases: <target>

| ID | Behavior / risk | Priority | Status | Coverage / reason | Covered by |
|---|---|---|---|---|---|
| TC-001 | Returns total for valid order | P0 | Implemented | Covered | `OrderTests.Should_Total...` |
| TC-002 | Rejects an expired approval | P1 | Pending | Uncovered: external fixture unavailable | *(not yet implemented)* |
| TC-003 | Rounds odd cents down | P1 | Implemented | Known Quirk: pinned current result | `OrderTests.Characterize...` |
```

`Coverage / reason` is authoritative registry metadata. Every intentional
uncovered gap must name its reason (for example, unavailable dependency,
out-of-scope integration boundary, or pending product decision); never hide it
behind a coverage percentage. Coverage percentage detects gaps only, not
completion.

For a `Known Quirk`, state the current observable result and why it is pinned.
It preserves current behavior without claiming that behavior is correct or
approved. The registry metadata and the matching test header must both carry
the `Known Quirk` label.

## Required test-file header

Each owned test file identifies the exact registry path and target:

```csharp
// Test registry: .docs/order-validation.test-cases.md
// Subject: OrderService
```

```typescript
// Test registry: .docs/order-validation.test-cases.md
// Subject: OrderService
```

The registry path and per-test headers are the authoritative traceability
metadata across C#, React, and PCF. A `Trait("TestCase", "TC-001")` or a TC ID
in a JS test name may help runner filtering when already conventional, but
does not replace the header.

## Per-test header

Use a QA-readable header that names the TC ID, setup, action, and observable
verification. Include the exact `Known Quirk` label when applicable.

```csharp
/// TC-003: Rounds odd cents down.
/// Known Quirk: pins the current result; correctness is not asserted.
[Fact]
public void Characterize_Rounding_For_OddCents() { /* ... */ }
```

```typescript
/** TC-003: rounds odd cents down.
 * Known Quirk: pins the current result; correctness is not asserted. */
it('TC-003: characterizes odd-cent rounding', () => { /* ... */ });
```

One TC per test is the default. Parameterized tests may cover multiple cases
when their header and native tags/name list every ID. Describe observable
behavior, not mock setup or private implementation.

## Reconcile and back-link

Before adding a row, find existing same-subject coverage. Leave correct
coverage, update the owned test for an approved change, add only an uncovered
meaningful behavior, and flag contradictions for review. Do not duplicate a
behavior or weaken a passing test to make a suite green.

After the relevant suite is GREEN, update `Covered by` with the owned file and
test name. Keep pending and intentionally uncovered rows visible with their
reasons. If a test is renamed, update its back-link in the same change.

`verify_output.py --test-cases <registry.md>` validates registry IDs,
file-level registry headers, test references, and traceability warnings.
