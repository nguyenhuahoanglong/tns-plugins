---
name: workflow
description: Scope, classification, local worktree, child-read preflight, and cleanup workflow for code-review-lite
---

# Workflow

## Scope and Diff

Resolve PR, branch, staged changes, or explicit files. Prefer PR metadata; fall back to git. Record source branch for PR/branch scope.

When the request is PR-only ("review PR {id}" or explicit PR-only intent), a resolvable PR is required. Gate it with `python <skill>/scripts/ado_work_item.py pr-required --pr {id} --repo "{repo}"`: exit `0` proceeds in `pr` scope; exit `4` (PR not found) or `2` (az/auth unavailable) is a hard error — stop and report, do not fall back to branch/staged/working/files. Default (non-PR-only) reviews keep the existing fallbacks.

Write the full diff once to:

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

When a work item resolves, enrich it with design-doc context: read the repo `AGENTS.md` for a declared design-doc root (`Design docs: <path>` or equivalent), use `.docs/ado-context.md` to map the parent Feature to its design-doc file(s), and pass the matching section to the Requirement Validator as elaboration of the AC. Treat it as context only, not new binding criteria; fall back to AC-only when no root is declared or no section matches. Never block on this.

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

For PR scope, review the merge preview (source merged into target), not source HEAD. Resolve it with `python <skill>/scripts/ado_work_item.py merge-preview --pr {id} --repo "{repo}" --json`, then pick the first tier that works (always `git fetch` first):

1. **Server merge** — `mergeStatus == succeeded` and `lastMergeCommit` set: fetch `refs/pull/{id}/merge` (or the SHA) and `git worktree add --detach "{worktree}" FETCH_HEAD`.
2. **Local merge** — else worktree at `origin/{source-branch}`, then `git merge --no-ff --no-edit origin/{target-branch}`; on conflict `git merge --abort` and keep source HEAD.
3. **Source HEAD** — when `az` is unavailable or the above fail: the committed-branch behavior above.

Record `mergePreviewStrategy` (`server-merge | local-merge | source-head`) in the report. The reviewed commit changes, but the worktree root convention does not.

For staged/working changes:

1. Save a binary diff from `HEAD` to `.CodeReview/.{safe-branch}.working.diff`.
2. Add a detached worktree at `HEAD`.
3. Apply the saved diff in the worktree.
4. Copy only explicitly scoped untracked files, preserving relative paths.

Do not create a nested review worktree when already inside `.CodeReview/.worktrees/`.

For repos with JS projects, after worktree add and before the Build Validator, run `python <skill>/scripts/prepare_worktree_deps.py --worktree "{worktree}" --repo "{repo}" --diff "{diff-path}" --json`. It junctions unchanged-dependency `node_modules` from the source repo (never installs) and signals `skip-build` for any project whose `package.json`/lockfile changed. A `skip-build` project's build row is reported `JS-SKIPPED (deps changed)`, not silently passed.

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

- PR/branch scope: Branch Work Item Gate runs with `haiku / default` in parallel with first Build Validator:
  `python <skill>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{sourceBranch}" --repo "{repo}"`
- Staged, working, and files scope: run Branch Work Item Gate and record `SKIPPED`.
- Branch Work Item Gate validates `{slug}/{work-item-id}` with optional `-{text}` and calls `az boards work-item show` to verify the ID exists and `System.WorkItemType` is `User Story`, `Bug`, or `Issue`.
- Gate `WARN`: record the branch convention/type-prefix mismatch and continue review.
- Gate `FAIL`: write a report with completed build results, record a Critical finding, skip Requirement Validator and specialists, and stop.
- Docs Tiny: Branch Work Item Gate only when applicable; no other dispatch.
- Code Tiny: Branch Work Item Gate plus Build Validators in parallel, one per repo.
- Lite: Branch Work Item Gate plus Build Validators; Requirement Validator always after gate pass; optional single named specialist only after passing builds.
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
2. Remove `node_modules` junctions from the verified worktree **before** removing it, so `git worktree remove` cannot recurse into a junction and delete the source repo's real `node_modules`: `python <skill>/scripts/prepare_worktree_deps.py --teardown --worktree "{worktree}"`.
3. Remove worktrees with `git worktree remove --force "{worktree}"`.
4. Remove only temporary preflight and diff artifacts.
5. Keep `.CodeReview/{safe-branch}.lite.md`.

Never remove `.CodeReview/` recursively.
