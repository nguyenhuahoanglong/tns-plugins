# Testing Anti-Patterns

Load this reference before writing or changing any test that involves a mock. Cross-cutting principles
(AAA, mock-at-boundary, naming, determinism) live in `best-practices.md` — this file is the *failure modes*
of mocking specifically, for both C# (xUnit + NSubstitute) and React (Vitest/Jest + RTL).

**Core principle:** test what the code does, not what the mock does. A mock isolates the unit under test;
it is never itself the thing being verified.

## The Iron Laws

```
1. NEVER assert on mock behavior — assert on the SUT's observable behavior
2. NEVER add test-only methods to production classes
3. NEVER mock a dependency without understanding what the real one actually does
```

## Anti-Pattern 1: Asserting the Mock Instead of the Behavior

**BAD** — proves the substitute was configured, not that the SUT does anything:

```csharp
[Fact]
public void Should_ApplyDiscount_When_CustomerIsPremium()
{
    var repo = Substitute.For<IPriceRepository>();
    repo.GetBasePrice("SKU1").Returns(100m);
    var sut = new OrderService(repo);

    sut.Quote("SKU1", isPremium: true);

    repo.Received(1).GetBasePrice("SKU1");   // only checks the stub was called
}
```

**GOOD** — assert the SUT's output; the call to the collaborator is incidental, not the point:

```csharp
[Fact]
public void Should_ApplyDiscount_When_CustomerIsPremium()
{
    var repo = Substitute.For<IPriceRepository>();
    repo.GetBasePrice("SKU1").Returns(100m);
    var sut = new OrderService(repo);

    var total = sut.Quote("SKU1", isPremium: true);

    total.Should().Be(90m);   // behavior, not mock plumbing
}
```

### Gate function

```
BEFORE the final assertion in a test:
  Ask: "Does this assertion describe what the SUT produced, or just that a mock fired?"
  IF it only proves the mock fired:
    STOP — replace or supplement it with an assertion on the SUT's return value / rendered output / state
```

## Anti-Pattern 2: Test-Only Methods on Production Classes

**BAD** — `ResetForTests()` ships in the production class just so tests can rewind state:

```csharp
public class SessionCache
{
    public void ResetForTests() => _entries.Clear();   // dead weight in production, a foot-gun if ever called live
}
```

**GOOD** — the test owns its own teardown; the production class never learns tests exist:

```csharp
// test helper, not on SessionCache
private static SessionCache CreateSut() => new SessionCache();
// each test builds a fresh instance instead of resetting a shared one
```

### Gate function

```
BEFORE adding any method to a production class:
  Ask: "Is this only ever called from a test?"
  IF yes:
    STOP — put it in a test helper/fixture instead; do not add it to the class
```

## Anti-Pattern 3: Mocking Without Understanding the Real Dependency

**BAD** — mocking a method that has a side effect the test silently depends on:

```ts
it('detects a duplicate server registration', async () => {
  vi.mock('./toolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined), // real impl also PERSISTS the config
  }));

  await addServer(config);
  await addServer(config); // expected to throw "already registered" — but the config was never written, so it won't
});
```

**GOOD** — mock only the slow/external part; keep the side effect the test's assertion relies on:

```ts
it('detects a duplicate server registration', async () => {
  vi.mock('./remoteToolDiscovery'); // just the slow network call, not the config write

  await addServer(config);
  await expect(addServer(config)).rejects.toThrow('already registered');
});
```

### Gate function

```
BEFORE mocking any dependency:
  1. Ask: "What does the real implementation do — including side effects?"
  2. Ask: "Does this test's assertion depend on any of those side effects?"
  IF unsure or it does depend on them:
    Run against the real implementation first, observe what happens, THEN mock only the
    slow/external boundary — never the method the assertion actually needs.
  Red flag: "I'll mock this to be safe" without having read the real implementation.
```

## Anti-Pattern 4: Incomplete Mocks

**BAD** — mock only carries the fields the current test happens to read:

```ts
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  // real API also returns `metadata.requestId` — downstream code reads it and blows up in production
};
```

**GOOD** — mirror the complete real response shape, not just what today's assertion touches:

```ts
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1719260400 }, // every field the real API returns
};
```

**The rule:** mock the COMPLETE data structure as it exists in reality — check the real API/DTO/schema
before writing the mock, not just the fields your test currently consumes.

### Gate function

```
BEFORE hand-writing a mock response/entity/DTO:
  Check: "What does the REAL dependency return, in full?" (docs, a live sample, the actual class/schema)
  Include every field downstream code might read — not only the ones this test's assertion uses
  IF uncertain which fields exist:
    Capture one real response/object and base the mock on it — don't guess
```

## Anti-Pattern 5: Tests Written as an Afterthought

**BAD:**

```
Implementation complete. No tests written. "Ready for review."
```

**GOOD** — tests land with the implementation, not after it:

```
1. Write the test for the next behavior (it should fail for the right reason)
2. Implement just enough to make it pass
3. Refactor
4. Only then move to the next behavior / claim the slice complete
```

### Gate function

```
BEFORE marking any implementation task complete:
  Ask: "Do tests exist for every behavior/AC this change introduces?"
  IF no:
    STOP — write them now; "tests later" reliably becomes "tests never"
```

## Red Flags

- Mock setup is **>50% of the test** — the test is more about wiring than behavior.
- An assertion checks that a mock/stub/spy was called, with no assertion on the SUT's output or state.
- A method exists on a production class and is only ever referenced from test files.
- Mocking "just to be safe" without having read what the real dependency does.
- A hand-built mock response/entity that was never compared against the real shape.
- "Implementation done, tests pending" appears in a status update.

## Quick Reference

| Anti-pattern | Fix |
|---|---|
| Assert on mock call instead of behavior | Assert on the SUT's return value/output/state |
| Test-only methods on production classes | Move to a test helper/fixture |
| Mock without understanding side effects | Read the real dependency first; mock the minimal boundary |
| Incomplete mocks | Mirror the complete real data structure |
| Tests as afterthought | Write the test before/alongside the code, not after |

## The Bottom Line

Mocks isolate the unit under test — they are never the thing under test. If an assertion would still pass
with the production code deleted and only the mock left standing, it is testing the mock, not the code.
