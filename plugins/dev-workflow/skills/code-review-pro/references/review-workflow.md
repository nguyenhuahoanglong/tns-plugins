---
name: review-workflow
description: Scope, diff, context, repo-local worktree, child-read, and cleanup workflow
---

# Review Workflow

## 1. Resolve Scope

Support PR ID, branch/target, staged changes, or explicit files. Prefer PR metadata when available; otherwise compute a merge base against the confirmed target branch.

**PR-only mode.** When the request is PR-only (phrase "review PR {id}" or an explicit PR-only intent), a resolvable PR object is required. Gate it deterministically:

```text
python <skill-dir>/scripts/ado_work_item.py pr-required --pr {id} --repo {repo-root}
```

Exit `0` proceeds in `pr` scope. Exit `4` (PR not found) or exit `2` (az/auth unavailable) is a hard error: stop and report that PR-only review cannot resolve PR {id}. Do **not** fall back to branch, staged, working, or files scope. Default (non-PR-only) reviews are unchanged — PR-resolution exit 2/3 stays non-blocking and the usual scope fallbacks apply.

For each repo, record source branch, target, HEAD, safe branch (`/`, `\`, `:`, and whitespace replaced by `-`), and changed project paths.

Record `scopeType` (`pr`, `branch`, `staged`, `working`, or `files`) and `scopeBase`. Compute `diffFingerprint` as SHA-256 over normalized scoped diff bytes. For working scope, include sorted untracked relative paths plus each file content hash.

## 2. Collect Once

Create `.CodeReview/` and write one full-context diff:

```text
git diff --no-prefix -U50 {base}..HEAD > ".CodeReview/.{safe-branch}.diff"
git diff --name-only {base}..HEAD
git diff --shortstat {base}..HEAD
```

For staged scope, use `git diff --cached`. Count `changedLines` as additions + deletions, not diff-file line count. Pass the absolute diff path to children; never paste the diff into every prompt.

## 3. Gather Context

In parallel:

- Detect repos and changed projects (`.sln`/`.csproj`, `package.json`, other build manifests).
- Discover instruction/standard paths and 2-3 nearby exemplars per changed source file.
- Resolve work item:

```text
python <skill-dir>/scripts/ado_work_item.py context [--pr {id}] --repo {repo-root}
```

Exit 3 means no item; exit 2 means CLI/auth unavailable. Neither blocks review. For Pro, use regression-only requirement mode when direct requirement context remains unavailable.

## 4. Repo-Local Worktrees

Docs-only creates no worktree. For Tiny/Pro, create one worktree inside each repo:

```text
{REPO_ROOT}/.CodeReview/.worktrees/{safe-branch}
```

Verify the resolved path remains beneath `{REPO_ROOT}/.CodeReview/.worktrees` before remove/recreate. Use the reviewed commit/branch without modifying the user's current checkout. For collisions, remove only a registered worktree at that exact verified path, then prune and recreate.

For a committed branch, add the source commit/ref directly. For staged or working changes, save a binary diff from `HEAD`, add a detached worktree at `HEAD`, apply the saved diff there, and copy only explicitly scoped untracked files while preserving relative paths. Never create a nested review worktree when already inside `.CodeReview/.worktrees`.

### PR scope: review the merge preview

For `pr` scope, review what actually lands (source merged into target), not source HEAD. Resolve the server merge first:

```text
python <skill-dir>/scripts/ado_work_item.py merge-preview --pr {id} --repo {REPO_ROOT} --json
```

Then add the worktree by the first tier that succeeds (always `git fetch` first so remote is current):

- **Tier A — server merge.** When `mergeStatus == succeeded` and `lastMergeCommit` is non-empty: `git -C {REPO_ROOT} fetch origin {sourceBranch} {targetBranch}`, fetch the merge commit (`git fetch origin refs/pull/{id}/merge`, or the SHA), then `git worktree add --detach {worktree} FETCH_HEAD`.
- **Tier B — local merge.** Otherwise add the worktree at `origin/{sourceBranch}`, then inside it `git merge --no-ff --no-edit origin/{targetBranch}`. On conflict, `git merge --abort` and keep the source-HEAD worktree (Tier C); record the merge was unavailable as a Reviewer Note.
- **Tier C — source HEAD.** When `az` is unavailable or A/B fail before any worktree add: today's behavior, worktree at `origin/{sourceBranch}`.

The worktree root convention and the containment check are unchanged — only the reviewed commit changes. Record `prMergePreview` (bool) and `mergePreviewStrategy` (`server-merge | local-merge | source-head`) in the sidecar. `scopeBase`/`diffFingerprint` stay defined over `{scopeBase}..HEAD`; merge preview changes worktree contents only, so follow-up reclassification stays deterministic.

### Prepare JS dependencies

A fresh worktree has no `node_modules`, so JS/PCF build gates cannot run. After worktree add and before dispatching the Build Validator, for repos with JS projects:

```text
python <skill-dir>/scripts/prepare_worktree_deps.py --worktree {worktree} --repo {REPO_ROOT} --diff {diff-path} --json
```

It junctions unchanged-dependency `node_modules` from the source repo (no install) and signals `skip-build` for any project whose `package.json`/lockfile changed. Record the `jsDepsStrategy` roll-up (`link | skip | mixed | none`). A `skip-build` project's build row is reported `JS-SKIPPED (deps changed)` — surfaced, never silently passed. Never authorize an implicit dependency install.

Agents receive absolute paths for worktree, diff, role prompt, standards, prior report, and changed files.

## 5. Branch Work Item Gate

For PR and branch scope, run this gate in parallel with the first Build Validator and record it with `haiku / default`:

```text
python <skill-dir>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{sourceBranch}" --repo "{repo}"
```

For staged, working, and files scope, run it with the same command and record `SKIPPED`. The script validates branch format `{slug}/{work-item-id}` with optional `-{text}` and calls `az boards work-item show` to ensure the ID exists and its `System.WorkItemType` is `User Story`, `Bug`, or `Issue`. `WARN` means the ID/type is valid but the branch prefix is non-standard or mismatched; continue review. `FAIL` blocks Requirement Validator and specialists; synthesize a report with completed build results and a CRITICAL Must Fix.

## 6. Child-Read Preflight

Create `{worktree}/.code-review-preflight` with a random review token. Include its absolute path and token in every child prompt, plus role prompt, worktree, diff, and role-specific paths.

Every child must read the sentinel first and emit `Child Read: PASS {token}` before analysis. Missing/unreadable/mismatched token emits `Child Read: FAIL` and stops that child. Do not accept output lacking the exact PASS.

The first child per repo is its Build Validator. Repair/retry any failed Build child before dispatching Requirement or specialists. Later children repeat the same preflight; a failed preflight is infrastructure failure, not an intentional skip.

## 7. Cleanup

Run unconditionally after synthesis/verification or infrastructure failure:

1. Resolve and verify each worktree path is still under its repo-local `.CodeReview/.worktrees`.
2. Remove the exact sentinel and temporary applied-diff artifact inside the verified worktree.
3. Remove `node_modules` junctions from the verified worktree **before** removing the worktree, so `git worktree remove` cannot recurse into a junction and delete the source repo's real `node_modules`:
   ```text
   python <skill-dir>/scripts/prepare_worktree_deps.py --teardown --worktree {worktree}
   ```
4. Remove only those exact worktrees through `git worktree remove --force`.
5. Prune worktree metadata.
6. Delete review diff artifacts; keep report and v2 sidecar.

Never recursively delete a computed path before containment and registered-worktree checks pass.
