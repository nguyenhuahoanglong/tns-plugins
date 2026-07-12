# Plan Template (implement-plan)

Use this when writing `.plans/{feature-name}.md` in Phase 1.4. The shape follows the **Claude Code
native plan pattern**: `Context → Goal → Global Constraints → Acceptance Criteria → Tasks →
Verification`.

**Filename:** flat `.plans/{feature-name}.md` (e.g. `csv-export.md`). Keep an existing plan file's
name if the input was already a plan.

The plan is the single source of truth. **The main agent owns all status writes** — sub-agents read
the plan but do not edit it (they report status back). Keep task headings unique.

---

```markdown
# Plan: {Feature Name}

## Context
{Why this change — the problem/need, prior state, and decisions locked with the user.
Include these exact lines:
Unit tests: {requested or not requested}
Code review: {requested or not requested}
Depth: TDD when unit tests are requested; otherwise simplify.}

## Goal
{1-2 paragraphs — enough for an implementer to understand what to build without the original source.}

## Global Constraints
{Project-wide requirements copied VERBATIM from the requirements/spec — naming rules, framework/
library versions, protected paths, non-goals. One line each, exact values. This block is handed
verbatim to every implementer and reviewer dispatch; every task's requirements implicitly include it.}

## Acceptance Criteria
- [ ] AC-1: {concrete, observable, testable}
- [ ] AC-2: {concrete, observable, testable}

## Tasks

### Task 1: {Descriptive Name}
- Status: pending
- Depends on: none
- Files: `path/to/file1`, `path/to/file2`
- Description: {what to implement — specific enough to act on}
- Interfaces (optional — required whenever another task shares this task's type/function boundary):
  - Produces: {exact symbols this task creates that other tasks consume — name, params, return type}
- Done when: {mechanically checkable — e.g. "dotnet build passes; GET /api/users returns 200 with UserDto[]"}
- ACs: AC-1

### Task 2: {Descriptive Name}
- Status: pending
- Depends on: Task 1
- Files: `path/to/other`
- Description: {…}
- Interfaces:
  - Consumes: {exact symbols/types from other tasks this task calls — name, params, return type}
- Done when: {…}
- ACs: AC-2

## Agent Assignment
| Wave | Task(s) | Agent | Verified by (main agent) |
|---|---|---|---|
| 1 | Task 1, Task 2 (parallel) | code-implementer | diff + Done-when evidence |
| 2 | Task 3 (after Task 1) | code-implementer | scoped tests green |
| — | failing tests (only when unit tests requested) | qa-engineer | tests exist, bind to scaffold, red |

## Verification
{Narrative: the build/test commands to run and the manual confirmation steps that prove the ACs.
E.g. "Run `npm test`; manually export an empty report and confirm a header-only CSV."}
```

When `Unit tests: requested`, expand each task's single `Done when:` line into a `Definition of Done:` checklist
of named, mechanically checkable items (see `definition-criteria.md`) — the qa-engineer turns each
into a failing test.

---

## Field Reference

### Task Status
| Status | Meaning |
|---|---|
| `pending` | Not started |
| `scaffolded` | (TDD only) stub/signature written, no logic yet |
| `in-progress` | Implementer working |
| `complete` | Done-when met; main agent recorded it |
| `blocked` | Reported blocker, retry exhausted |

## Rules
1. **Unique task headings** — `### Task N: Name` must be unique.
2. **File isolation** — no two tasks share a file; merge if they must overlap.
3. **Every task has a "Done when"** — mechanically checkable. No criterion ⇒ the task isn't ready.
4. **Every AC maps to ≥1 task.**
5. **`Depends on` drives dispatch order** — independent tasks parallelize; dependents wait.
6. **Main agent writes status** — sub-agents report; the main agent edits the plan. No parallel
   writes to the plan file.
7. **Agent Assignment waves derive from `Depends on`** — one wave = one independent set of tasks;
   Phase 2 dispatches exactly what this table says; the main agent verifies each row's output
   (diff + Done-when evidence) before advancing to the next wave.
8. **Preference flags are mandatory** — do not write the plan until both are resolved; unit tests
   control TDD/new test creation, while code review independently controls review/rework/verdict.
9. **No placeholders** — never write "TBD", "TODO: decide later", "add appropriate error handling",
   or "similar to Task N" (repeat the detail instead — tasks may execute out of order or in
   isolation); never reference a type/function that no task defines.
