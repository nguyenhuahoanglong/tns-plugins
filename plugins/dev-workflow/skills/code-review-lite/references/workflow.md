---
name: workflow
description: Scope, classification, local worktree, child-read preflight, and cleanup workflow for code-review-lite
---

# Workflow

## Scope and Diff

Resolve PR, branch, staged changes, or explicit files. Prefer PR metadata; fall back to git. Write the full diff once to:

```text
.CodeReview/.{safe-branch}.diff
```

Sanitize branch names by replacing `/`, `\`, `:`, and whitespace with `-`. Count changed lines as added plus deleted lines, excluding diff headers.

For multi-repo work, keep one scope record per repo:

```text
repo root | source | target | changed files | changed lines | diff path
```

## Requirement Context

User-provided requirement text has priority. Otherwise run once:

```text
python <skill>/scripts/ado_work_item.py context [--pr {pr-id}] --repo "{repo}"
```

Exit `0`: use returned context. Exit `2` or `3`: check `.docs/ado-context.md`, then ask at most one skippable question. Never block review or retry fetch.

## Classification

Classify from behavior, not filename alone.

1. Detect risk flags before applying Tiny thresholds.
2. Docs Tiny applies whenever every changed file is documentation text with no runtime effect, independent of size.
3. Code Tiny requires `<=3` files, `<=100` changed lines, and zero elevated-risk flags.
4. Remaining non-documentation changes are Lite or escalate.
5. Non-Tiny changes map to Security, Performance, Philosophy, and Standard reviewers.
6. More than one reviewer trigger routes to `code-review-pro`.

Examples that are not docs-only: config examples consumed by tooling, generated schemas, package metadata, deployment YAML, executable snippets, and scripts.

## Local Worktree

Agent-backed profiles use one repo-local worktree per repo:

```text
{repo}/.CodeReview/.worktrees/{safe-branch}
```

Resolve and verify the absolute path remains under `{repo}/.CodeReview/.worktrees/` before removing or replacing it.

For a committed branch:

```text
git fetch origin {source-branch}
git worktree add "{worktree}" "origin/{source-branch}"
```

For staged/working changes:

1. Save a binary diff from `HEAD` to `.CodeReview/.{safe-branch}.working.diff`.
2. Add a detached worktree at `HEAD`.
3. Apply the saved diff in the worktree.
4. Copy only explicitly scoped untracked files, preserving relative paths.

Do not create a nested review worktree when already inside `.CodeReview/.worktrees/`.

## Child-Read Preflight

Before dispatch, create `{worktree}/.code-review-preflight` containing a random review token. Include its absolute path and token in every child prompt.

Each child must perform this first:

```text
Read {absolute-preflight-path}.
Return "Child Read: PASS {token}" before analysis.
If missing, unreadable, or mismatched, return "Child Read: FAIL" and stop.
```

Treat missing PASS as dispatch failure. Do not accept findings from a child that failed preflight.

## Dispatch Order

Announce each actor with reason and exact runtime profile before dispatch.

- Docs Tiny: no dispatch.
- Code Tiny: Build Validators in parallel, one per repo.
- Lite: Build Validators; Requirement Validator always; optional single named specialist only after passing builds.
- Escalation: announce triggered reviewers and invoke `code-review-pro` instead.

Build failure skips specialist, but Requirement Validator still runs before synthesis.

## Build-Fail Report

Use `.CodeReview/{safe-branch}.lite.md` and include normal metadata plus:

```markdown
## Build Status

| Repo | Status | Errors | Warnings |
|---|---|---:|---:|
| `{repo}` | FAIL | {count} | {count} |

## Recommendation

Fix build errors and rerun review. Requirement validation completed; specialist review skipped because build failed.
```

## Cleanup

Run after report synthesis and verification, including failure paths:

1. Verify each worktree path is under the expected repo-local worktree root.
2. Remove worktrees with `git worktree remove --force "{worktree}"`.
3. Remove only temporary preflight and diff artifacts.
4. Keep `.CodeReview/{safe-branch}.lite.md`.

Never remove `.CodeReview/` recursively.
