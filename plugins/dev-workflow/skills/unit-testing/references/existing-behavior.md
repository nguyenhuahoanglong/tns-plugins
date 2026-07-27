# Existing Behavior Preservation

Use this workflow when running code needs protection without an approved behavior change. It applies to healthy code, legacy code, suspicious behavior, and coverage gaps in an existing method or function. Do not change production behavior in this workflow.

## Ordered workflow

Perform these actions in order:

1. Discover applicable instructions.
2. Resolve canonical test ownership.
3. Capture a GREEN baseline.
4. Inventory observable behavior.
5. Map meaningful regression risks.
6. Reconcile existing tests.
7. Satisfy the test-case approval gate.
8. Write and verify owned tests.
9. Back-link the registry.

Do not reorder baseline capture after writing tests, or ownership after choosing a destination. Stop when the rules below require user direction.

## 1. Discover applicable instructions

Before analyzing tests, report candidates in this deterministic order:

1. Target-nearest `AGENTS.md` files outward to project root.
2. Target-nearest tool-specific files, such as `CLAUDE.md`, outward to project root.
3. Test-project `README.md` and test documentation.
4. Test configuration.
5. Observed suite conventions.

Apply precedence as: explicit user instructions; nearest scoped project instructions; ancestor project instructions; test documentation; test configuration and observed convention; then skill defaults. Same-scope conflicts, or instructions without declared precedence, require user direction. The detector provides candidates and evidence; it does not resolve a conflict for you.

## 2. Resolve canonical test ownership

Find existing tests for the same subject under test, module, fixture, and project convention. Reuse the canonical owner and its framework, naming, helper, and fixture patterns.

Resolve a registry in this order:

1. Existing registry.
2. Approved plan or design artifact.
3. Project convention.
4. Canonical test file.

Registry metadata and the test file header are authoritative cross-framework traceability. Add native framework tags only when current project conventions support them. If multiple owners remain equally valid, stop and ask the user. Never create a parallel test file just to avoid the decision.

## 3. Capture a GREEN baseline

Run the existing relevant suite before changing tests and record the command, pass result, and any pre-existing failures. A baseline distinguishes a new regression from an already-red suite. If a relevant suite is not GREEN, stop for direction unless the user explicitly authorizes work against that baseline.

## 4. Inventory observable behavior

List the method or function's observable behavior, including meaningful:

- Normal and alternative branches.
- Boundaries, null/empty values, and limits.
- Errors, validation, and failure outcomes.
- Side effects, calls across external boundaries, and state changes.

Map each item to an existing test, a new case, an intentionally uncovered gap with its reason, or a request for clarification. Coverage percentage may reveal a missed area but is never proof of sufficient behavior coverage.

## 5. Map regression risk

Prioritize behaviors whose change would affect callers, persisted data, external requests, error handling, calculations, permissions, or important boundaries. Prefer a small set of meaningful behavior tests over implementation-coupled tests that merely increase coverage.

When current behavior looks suspicious but must be preserved, record it as `Known Quirk` in both registry metadata and the test header. State what happens today and why it is pinned; do not state that it is correct.

## 6. Reconcile existing tests

For each inventoried behavior:

| Existing state | Action |
|---|---|
| Covered and still correct | Leave it; do not duplicate it. |
| Covered but approved behavior changed | Update the owned test. |
| Not covered | Add the smallest owned test. |
| Contradicts the approved contract or observed behavior | Flag it for human review. |

Do not delete or weaken a passing test to make code green. A previously GREEN test that becomes red is evidence to investigate. A characterization test is load-bearing: a failure means behavior changed and needs confirmation.

## 7. Approval gate

For a direct request, present the behavior/risk test-case list and wait for approval before test code. An approved `implement-plan` task or `design-backbone` Test Coverage Matrix supplies the same approval; derive cases from it and do not ask again.

The list retains stable IDs, reconciliation changes, registry identity, `Known Quirk` labels, and intentionally uncovered gaps with reasons.

## 8–9. Verify and back-link

Run the relevant suite and the output guardrail after writing tests. Confirm the baseline remains GREEN, tests use the canonical owner, headers identify the registry, and each `Known Quirk` appears in both required locations. Update the registry's coverage/back-link field with the owned test file and method. Keep pending or uncovered gaps visible with their reasons.

## Stop rules

Stop and ask the user when:

- Applicable instructions conflict at the same scope or lack a declared precedence.
- Test ownership remains ambiguous after same-subject, module, fixture, and convention analysis.
- The relevant existing baseline is not GREEN without explicit authorization.
- The observed behavior conflicts with an approved contract and the intended behavior cannot be determined.
