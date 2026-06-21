# Legacy Code: Characterization Tests

**Goal:** when you must change code that has no tests, first build a safety net that captures what the code **does today** — so a future change that alters behavior fails loudly. This is the primary defense for *"future changes won't break the current logic."*

A characterization test does not assert *correct* behavior — it asserts *current* behavior, even if that behavior is arguably a bug. You are pinning a baseline. Fixing behavior is a separate, later commit (and the failing characterization test is your proof the behavior changed).

## When to use this path

- Code is about to be refactored, extended, or have a bug fixed, **and** has no/low test coverage.
- You don't fully understand all the code's behavior (that's normal for legacy — the tests document it as you go).

If the code already has good tests, use the normal behavior/spec strategy instead.

## The loop (Feathers' method)

1. **Find a seam.** A seam is a place you can sense or substitute behavior without editing the code in place. If there is none, create the smallest one possible (extract an interface, add a constructor parameter, wrap a static call). Make the *smallest* structural change that lets you instantiate and invoke the unit. See per-stack notes below.
2. **Write a test that calls the code** with representative inputs and asserts something you *expect to be wrong* (e.g. `result.Should().Be("PLACEHOLDER")`).
3. **Run it.** The failure message reveals the actual output.
4. **Paste the actual output into the assertion.** The test now pins current behavior.
5. **Repeat** across branches/inputs until the behavior you're about to touch is covered.
6. **Now refactor/fix** with confidence — green means behavior preserved; red on a pin you didn't intend to change means you broke something.

## Approval / snapshot testing (faster for complex output)

When the output is large or structured (objects, generated text, rendered DOM), use approval testing instead of hand-writing asserts — the tool records the first run as the "approved" baseline file, then diffs future runs:

- **C#:** `Verify` (VerifyXunit) or `ApprovalTests` — first run writes `*.received.*`; you promote it to `*.verified.*`.
- **React/TS:** Vitest/Jest `toMatchSnapshot()` — but keep snapshots **small and intentional** (one component, key props), never whole pages, or every UI tweak breaks unrelated tests.
- **PCF:** snapshot the rendered grid fragment for the states you're about to change.

Commit the approved baseline files. A diff in review = a behavior change to scrutinize.

## Creating seams safely

The risk in legacy code is that *enabling* testing changes behavior. Keep seam-creation edits behavior-preserving and minimal:

- **Extract interface + inject** the hard dependency (DB, service, clock) so a test can substitute a fake. (C#: extract `IFoo`, take it via constructor. TS: accept a dependency arg/prop.)
- **Wrap statics/singletons** behind an injectable wrapper rather than calling them directly.
- **Don't reformat or "clean up"** while adding seams — every line changed before the net exists is unprotected. Pin first, beautify later.

## Labeling

Mark characterization tests so reviewers don't mistake a pinned quirk for an intended spec:

```csharp
// CHARACTERIZATION: pins CURRENT behavior of legacy rounding; not verified as correct.
[Fact]
public void Characterize_TaxRounding_For_OddCents() { ... }
```

In the requirement→test mapping (see `best-practices.md`), tag these as `legacy/pin` so the QA report distinguishes "captures current behavior" from "verifies a requirement".

## Scope discipline

Pin only the behavior in the blast radius of your change — you do not need 100% characterization of an entire legacy module. Cover what you're about to touch and the paths that flow into it.
