# Plan Template

Use this template when creating `{artifact-folder}/{feature-name}-plan.md` in Phase 2.

**Filename convention**: `{feature-name}-plan.md` (e.g., `user-analytics-plan.md`). The feature name in the filename makes the plan self-identifying alongside other artifacts (`{feature-name}-requirement.md`, `qa/`, `reviews/`). Legacy `plan.md` is read on input but not written for new plans.

---

```markdown
# Plan: {Feature Name}

## Meta
- **Status**: planning
- **Created**: {YYYY-MM-DD}
- **Requirement**: {source — work item ID, file path, or "inline"}
- **Iteration**: 1

## Requirement Summary

{1-3 paragraph summary from requirement.md — enough for any sub-agent to understand the feature without reading the full requirement}

## Acceptance Criteria

- [ ] AC-1: {concrete, testable criterion}
- [ ] AC-2: {concrete, testable criterion}
- [ ] AC-3: {concrete, testable criterion}

## Work Packages

### Wave 1

#### WP-1: {Descriptive Name}
- **Status**: pending
- **Files**: `path/to/file1.ts`, `path/to/file2.ts`
- **Description**: {What to implement — specific enough for a code-implementer agent}
- **AC**: AC-1, AC-2
- **Review**: pending

#### WP-2: {Descriptive Name}
- **Status**: pending
- **Files**: `path/to/other-file.ts`
- **Description**: {What to implement}
- **AC**: AC-3
- **Review**: pending

### Wave 2 (depends on: Wave 1)

#### WP-3: {Descriptive Name}
- **Status**: pending
- **Files**: `path/to/dependent-file.ts`
- **Description**: {What to implement — may reference output from Wave 1 WPs}
- **AC**: AC-1, AC-3
- **Dependencies**: WP-1, WP-2
- **Review**: pending

## QA Results
- **Status**: pending

## Iteration Log
- {YYYY-MM-DD HH:MM}: Plan created
```

---

## Field Reference

### Status values (Meta)
| Status | Meaning |
|--------|---------|
| `gathering` | Phase 1 — collecting requirements |
| `planning` | Phase 2 — creating plan |
| `implementing` | Phase 3 — code-implementer agents active |
| `reviewing` | Phase 4 — code-reviewer agents active |
| `verifying` | Phase 5 — qa-engineer agent active |
| `done` | Phase 6 — all AC met, feature complete |
| `blocked` | Max retries exhausted, needs user |

### WP Status values
| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `in-progress` | Agent currently working |
| `complete` | Implementation done |
| `needs-rework` | Review found must-fix issues |

### WP Review values
| Value | Meaning |
|-------|---------|
| `pending` | Not yet reviewed |
| `pass` | No must-fix findings |
| `must-fix` | Has findings requiring rework |

## Wave Rules

1. **File isolation**: No two WPs in the same wave may list overlapping files
2. **Self-contained**: Each WP description must be understandable without reading other WPs
3. **Dependency declaration**: Wave N+1 WPs must declare which Wave N WPs they depend on
4. **AC mapping**: Every AC must be addressed by at least one WP

## State Transitions

```
gathering → planning → implementing ⇄ reviewing → verifying → done
                           ↑               |            |
                           └── needs-rework ←── fail ───┘
                                                        └→ blocked (max retries)
```

Update `plan.md` status at every transition. Log each event with timestamp in the iteration log.
