# Testing Anti-Patterns

Read this before changing a test that uses mocks. Test what the system under
test (SUT) does; a mock isolates an external boundary and is never the outcome
being verified.

## Non-negotiable rules

1. Assert observable SUT behavior, not that mock plumbing ran.
2. Never add a production method solely for tests.
3. Understand a real dependency and its side effects before mocking it.
4. Model the complete real data shape that downstream code can read.
5. Maintain tests with the implementation; do not defer meaningful coverage.

## 1. Assert behavior, not mock calls

```csharp
// Bad: only proves a substitute was called.
repo.Received(1).GetBasePrice("SKU1");

// Good: proves the SUT's observable result.
total.Should().Be(90m);
```

Interaction assertions are valid only when the interaction itself is the
observable contract (for example, publishing a required command). Otherwise,
supplement them with output, state, or boundary-effect verification.

## 2. Do not make production code test-aware

```csharp
// Bad: public production surface exists only for tests.
public void ResetForTests() => _entries.Clear();

// Good: fresh fixture or test helper owns setup and teardown.
private static SessionCache CreateSut() => new SessionCache();
```

Before adding a method, ask whether production callers need it. If not, keep it
in test support or inject the dependency needed to construct the SUT.

## 3. Mock only understood external boundaries

Before mocking, read the real implementation/schema and list its relevant side
effects. If the assertion depends on a write, cache update, validation, or
other effect, keep that part real or fake it faithfully; mock only the slow or
external boundary. Do not mock “to be safe” without evidence.

```ts
// Bad: replaces persistence that the duplicate assertion needs.
vi.mock('./toolCatalog', () => ({ discoverAndCacheTools: vi.fn() }));

// Better: isolate only remote discovery; preserve the configuration write.
vi.mock('./remoteToolDiscovery');
```

## 4. Avoid incomplete or invented mocks

Build mock responses from the real DTO, API contract, schema, or captured
sample. Include every field downstream paths can read, including metadata and
nested state. If the shape is uncertain, inspect or capture the real object;
do not guess from today's assertion.

## 5. Do not treat tests as an afterthought

For approved new or changed behavior, add the relevant tests with the slice:
write the case, make the smallest implementation change, verify it, then
refactor. For Existing Behavior Preservation, retain the GREEN baseline and
characterize meaningful risks before refactoring. Do not claim completion while
meaningful approved behavior has no test or an uncovered-gap reason.

## Fast review checks

- Is mock setup more prominent than the behavior assertion? Simplify it.
- Would the assertion pass with production code removed? It tests the mock.
- Is a production member referenced only by tests? Move responsibility to test
  support.
- Does the test rely on real data, time, ordering, or side effects the mock
  erased? Use a deterministic fake or preserve the needed behavior.
- Did a duplicate test, broad snapshot, shared mystery fixture, real sleep, or
  irrelevant log/call-order assertion appear? Replace it with a focused test.

These guardrails protect both correctness and maintenance cost: minimal,
behavior-focused tests are easier to trust and survive safe refactors.
