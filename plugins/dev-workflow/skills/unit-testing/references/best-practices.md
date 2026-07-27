# Unit Testing Best Practices

These rules apply to C#, React, and PCF. Stack references provide syntax;
this reference supplies judgment.

## Write behavior-focused tests

- Assert observable outputs, errors, rendered state, persisted state, or
  meaningful boundary effects; do not assert private implementation shape.
- Keep one logical behavior per test. Multiple assertions are fine when they
  prove that one behavior.
- Use Arrange, Act, Assert with one clear Act. Give every test its own state;
  never rely on execution order or shared mutable state.
- Make inputs deterministic: inject clocks, IDs, random values, and external
  boundaries instead of relying on real time, generated IDs, or randomness.
- Name the behavior and condition: C# `Should_<Behavior>_When_<Condition>` or
  a readable JS/TS sentence inside a unit-focused `describe`.

## Cover behavior and risk

Inventory meaningful observable behavior, not lines:

- Normal and alternative branches.
- Boundaries: null, empty, zero, maximum, off-by-one, and duplicates where
  relevant.
- Errors, validation, and failure outcomes.
- Side effects, state changes, and calls across external boundaries.

Prioritize risks to callers, persisted data, calculations, permissions,
external requests, error handling, and important boundaries. A coverage
percentage is a gap detector only. Each intentionally uncovered gap must stay
visible in authoritative registry metadata with a concrete reason; do not add
empty tests merely to raise a number.

## Mock at boundaries

Mock databases, HTTP/APIs, message buses, filesystem, clocks, PCF host context,
and other external boundaries. Prefer cheap, deterministic real collaborators
or fakes for pure logic and simple in-memory behavior. Do not mock helpers or
value objects inside the unit; that couples tests to implementation and makes
safe refactors fail. Read `testing-anti-patterns.md` before any mock changes.

## Traceability and Existing Behavior

Use the registry hierarchy and authoritative registry/header metadata in
`test-case-management.md`. For Existing Behavior Preservation, reconcile the
same-subject suite before adding tests: leave correct coverage, update the
canonical owned test only for an approved change, add the smallest missing
behavior, and flag contradictions for review.

Use `Known Quirk` only for suspicious current behavior that must remain pinned.
Put it in registry metadata and the test header, state what happens today and
why it is pinned, and never imply it is correct. Detailed workflow and stop
rules live in `existing-behavior.md`; this replaces legacy-only handling.

## Maintain a trustworthy suite

1. Find existing tests for the same subject before writing a new one.
2. Capture the relevant GREEN baseline and record pre-existing failures.
3. Do not delete, loosen, or duplicate passing coverage to make another test
   pass. Treat a new red test as evidence to investigate.
4. Keep characterization pins load-bearing: a failing pin means current
   behavior changed and needs confirmation before any baseline update.
5. After a GREEN run, back-link the owned test in the registry and retain
   uncovered gaps with reasons.

Avoid assertions on irrelevant logs, call order, or mock plumbing; giant shared
fixtures; real sleeps/timers; and broad snapshots. Snapshot only intentional,
small surfaces when a snapshot is the right characterization tool.
