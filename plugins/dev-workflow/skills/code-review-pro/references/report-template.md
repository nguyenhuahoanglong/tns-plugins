---
name: report-template
description: Template for the final synthesized code review report — merges findings from 5 deep-dive agents plus build validator into a unified report
---

# Report Template

For early-exit variants (gate REJECT, build FAIL), see `short-reports.md`.

Follow-up reviews (`followup-review.md`) regenerate this SAME full report — resolved findings are dropped, remaining findings keep their `[mf:slug]` tags unchanged, new findings get new slugs. `code-review-publish` diffs slug sets across iterations, so a partial/appended report would break it.

## Output Location

Write the final report to: `.CodeReview/{BranchName}.md`

If the `.CodeReview/` directory doesn't exist, create it. Use the current branch name (sanitized for filesystem) as the filename.

## ADO Autolink Safety

ADO renders raw `#123` as a work-item link. Emit raw `#number` only when the text intentionally links a work item, e.g. `Work Item #1795` or `Parent #1696`. Escape all other number references with a backslash: `PR \#1489`, `AC \#4`, `Philosophy \#23`. After writing the report, run:

```bash
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{BranchName}.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{BranchName}.md"
```

## Final Report Template

```markdown
# Code Review: {Feature/PR Title}

**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Target**: {target-branch}
**Reviewed Commit**: {HEAD sha at review time}
**Iteration**: {n — 1 for the initial full review; incremented by follow-up reviews}
**Files Reviewed**: {count}
**Agents**: {list of agents that ran, e.g., "Build, Standard Reviewer, Philosophy, Security, Performance, Requirement" — or "Build, Delta Reviewer" on follow-up}

---

## Build Status

> Omit entirely if Build Validator was skipped.

| Project | Type | Status | Errors | Warnings |
|---------|------|--------|--------|----------|
| {name} | .NET 8 | PASS / FAIL | {n} | {n} |

{Errors and warnings detail if any}

---

## Requirement Fulfillment

**Work Item**: #{id} - {title} | **Parent**: #{parent-id} - {parent-title}

| # | Acceptance Criterion | Status | Evidence |
|---|---------------------|--------|----------|
| 1 | {criterion text} | Addressed / Partial / Missing | {file:line or explanation} |

**Scope Assessment**: {On-scope / Over-scoped / Under-scoped} — {brief}

> If Requirement Validator was skipped, replace this section with: "Requirement validation skipped — no linked work item."

---

## Summary

| Dimension | Agent | Status | Notes |
|-----------|-------|--------|-------|
| Approach | Orchestrator inline (opus) | Pass / Pass-with-concerns | {brief} |
| Build | Build Validator (haiku) | Pass / Fail / Skipped | {brief} |
| Requirements (P1) | Requirement Validator (sonnet) | Pass / Warn / Skipped | {brief} |
| Performance (P2) | Performance Reviewer (sonnet) | Pass / Warn | {brief} |
| Security (P3) | Security Reviewer (sonnet) | Pass / Warn | {brief} |
| Philosophy (P4) | Philosophy Reviewer (sonnet) | Pass / Warn | {brief} |
| Standards (P5) | Standard Reviewer (sonnet) | Pass / Warn | {brief} |

### Findings Count

| Critical | High | Medium | Low | Total |
|----------|------|--------|-----|-------|
| {n} | {n} | {n} | {n} | {n} |

### Must Fix Before Merge

> Shortlist of findings meeting `analysis-framework.md` §Action Classification Must Fix criteria: breaks behavior, runtime error, fails design requirement, or critical security/performance. Capped ~10, sorted by severity then tier (P1→P5). If empty, write "None — all findings are Should Fix or Consider."

> **Slug requirement** — every Must Fix bullet MUST carry a stable `[mf:{slug}]` tag (kebab-case, ≤24 chars, derived from the issue noun phrase: `auth-broaden`, `nre-risk`, `raw-statuscode`, `finalize-reload`). The slug is what the `code-review-publish` skill uses to diff iterations — do not change it across re-runs unless the underlying issue is genuinely different. Slug stability > naming polish.

- **[CRITICAL] [{Agent}] [mf:{slug}]** {one-line issue} — `{file}:{line}`
- **[HIGH] [{Agent}] [mf:{slug}]** {one-line issue} — `{file}:{line}`

---

## Principles Check

> From the Philosophy Reviewer.

| Principle | Status |
|-----------|--------|
| Single Responsibility | Pass / Warn |
| Open/Closed | Pass / Warn / N/A |
| Liskov Substitution | Pass / Warn / N/A |
| Interface Segregation | Pass / Warn / N/A |
| Dependency Inversion | Pass / Warn |
| DRY | Pass / Warn |
| KISS | Pass / Warn |
| YAGNI | Pass / Warn |
| Separation of Concerns | Pass / Warn |
| Fail Fast | Pass / Warn |

---

## Files Changed

| # | File | Build | Standard | Philosophy | Security | Performance | Requirement |
|---|------|-------|------------|------------|----------|-------------|-------------|
| 1 | `{path}` | Clean | 1 issue | Clean | 1 issue | Clean | Addressed |

---

## Detailed Findings

One subsection per file that has findings. Files with zero findings are omitted here (they still appear in the Files Changed table as "Clean"). Within each file, list findings by severity (Critical → Low), then by tier (P1 Requirement → P5 Convention). Each finding carries inline `[SEVERITY]` and `[Agent]` tags. **Do not create severity section headers (`### CRITICAL`, `### HIGH`, etc.) — severity is a tag, not a heading.**

### `{file-path}`

**Change**: {type} | +{added}/-{removed}

1. **[CRITICAL] [{Agent}]** {Finding title}
   - **Issue**: {Description}
   - **Impact**: {Why this matters — optional for P4-P5}
   - **Suggestion**: {How to fix}

2. **[HIGH] [{Security, Performance}]** {Finding title} — {one-line with inline suggestion}

### `{next-file-path}`

**Change**: {type} | +{added}/-{removed}

1. **[MEDIUM] [{Agent}]** {Finding title} — {one-line}

---

## Reviewer Notes

{Additional observations, cross-cutting concerns, or questions for the author}
```

## Synthesis Guidelines

Apply priority-tier effort scaling from `analysis-framework.md` (P1 Requirement → P5 Convention) — most rigor on P1, light pass on P5.

1. **Build findings** — errors → CRITICAL, warnings → MEDIUM
2. **Deduplication** — same `file:line` from multiple agents → one entry, multi-tag (e.g., `[Security, Performance]`), highest severity wins
3. **Files Changed table** — summarize per-agent findings per file (count or "Clean")
4. **Must Fix shortlist** — select findings meeting `analysis-framework.md` §Action Classification Must Fix criteria (breaks behavior / runtime error / fails requirement / critical security-or-performance), cap ~10, sort by severity then tier
5. **Agent attribution** — every finding tagged with source agent
6. **Skipped agents** — mark "Skipped" in Summary; omit empty sections
7. **Approach pre-findings** — concerns from a PASS-with-concerns gate → P1 findings tagged `[Approach]`
8. **ADO autolink guard** — run `ado_autolink_guard.py fix` then `check` before declaring the report complete
