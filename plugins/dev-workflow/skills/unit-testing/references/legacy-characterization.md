# Existing Behavior Characterization

Characterization is a technique within `Existing Behavior Preservation`, not a
legacy-only testing path. Use it when running code needs protection before a
refactor, extension, or later behavior decision and current behavior is not
fully specified. Do not change production behavior in this workflow.

## Purpose and scope

Capture what the code does today so an unintended later change fails loudly.
A characterization test pins current observable behavior; it does not prove
that behavior is correct. Pin only the target's blast radius and meaningful
branches, boundaries, errors, and side effects, rather than trying to cover an
entire module.

If an approved contract already describes the intended behavior, use the
normal new/change behavior strategy. If observed behavior conflicts with that
contract and intent is unclear, stop for user direction.

## Safe loop

1. Discover instructions, resolve canonical ownership, and capture a GREEN
   baseline as required by `existing-behavior.md`.
2. Inventory behavior and prioritize regression risks before choosing cases.
3. Find the smallest seam needed to invoke the unit. Prefer a behavior-neutral
   injected boundary or wrapper for a hard external dependency.
4. Call the code with representative inputs, observe the actual output, and
   pin that output with a behavior-focused assertion.
5. Repeat for meaningful risk paths; record every intentional uncovered gap
   and reason in the registry.
6. Run the relevant suite, then back-link owned tests to the registry.

Keep seam creation minimal and behavior-preserving. Do not reformat or clean up
while the safety net is absent. Never add production methods that exist only
for tests; use a test helper, fixture, or injected dependency instead.

## Known Quirk policy

When a current result looks suspicious but must remain pinned, label it
`Known Quirk` in both authoritative registry metadata and the per-test header.
State the observable current result and why it is pinned. Never describe the
quirk as correct, expected, approved, or a requirement.

```csharp
// Known Quirk: pins the current odd-cent result; correctness is not asserted.
[Fact]
public void Characterize_TaxRounding_For_OddCents() { /* ... */ }
```

The later fix is a separate approved behavior change. A failing
characterization test is evidence that current behavior changed; confirm intent
before replacing its baseline.

## Approval and snapshots

Direct test requests still require approved behavior/risk cases. An approved
`implement-plan` task or `design-backbone` Test Coverage Matrix satisfies that
same gate; do not ask twice. Registry selection, ownership, headers, and
back-links follow `test-case-management.md`.

For large, structured, or rendered output, an approval/snapshot baseline can
be the characterization assertion: use C# Verify/ApprovalTests or a small,
intentional Vitest/Jest/PCF snapshot. Commit approved baseline artifacts and
review every diff as a behavior change. Never snapshot an entire page or object
merely for convenience.
