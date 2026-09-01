# Unit Testing Best Practices

These rules apply to C#, React, and PCF. Stack references provide syntax;
this reference supplies judgment.

## Write behavior-focused tests

- Before writing the body, name the production change that should fail the
  test and why that change is a bug. Useful targets include a wrong branch,
  argument, return, boundary result, validation, or missing side effect.
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

## Keep tests falsifiable

- Derive expected values independently with literals or hand-checked fixtures.
  Do not reuse the code under test, its builder, or its helpers to calculate
  the expected result; mirrored logic can agree with the same bug.
- Reject source-text tests. Grepping a script, skill, prompt, or configuration
  proves only that text exists; run the artifact against controlled inputs and
  assert its output, side effects, or exit code. Human-facing prose earns no
  automated test.
- Reject change detectors that only pin a constant, exact wording, or private
  structure. Assert the consumer-visible behavior that depends on the decision,
  such as the number of retries and the absence of an extra attempt.
- Test the boundary owned by the production code: the route it registers,
  payload it emits, query it builds, or state it changes. Framework mechanics
  belong to the framework maintainers. Use one narrow characterization test
  only when a surprising upstream assumption is itself a real integration risk.

If no realistic production bug would fail the proposed test, redesign it
around observable behavior or omit it. Coverage alone does not justify a test.

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
5. Mentally mutate realistic branches, arguments, returns, validations, state
   changes, and side effects. Each in-scope mutation must fail at least one test
   or remain visible as an intentional uncovered gap.
6. After a GREEN run, back-link the owned test in the registry and retain
   uncovered gaps with reasons.

Avoid assertions on irrelevant logs, call order, or mock plumbing; giant shared
fixtures; real sleeps/timers; and broad snapshots. Snapshot only intentional,
small surfaces when a snapshot is the right characterization tool.
