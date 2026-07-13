# Plan Template

Write new plans to flat `.plans/{feature-name}.md`; keep existing input plan path. Main agent owns
all status edits. Task headings must be unique.

```markdown
# Plan: {Feature Name}

## Context
{Problem, prior state, and decisions. Include exact lines below.}
Unit tests: {selected|skipped}
Unit tests source: {user|auto-assessment}
Unit tests reason: {specific instruction or repository evidence}
Code review: {selected|skipped}
Code review source: {user|auto-assessment}
Code review reason: {specific instruction or repository evidence}
Depth: {TDD|simplify}

## Goal
{Implementation outcome understandable without original conversation.}

## Global Constraints
{Copy project rules, compatibility constraints, protected paths, and non-goals exactly.}

## Acceptance Criteria
- [ ] AC-1: {observable result}
- [ ] AC-2: {observable result}

## Tasks

### Task 1: {Descriptive Name}
- Status: pending
- Depends on: none
- Files: `path/to/file1`, `path/to/file2`
- Description: {specific implementation behavior}
- Interfaces (when another task consumes this boundary):
  - Produces: {symbol, parameters, return type}
- Done when: {mechanical build/test/behavior evidence}
- ACs: AC-1

### Task 2: {Descriptive Name}
- Status: pending
- Depends on: Task 1
- Files: `path/to/other`
- Description: {specific implementation behavior}
- Interfaces:
  - Consumes: {exact symbol/type from Task 1}
- Done when: {mechanical evidence}
- ACs: AC-2

## Agent Assignment
| Wave | Task(s) | Agent | Verified by (main agent) |
|---|---|---|---|
| 1 | Task 1 | code-implementer | diff + Done-when evidence |
| 2 | Task 2 | code-implementer | diff + scoped verification |
| pre-1 | failing tests (TDD only) | qa-engineer | tests bind to scaffold and fail for missing behavior |

## Verification
- Build: `{exact command}`
- Existing tests: `{exact command}`
- New unit tests (selected only): `{exact command}`
- Code review (selected only): `code-review-lite` over changed files
- Manual/static checks: {specific checks}
```

When unit tests are selected, replace each `Done when` line with Definition-of-Done checklist from
`definition-criteria.md`; include `qa-engineer` row. When skipped, omit TDD/new-test row. When code
review is skipped, omit review invocation while retaining build and existing-test commands.

## Task status

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `scaffolded` | TDD signature/stub only |
| `in-progress` | Implementer active |
| `complete` | Main agent verified Done-when |
| `blocked` | Retry exhausted |

## Rules

1. No two tasks share a file; merge overlapping work.
2. Every task has `Depends on`, files, concrete description, mechanical Done-when, and AC mapping.
3. Every AC maps to at least one task.
4. Agent Assignment waves follow dependencies.
5. No placeholders such as TBD, undecided markers, vague error handling, or cross-task shorthand.
6. Exact quality fields are mandatory; reasons cite evidence. Depth matches unit-test decision.
7. Existing legacy `requested/not requested` flags map per `quality-assessment.md`, then normalize
   when plan is next written.
