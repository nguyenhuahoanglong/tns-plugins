---
name: report-template
description: Exact v3 gate, semantic-agent, evidence, and finding structure for code-review-lite reports
---

# Report Template

Write `.CodeReview/{safe-branch}.lite.md`; never use the full-review filename. Escalation produces no Lite report because `code-review-pro` owns that flow.

## Header

```markdown
# Code Review (Lite): {title}

**Date**: {YYYY-MM-DD}
**Source**: {source}
**Target**: {target}
**Files Reviewed**: {count}
**Skill**: code-review-lite v3.0.0
**Review Profile**: Docs Tiny | Code Tiny | Lite
**Main Runtime**: {model or not exposed} / {effort or not exposed}
**PR-Only**: true | false
**Merge Preview**: server-merge | local-merge | source-head | n/a
**Context Manifest**: {absolute Lite context path | n/a}
```

Use `PR-Only: true` only for enforced PR-only mode. Use merge preview `n/a` outside PR scope. Lite requires its absolute context-manifest path; Docs/Code Tiny use `n/a`. Resolve main runtime from explicit launch metadata, then session metadata; never replace a known field.

## Classification

```markdown
## Classification

- **Files Changed**: {files}
- **Changed Lines**: {lines}
- **Documentation Only**: true | false
- **Risk Triggers**: {labels or None}
- **Specialist Triggers**: {Reviewer=label or None}
- **Decision**: {profile reason}
```

## Deterministic Gates

```markdown
## Deterministic Gates

### Branch Work Item Gate
- **Status**: PASS | WARN | FAIL | SKIPPED
- **Branch**: {source or None}
- **Work Item**: {prefix/id, expected and actual type, title/state, or None}
- **Source**: pr | branch | staged | working | files
- **Reason**: {bounded evidence}

### Build Gates
| Repo | Status | Command | Exit | Errors | Warnings | Log / Reason |
|---|---|---|---:|---:|---:|---|
| `{repo}` | PASS / PASS WITH WARNINGS / FAIL / NOT RUN (environment) / NOT RUN (timeout) / JS-SKIPPED | `{approved command}` | {n or n/a} | {n} | {n} | `{log}` / {reason} |
```

Docs Tiny writes `Build Gates: Not applicable`. For JS-SKIPPED, include `deps changed`, `no lockfile`, or `install failed`; never invent an exit code. Note freshly installed dependencies. Branch FAIL is Critical, skips semantic children, and preserves already-completed build evidence. Build FAIL is Critical; environment/timeout/JS gaps are explicit unverified gaps.
Each Lite row must exactly mirror its context `buildResults` record: repo, status, command, `commandExitCode` (`n/a` for null), error/warning counts, log path, and reason.

## Semantic Agents

```markdown
## Semantic Agents

### Triggered
- Requirement Validator (`opus / default`) - {reason}
- {Specialist} Reviewer (`sonnet / default`) - {trigger}
- None

### Skipped
- Requirement Validator - {Docs/Code Tiny, branch failure, or None}
- {Specialist} Reviewer - {profile, no trigger, branch/build failure, validation gap, or None}

### Agent Usage
| Agent | Runtime | Context Mode | Input Tokens | Cache Read | Cache Write | Output Tokens |
|---|---|---|---:|---:|---:|---:|
| Requirement Validator | `opus / default` | isolated manifest | {number or `not exposed`} | {number or `not exposed`} | {number or `not exposed`} | {number or `not exposed`} |
| {Specialist} Reviewer | `sonnet / default` | isolated manifest | {number or `not exposed`} | {number or `not exposed`} | {number or `not exposed`} | {number or `not exposed`} |
```

List only triggered children in Agent Usage. Gates never appear there. Docs/Code Tiny and branch-fail reports use `Triggered: None` and `Agent Usage: None`. Lite always triggers Requirement after branch pass/warn/skip, including build failure; a specialist runs only when selected and builds pass/pass-with-warnings. Token/cache cells accept non-negative integers or exact `not exposed`, never estimates.

## Requirement and Behavior Evidence

```markdown
## Requirement Evidence

| Requirement | Status | Evidence |
|---|---|---|
| {criterion} | Addressed / Partial / Missing / Not verifiable | `{file}:{line}` + behavior, or searched scope |

## Behavior Preservation and Collateral Impact

| Behavior | Classification | Base -> New | Impact Trace | Preservation Evidence | Status |
|---|---|---|---|---|---|
| {behavior} | Direct requirement / Necessary collateral / Unrelated / Unclear | {before} -> {after} | {caller/consumer/event/state/config} | `{tests/paths}` or None | Preserved / Regressed / Unproven |

- **Collateral Impact**: None
- **Scope Drift**: None
```

Use the sentinels only when clean. Work-item Lite lists every direct criterion, including `Addressed`, and every material behavior delta, including `Preserved`; omit only redundant prose. Collateral is evidence, not a new criterion. `Addressed` requires changed implementation. `Regressed` requires exposed-path evidence; absent proof is `Unproven`. Docs/Code Tiny evidence may come from the main agent; Lite evidence comes from the Requirement Validator plus main verification.

## Findings and Recommendation

```markdown
## Must Fix Before Merge
{Critical/High findings, or None.}

## Detailed Findings
### `{file}`
1. **[CRITICAL|HIGH|MEDIUM|LOW] [Actor/Family]** `{line}` - {title}
   - **Evidence**: {specific code/caller/path evidence}
   - **Impact**: {observable consequence}
   - **Suggestion**: {bounded correction}

## Recommendation
{merge decision, build/validation gaps, and concise next action}
```

Verify each finding against the diff/worktree, deduplicate identical locations at highest severity, and organize by file. Build warnings are Medium. Branch/build code failures are Critical. Scope drift is advisory HIGH/MEDIUM and never blocks by itself. State unavailable evidence; do not infer success.

## ADO Autolink and Verification

Escape non-ADO number references such as `PR \#4` and `AC \#2`, then run:

```text
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{safe-branch}.lite.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{safe-branch}.lite.md"
python <skill>/scripts/verify_output.py ".CodeReview/{safe-branch}.lite.md"
```
