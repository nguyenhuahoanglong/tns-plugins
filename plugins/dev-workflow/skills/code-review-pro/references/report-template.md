---
name: report-template
description: Exact v2 report fields and profile-aware synthesized code review layout
---

# Report Template

Write `.CodeReview/{safe-branch}.md`. Follow-ups regenerate the full report and preserve unchanged `[mf:slug]` values.

## Required Header

Use these field names exactly and once:

```markdown
# Code Review: {title}

**Skill**: code-review-pro v2.2.0
**Review Profile**: Docs-only | Tiny | Pro
**Main Runtime**: {resolved model} / {resolved effort}
**Agents Triggered**: {pipe-separated trigger/actor records, or None}
**Agents Skipped**: {pipe-separated actor/reason records, or None}
**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Target**: {target}
**Reviewed Commit**: {sha}
**PR-Only**: true | false
**Merge Preview**: server-merge | local-merge | source-head | n/a
**Iteration**: {integer}
**Files Reviewed**: {count}
```

`Agents Triggered` and `Agents Skipped` must match the announcement and v2 sidecar. Resolve model and effort from explicit launch metadata first, then current session metadata. Use `not exposed` only for an individually unavailable field; never discard a known value. The sidecar `runtime.main` must exactly match this header.

Join records with ` | ` and do not use pipes inside one record. Use exact actor forms:

- `Main(docs-only inline)` or `Main(Tiny all-lens)`
- `Branch Work Item Gate(haiku / default; branch work item convention)`
- `Build Validator[{repo}](haiku / default; {reason})`
- `Requirement Validator(opus / default; {work-item|regression-only})`
- `{Specialist} Reviewer(sonnet / default; {trigger})`

Skipped actors use `{Actor}({reason})`. Branch Work Item Gate is triggered for PR/branch scope and skipped for staged, working, or files scope. Docs-only triggers Main plus optional Branch Work Item Gate; Tiny triggers Main plus Branch Work Item Gate and Build per repo.

## Classifier

```markdown
## Review Classification

- **Files Changed**: {n}
- **Changed Lines**: {added + removed}
- **Docs Only**: true | false
- **Risk Triggers**: {labels joined by ` | `, or None}
- **Risk Evidence**: {label=one-sentence evidence joined by ` | `, or None}
- **Specialist Triggers**: {Reviewer=label joined by ` | `, or None}
```

## Validation

```markdown
## Branch Work Item Gate

- **Status**: PASS | WARN | FAIL | SKIPPED
- **Branch**: {source branch or None}
- **Prefix**: US | BUG | ISSUE | None
- **Work Item ID**: {id or None}
- **Expected Type**: User Story | Bug | Issue | None
- **Actual Type**: {ADO System.WorkItemType or None}
- **Title**: {ADO title or None}
- **State**: {ADO state or None}
- **Source**: pr | branch | staged | working | files
- **Reason**: {one-line result or failure reason}

## Build Status

| Repo / Project | Child Read | Build | Errors | Warnings |
|---|---|---|---|---|
| {name} | PASS | PASS / FAIL / NOT RUN / NOT RUN (environment) / JS-SKIPPED | {n} | {n} |

A `JS-SKIPPED` build row means `prepare_worktree_deps.py` could not make that project's dependencies usable. State the reason exactly: `deps changed` | `no lockfile` | `install failed`. A JS-skipped row is not a build failure but must be surfaced, never silently passed, and the Build Validator is never dispatched with that project's JS build command.

A build row for a project reported with `jsDepsStrategy` strategy `install` means `prepare_worktree_deps.py` performed a fresh frozen, lockfile-gated install for that project before the build ran — a PASS there reflects freshly installed dependencies, not a stale/reused `node_modules`.

## Requirement Validation

**Mode**: work-item | regression-only | inline | not-applicable
**Direct Work Item**: Work Item #{id} - {title} | None
**Parent Context**: Work Item #{id} - {title} | None

| Direct AC / Preserved Behavior | Status | Evidence |
|---|---|---|
| {criterion or behavior} | Addressed / Partial / Missing / Preserved / Regressed | `{file}:{line}` plus path |

### Scope Drift

| Change (`file:line`) | Justifying requirement? | Risk |
|---|---|---|
| `{file}:{line}` | No | HIGH (shared/public/API/schema/state) / MEDIUM (isolated) |

- **Scope Drift**: None
```

For Docs-only, include a build row with `SKIPPED` / `NOT RUN`, and use requirement mode `not-applicable` unless documentation has explicit requirements. For Tiny use `inline`. Parent context never appears as a direct AC row. The Pro profile always includes the Scope Drift block (the `- **Scope Drift**: None` sentinel when clean); list only unjustified changes. Scope-drift findings are HIGH/MEDIUM advisories ("justify or revert") and never block merge.

## Summary and Findings

```markdown
## Summary

| Lens | Owner | Status | Evidence summary |
|---|---|---|---|
| Branch work item | Branch Work Item Gate / Skipped | Pass / Warn / Fail / Skipped | {brief} |
| Build | Build Validator / Skipped | Pass / Fail / Skipped | {brief} |
| Requirement and regression | Main / Requirement Validator | Pass / Warn / Fail | {brief} |
| Security | Main / Security Reviewer / Skipped | Pass / Warn / Skipped | {brief} |
| Performance | Main / Performance Reviewer / Skipped | Pass / Warn / Skipped | {brief} |
| Design | Main / Philosophy Reviewer / Skipped | Pass / Warn / Skipped | {brief} |
| Standards | Main / Standard Reviewer / Skipped | Pass / Warn / Skipped | {brief} |

### Must Fix Before Merge

- **[CRITICAL|HIGH] [{Owner}] [mf:{stable-slug}]** {issue} - `{file}:{line}`

Branch Work Item Gate `FAIL` is a CRITICAL Must Fix before merge. Include completed build results, skip later validators/specialists, and state that review stopped after first gates. Branch Work Item Gate `WARN` is advisory, records branch convention/type-prefix mismatch, and does not stop review.

## Files Changed

| File | Build | Requirement | Security | Performance | Design | Standards |
|---|---|---|---|---|---|---|
| `{path}` | Clean | Preserved | Clean | Clean | Clean | Clean |

## Detailed Findings

### `{file-path}`

1. **[SEVERITY] [{Owner}]** `{line}` - {title}
   - **Evidence**: {base/new behavior, caller/consumer/event/state/test path}
   - **Impact**: {concrete effect}
   - **Suggestion**: {actionable fix}
   - **Confidence**: High | Medium | Low (carried from the reporting agent; Medium/Low findings are synthesized on this evidence without re-verification)

## Reviewer Notes

{uncertainty, limits, or follow-up}
```

Group details by file, then severity. No severity headings. Deduplicate same issue/path, keep highest severity, and combine owner tags.

## ADO Safety

Raw `#number` is only for intentional work-item links. Escape PR, AC, and finding numbers. Run `ado_autolink_guard.py fix` then `check`.
