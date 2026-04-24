---
name: report-template
description: Template for the lite code review report — merges build, critical, and quality findings into a unified file
---

# Report Template

## Output Location

Write the final report to: `.CodeReview/{BranchName}.lite.md`

If the `.CodeReview/` directory doesn't exist, create it. Use the current branch name (sanitized for filesystem) as the filename. **Always use the `.lite.md` suffix** — never write to `.CodeReview/{BranchName}.md` (that path is reserved for full reviews).

## Final Report Template

~~~markdown
# Code Review (Lite): {Feature/PR Title}

**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Target**: {target-branch}
**Files Reviewed**: {count}

---

## Build Status

| Project | Type | Status | Errors | Warnings |
|---------|------|--------|--------|----------|
| {name} | .NET 8 | PASS / FAIL | {n} | {n} |

{Errors and warnings detail if any — omit table if no projects detected}

---

## Files Changed

| # | File | Build | Security | Performance | Quality |
|---|------|-------|----------|-------------|---------|
| 1 | `{path}` | Clean | 1 issue | Clean | 2 issues |

> Quality column absorbs philosophy and convention findings.

---

## Must Fix Before Merge

> Severity-sorted shortlist of Critical and High findings. If empty, write "None."

- **[CRITICAL] [{Agent}]** {one-line issue} — `{file}:{line}`
- **[HIGH] [{Agent}]** {one-line issue} — `{file}:{line}`

---

## Detailed Findings

One subsection per file that has findings. Files with zero findings are omitted here (appear in Files Changed as "Clean"). Within each file, list by severity (Critical → Low). Each finding carries inline `[SEVERITY]` and `[Agent]` tags. **Do not create severity section headers — severity is a tag, not a heading.**

### `{file-path}`

**Change**: {type} | +{added}/-{removed}

1. **[CRITICAL] [Critical]** {Finding title}
   - **Issue**: {Description}
   - **Impact**: {Why this matters}
   - **Suggestion**: {How to fix}

2. **[HIGH] [Quality]** `{line}` — {Finding title} — {one-line with inline suggestion}

3. **[MEDIUM] [Quality]** `{line}` — {Finding title} — {one-line}

### `{next-file-path}`

**Change**: {type} | +{added}/-{removed}

1. **[LOW] [Critical]** `{line}` — {Finding title} — {short description}

---

## Reviewer Notes

{Cross-cutting observations, overall code health assessment, follow-up recommendations}
~~~

## Synthesis Guidelines

1. **Build findings** — errors -> CRITICAL, warnings -> MEDIUM
2. **Deduplication** — same `file:line` from both agents -> one entry, multi-tag (e.g., `[Critical, Quality]`), highest severity wins
3. **Files Changed table** — summarize per-agent findings per file (count or "Clean"); Quality column combines philosophy + convention findings from Quality Reviewer
4. **Must Fix shortlist** — Critical and High findings only, severity-sorted, capped ~10
5. **Agent attribution** — tag every finding: `[Critical]` for Critical Reviewer, `[Quality]` for Quality Reviewer, `[Build]` for Build Validator
6. **Skipped sections** — if no findings for a file, omit from Detailed Findings; show "Clean" in Files Changed
