# Definition Criteria

The verification contract for the whole workflow. Everything downstream — the generated unit tests, the implementer's done-signal, and the Phase 5 guardrail check — reads from these criteria. Locking them is the primary job of the Phase 0 interview.

There are **two levels**, and both must be *verifiable by construction*. "Make it work" / "handle errors properly" are not criteria — they are gaps to resolve in the interview.

## Level 1 — Acceptance Criteria (plan-level)

What the **whole feature** must satisfy, confirmed by the user in Phase 0. Each AC is a testable statement of observable behavior.

- ✅ "AC-1: Exporting an empty report yields a CSV with only the header row."
- ✅ "AC-2: A non-admin user calling the export endpoint receives 403."
- ❌ "AC: Export works." (not observable / not testable)

Every AC must map to at least one task.

## Level 2 — Definition of Done (per task)

Concrete, **mechanically checkable** conditions for a single task to count as complete. Each item is something a machine (or a quick deterministic check) can confirm — not a judgement call.

Good DoD items:
- A **named unit test passes**: ``GetUsers_EmptyDb_ReturnsEmptyList`` is green.
- A **build/lint** result: `dotnet build` succeeds with no new warnings.
- A **concrete behavior**: `GET /api/users` returns `200` with a `UserDto[]` body.
- A **value assertion**: `CsvExporter.Export([])` returns a string equal to `"Id,Name\n"`.

Weak DoD items (reject / sharpen in interview):
- "Endpoint is implemented correctly" → *correct how? what input → what output?*
- "Good error handling" → *which errors? what response/behavior for each?*

### The DoD drives three things
1. **Phase 3 tests** — the qa-engineer turns each testable DoD item into a failing unit test. The test *is* the executable form of the DoD.
2. **Phase 4 done-signal** — an implementer's task is not complete until its DoD is satisfied (its tests are green).
3. **Phase 5 guardrail** — the main agent verifies each task against its DoD before marking it complete; unmet items drive the rework loop.

## Untestable tasks

Some tasks have no meaningful unit test — config changes, infra wiring, pure UI/style tweaks. For these:
- Mark the task **`Unit-testable: no`** in the plan.
- Its Definition of Done falls back to a **review-only gate**: the build still succeeds and `code-review-lite` returns no must-fix findings.
- Optionally add a smoke/behavioral check if one is cheap (e.g. "page renders without console errors").

Do not invent low-value tests just to satisfy the TDD step — flag the task honestly and let the review gate cover it.

## Interview tie-in

A task is only allowed into the plan once it has a Definition of Done. If, during Phase 0, the user cannot say how a piece would be verified, that is the signal to ask one more targeted question — *not* to write a vague task and hope. The criteria are cheaper to get right before any code or test exists.
