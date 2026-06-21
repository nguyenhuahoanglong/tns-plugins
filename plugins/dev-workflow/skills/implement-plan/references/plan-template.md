# Plan Template (implement-plan)

Use this when writing `{plan-folder}/{feature-name}-plan.md` in Phase 1.3.

**Filename**: `{feature-name}-plan.md` (e.g., `csv-export-plan.md`) so the plan self-identifies alongside other artifacts. Keep an existing plan file's name if the input was already a plan.

The plan is the single source of truth. **The main agent owns all status writes** — sub-agents read the plan but do not edit it (they report status back). Keep task headings unique.

---

```markdown
# Plan: {Feature Name}

## Meta
- **Status**: planning | implementing | complete | blocked
- **Created**: {YYYY-MM-DD}
- **Source**: {inline | file path | folder | work item #ID}
- **Plan folder**: {absolute path}

## Goal
{1-2 paragraphs — enough for an implementer to understand what to build without the original source}

## Acceptance Criteria
- [ ] AC-1: {concrete, observable, testable}
- [ ] AC-2: {concrete, observable, testable}

## Tasks

### Task 1: {Descriptive Name}
- **Status**: pending
- **Depends on**: none
- **Files**: `path/to/file1.cs`, `path/to/file1.tests.cs`
- **Contracts**: {signatures/interfaces this task exposes — what the scaffold will stub}
  - `IUserService.GetUsersAsync(): Task<IReadOnlyList<UserDto>>`
- **Unit-testable**: yes
- **Description**: {what to implement — specific enough to act on}
- **Definition of Done**:
  - [ ] Unit test `GetUsers_ReturnsActiveUsers` passes
  - [ ] Unit test `GetUsers_EmptyDb_ReturnsEmptyList` passes
  - [ ] `dotnet build` succeeds, no new warnings
- **ACs covered**: AC-1

### Task 2: {Descriptive Name}
- **Status**: pending
- **Depends on**: Task 1
- **Files**: `path/to/other.cs`
- **Contracts**: {…}
- **Unit-testable**: no   # config/infra/UI — review-only gate
- **Description**: {…}
- **Definition of Done**:
  - [ ] `dotnet build` succeeds
  - [ ] code-review-lite returns no must-fix findings
- **ACs covered**: AC-2

## Verification
- **Build**: pending | passing | failing
- **Tests**: pending | passing | failing
- **Review**: pending | pass | must-fix

## Iteration Log
- {YYYY-MM-DD HH:MM}: Plan created
```

---

## Field Reference

### Meta Status
| Status | Meaning |
|---|---|
| `planning` | Phase 0–1 — interviewing / writing the plan |
| `implementing` | Phases 2–5 active |
| `complete` | All tasks done, DoD met, build/tests/review pass |
| `blocked` | Loop exhausted, needs the user |

### Task Status
| Status | Meaning |
|---|---|
| `pending` | Not started |
| `scaffolded` | Stub/signature written (Phase 2), no logic yet |
| `in-progress` | Implementer working |
| `complete` | DoD met, tests green, main agent recorded it |
| `blocked` | Reported blocker, retry exhausted |

## Rules
1. **Unique task headings** — `### Task N: Name` must be unique.
2. **File isolation** — no two tasks share a file; merge if they must overlap.
3. **Every task has a Definition of Done** — mechanically checkable (see `definition-criteria.md`). No DoD ⇒ the task isn't ready to plan.
4. **Every AC maps to ≥1 task.**
5. **Contracts feed the scaffold** — Phase 2 stubs exactly the signatures listed under Contracts.
6. **`Depends on` drives dispatch order** — independent tasks parallelize; dependents wait.
7. **Main agent writes status** — sub-agents report; the main agent edits the plan. No parallel writes to plan.md.
