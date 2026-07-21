---
name: report-template
description: Strict v3 report and sidecar layout for runtime, scope, tests, routing, semantic review, and findings
---

# Report Template

Write `.CodeReview/{safe-branch}.md` and `.CodeReview/.{safe-branch}.review-meta.json`. Follow-ups regenerate both and preserve unchanged `[mf:slug]` values.

## Header

Use these fields exactly once. `Main Runtime` is exactly `{runtimeAttestation.modelId} / {runtimeAttestation.effort}`; never use settings, self-report, or `not exposed`.

```markdown
# Code Review: {title}

**Skill**: code-review-pro v3.0.0
**Review Profile**: No-production-code | Tiny | Pro
**Main Runtime**: {modelId} / {effort}
**Agents Triggered**: {pipe-separated exact actor records, or None}
**Agents Skipped**: {pipe-separated exact actor/reason records, or None}
**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Target**: {target}
**Reviewed Commit**: {sha}
**PR-Only**: true | false
**Merge Preview**: server-merge | local-merge | source-head
**Iteration**: {integer}
**Files Reviewed**: {production file count}
```

Join actor records with ` | ` and never put a pipe inside one record. Use:

- `Main(Tiny all-lens)`
- `Branch Work Item Gate(haiku / default; branch work item convention)`
- `Build Validator[{repo}](haiku / default; code build)`
- `Requirement Validator(opus / default; {work-item|regression-only})`
- `{Specialist} Reviewer(sonnet / default; {trigger})`

Skipped records use `{Actor}({reason})`. No-production-code triggers no semantic/build actor; an applicable Branch Work Item Gate is allowed. Tiny triggers Main plus one Build Validator per repository. Pro triggers one Build Validator per repository, one Requirement Validator, and exactly the classified specialists.

## Required Evidence Sections

```markdown
## Runtime Evidence
- **Status**: PASS
- **Artifact**: `{contained relative path}`
- **SHA-256**: `{digest}`
- **Session**: fresh | existing (override recorded)

## Scope Evidence
- **Status**: pass | no-production-code
- **Artifact**: `{contained relative path}`
- **SHA-256**: `{digest}`
- **Production Files**: {paths or None}
- **Evidence Files**: {paths or None}
- **Excluded Files**: {paths or None}

## Test Evidence
- **Status**: PASS | BLOCKED | NOT RUN (no production code)
- **Advisory**: use-unit-testing | None
- **Artifact**: `{contained relative path}`
- **SHA-256**: `{digest}`

| Repo | Command | Status | Exit | Duration | Passed | Failed | Skipped |
|---|---|---|---:|---:|---:|---:|---:|
| `{repo}` | `{argv}` | PASS / FAIL / TIMEOUT | {n} | {ms} | {n} | {n} | {n} |
```

Every production review uses `executions[]`, one unique record per repository. Failed/timeout evidence is reportable only as `BLOCKED` with sidecar `testGate.blocking: true`. Missing direct tests use exactly `use-unit-testing`; never put that advisory in findings.

## Classification and Gates

```markdown
## Review Classification
- **Files Changed**: {production-only count}
- **Changed Lines**: {production-only additions + removals}
- **Scope Status**: pass | no-production-code
- **Risk Triggers**: {labels joined by ` | `, or None}
- **Risk Evidence**: {label=evidence joined by ` | `, or None}
- **Specialist Triggers**: {Reviewer=label joined by ` | `, or None}

## Branch Work Item Gate
- **Status**: PASS | WARN | FAIL | SKIPPED
- **Branch**: {branch or None}
- **Prefix**: US | BUG | ISSUE | None
- **Work Item ID**: {id or None}
- **Expected Type**: User Story | Bug | Issue | None
- **Actual Type**: {type or None}
- **Title**: {title or None}
- **State**: {state or None}
- **Source**: pr | branch | staged | working | files
- **Reason**: {one-line result}

## Build Status
| Repo / Project | Child Read | Build | Errors | Warnings |
|---|---|---|---:|---:|
| `{name}` | PASS | PASS / FAIL / NOT RUN / JS-SKIPPED ({reason}) | {n} | {n} |
```

`jsDepsStrategy: skip | mixed` requires a `JS-SKIPPED` row. A Branch Gate FAIL is a non-file CRITICAL blocker, stops later semantic dispatch, and appears in `blockingValidations`, not `findings`.

## Semantic and Requirement Review

```markdown
## Semantic Review
{Production allowlist reviewed by Tiny main or Pro semantic actors, or Not run: no production code.}

## Requirement Validation
**Mode**: work-item | regression-only | inline | not-applicable
**Direct Work Item**: Work Item #{id} - {title} | None
**Parent Context**: Work Item #{id} - {title} | None

| Direct AC / Preserved Behavior | Status | Evidence |
|---|---|---|
| {criterion or behavior} | Addressed / Partial / Missing / Preserved / Regressed | `{production file}:{line}` plus path |

### Scope Drift
- **Scope Drift**: None
```

No-production-code states that semantic/build/test work was not run. Tiny uses `inline`. Pro always includes Scope Drift and uses `work-item` or `regression-only`.

## Summary and Finding Parity

```markdown
## Summary
{gate, build, test, requirement, specialist outcome summary}

## Detailed Findings
- Must Fix: {production/path}:{line} — [{stable id}] {summary}
- Should Fix: {production/path}:{line} — [{stable id}] {summary}
- Consider: {production/path}:{line} — [{stable id}] {summary}

None.
```

Use exactly one index row per sidecar `findings[]` item, in identical order. The target must be in `productionFiles`; an optional sidecar `action` and `line` must match the row. Cite tests/docs only as `evidence[]`. Gate/build/test blockers without a production target go in `blockingValidations[]` and may use `- Must Fix: {gate} — {reason}` without a `file:line`; they are not semantic findings.

After the index, optional detailed prose may group by production file with evidence, impact, suggestion, and confidence. Run the ADO autolink guard; raw `#number` is only for intentional work-item links.
