# Definition Criteria

The verification contract for the workflow. The interview's main job (Phase 0) is to lock these so
every task is verifiable *by construction*. "Make it work" / "handle errors properly" are not
criteria — they are gaps to resolve before planning.

There are **two levels**.

## Level 1 — Acceptance Criteria (plan-level)

What the **whole feature** must satisfy, confirmed by the user in Phase 0. Each AC is a testable
statement of observable behavior, and maps to at least one task.

- ✅ "AC-1: Exporting an empty report yields a CSV with only the header row."
- ✅ "AC-2: A non-admin user calling the export endpoint receives 403."
- ❌ "AC: Export works." (not observable / not testable)

## Level 2 — "Done when" per task (default)

Every task carries a **"Done when"** line: a concrete, mechanically checkable condition for that task
to count as complete — something a quick deterministic check can confirm, not a judgement call.

Good "Done when" items:
- A **build/lint** result: `dotnet build` succeeds with no new warnings.
- A **concrete behavior**: `GET /api/users` returns `200` with a `UserDto[]` body.
- A **value assertion**: `CsvExporter.Export([])` returns `"Id,Name\n"`.
- A **named test passes** (when the task already has tests): `GetUsers_EmptyDb_ReturnsEmptyList` is green.

Weak items (sharpen in the interview):
- "Endpoint is implemented correctly" → *correct how? what input → what output?*
- "Good error handling" → *which errors? what response/behavior for each?*

## TDD depth — Definition of Done checklist

When **TDD depth** is chosen for a logic-heavy, unit-testable change, expand the task's single
"Done when" line into a **Definition of Done** checklist of named, testable items. In TDD depth this
checklist drives three things:
1. **Failing tests** — the qa-engineer turns each testable item into a red unit test (the test *is*
   the executable form of the item).
2. **Implementer done-signal** — a task is not complete until its scoped tests are green.
3. **Verification** — the main agent checks each task against its DoD before marking it complete.

Tasks with no meaningful unit test (config, infra, pure UI/style) get a **review-only gate** instead:
the build still succeeds and `code-review-lite` returns no must-fix findings. Don't invent low-value
tests to satisfy the TDD step — flag the task honestly and let the review gate cover it.

## Interview tie-in

A task is only allowed into the plan once it has a "Done when" (or, in TDD depth, a Definition of
Done). If, during Phase 0, the user cannot say how a piece would be verified, that is the signal to
ask one more targeted question — *not* to write a vague task and hope. Criteria are cheaper to get
right before any code or test exists.
