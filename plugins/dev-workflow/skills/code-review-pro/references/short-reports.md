---
name: short-reports
description: "Two short-report variants for early-exit code review paths — Reject (Phase 2a fail) and Build Fail (Phase 2b fail)"
---

# Short Reports

Used when the orchestrator stops before deep dive because a gate failed.

All variants write to `.CodeReview/{BranchName}.md` (same path as the full report; the file content differs).

## Reject Report — Phase 2a fail

Used when the Approach Gate fires REJECT. See `approach-gate.md` for the criteria.

```markdown
# Code Review (Rejected at Approach Gate): {Feature/PR Title}

**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Gate**: Approach Assessment — REJECT
**Confidence**: high | medium | low

## Reason

{One sentence — what's structurally wrong}

## Evidence

- `{file}:{line}` — {what's wrong}
- {standards file}: "{rule text}"
- AC #{n}: "{criterion text}"

## Recommendation

{Concrete next step — typically: refactor the approach, then re-run review}

> Deep dive skipped. Re-run `/code-review-pro` once the approach is corrected, or reply with context to dispute this gate decision.
```

## Build Fail Report — Phase 2b fail

Used when the Build Validator returns `Gate Result: FAIL`. Captures errors only (warnings move to the full report on a successful re-run).

```markdown
# Code Review (Build Failed): {Feature/PR Title}

**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Gate**: Build Validation — FAIL

## Build Status

| Project | Type | Status | Errors |
|---------|------|--------|--------|
| {name} | .NET 8 | FAIL | {n} |
| {name} | React | PASS | 0 |

## Errors

### `{ProjectName}`

1. **`{file}:{line},{col}`** — {error-code}: {message}

## Recommendation

Fix the build errors and re-run `/code-review-pro`. Deep dive skipped to avoid reviewing broken code.
```

## Notes for the Orchestrator

- Short reports are written by the orchestrator directly — no agent involvement beyond Phase 2 outputs
- Phase 5 cleanup (worktree removal) still runs after writing any short report
- If both gates fail simultaneously, the Reject Report takes precedence (architectural fail is more fundamental than build fail)
