---
name: report-template
description: Exact metadata and finding structure for code-review-lite reports
---

# Report Template

Write `.CodeReview/{safe-branch}.lite.md`. Never use the full-review `.md` filename.

## Required Header

```markdown
# Code Review (Lite): {title}

**Date**: {YYYY-MM-DD}
**Source**: {source}
**Target**: {target}
**Files Reviewed**: {count}
**Skill**: code-review-lite v2.0.0
**Review Profile**: Docs Tiny | Code Tiny | Lite
**Main Runtime**: {resolved model} / {resolved effort}
**Agents Triggered**: {actor(runtime; reason) | ... | None}
**Agents Skipped**: {actor(reason) | ... | None}
```

Resolve model and effort from explicit launch metadata first, then current session metadata. Use `not exposed` only for an individually unavailable field and never discard a known value.

Use actor runtime strings exactly:

- `Build Validator[{repo}](haiku / default; {reason})`
- `Requirement Validator(opus / default; non-Tiny Lite)`
- `{Specialist} Reviewer(sonnet / default; {trigger})`

Skipped actors must include a reason. For Docs Tiny, Agents Triggered is `None`. Escalation produces no Lite report; `code-review-pro` owns its report.

## Body

```markdown
## Classification

- **Files Changed**: {files}
- **Changed Lines**: {lines}
- **Documentation Only**: true | false
- **Risk Triggers**: {labels joined by ` | `, or None}
- **Specialist Triggers**: {Reviewer=label joined by ` | `, or None}
- **Decision**: {why this profile was selected}

## Build Status

| Repo | Status | Errors | Warnings |
|---|---|---:|---:|
| `{repo}` | PASS / FAIL / NOT RUN | {n} | {n} |

## Requirement Evidence

| Requirement | Status | Evidence |
|---|---|---|
| {criterion} | Addressed / Partial / Missing / Not verifiable | `{file}:{line}` + behavior, or searched scope |

## Must Fix Before Merge

{Critical and High findings only, or "None."}

## Detailed Findings

### `{file}`

1. **[SEVERITY] [Actor/Family]** `{line}` - {title}
   - **Evidence**: {specific code/caller/path evidence}
   - **Impact**: {observable failure or risk}
   - **Suggestion**: {bounded fix}

## Clean Files

- `{file}` - No findings.

## Reviewer Notes

{Limits, unverified assumptions, and concise follow-up.}
```

Omit Build Status only for Docs Tiny. Code Tiny requirement evidence is produced by the main agent. Lite requirement evidence comes from the Requirement Validator and main-agent verification.

## Synthesis Rules

1. Verify every finding against the diff and worktree.
2. Deduplicate identical `file:line` findings; retain highest severity and all actor tags.
3. Requirement gaps use the evidence rules in `SKILL.md`.
4. Build errors are Critical; build warnings are Medium.
5. Must Fix includes only Critical and High findings.
6. Organize details by file, not severity.
7. State unavailable evidence as `Not verifiable`; do not infer success.

## ADO Autolink Safety

Raw `#123` is reserved for intentional ADO work-item links. Escape other number references (`PR \#4`, `AC \#2`). Run:

```text
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{safe-branch}.lite.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{safe-branch}.lite.md"
```

Then run `scripts/verify_output.py`. Both guards must pass.
