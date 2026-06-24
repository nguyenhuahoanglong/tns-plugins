---
name: review-workflow
description: Scope, diff, context, repo-local worktree, child-read, and cleanup workflow
---

# Review Workflow

## 1. Resolve Scope

Support PR ID, branch/target, staged changes, or explicit files. Prefer PR metadata when available; otherwise compute a merge base against the confirmed target branch.

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

Agents receive absolute paths for worktree, diff, role prompt, standards, prior report, and changed files.

## 5. Branch Work Item Gate

For PR and branch scope, run this gate in parallel with the first Build Validator and record it with `haiku / default`:

```text
python <skill-dir>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{sourceBranch}" --repo "{repo}"
```

For staged, working, and files scope, run it with the same command and record `SKIPPED`. The script validates branch format `(US|BUG|ISSUE)/{id}-{slug}` and calls `az boards work-item show` to ensure the ID exists and its `System.WorkItemType` matches `User Story`, `Bug`, or `Issue`. `FAIL` blocks Requirement Validator and specialists; synthesize a report with completed build results and a CRITICAL Must Fix.

## 6. Child-Read Preflight

Create `{worktree}/.code-review-preflight` with a random review token. Include its absolute path and token in every child prompt, plus role prompt, worktree, diff, and role-specific paths.

Every child must read the sentinel first and emit `Child Read: PASS {token}` before analysis. Missing/unreadable/mismatched token emits `Child Read: FAIL` and stops that child. Do not accept output lacking the exact PASS.

The first child per repo is its Build Validator. Repair/retry any failed Build child before dispatching Requirement or specialists. Later children repeat the same preflight; a failed preflight is infrastructure failure, not an intentional skip.

## 7. Cleanup

Run unconditionally after synthesis/verification or infrastructure failure:

1. Resolve and verify each worktree path is still under its repo-local `.CodeReview/.worktrees`.
2. Remove the exact sentinel and temporary applied-diff artifact inside the verified worktree.
3. Remove only those exact worktrees through `git worktree remove --force`.
4. Prune worktree metadata.
5. Delete review diff artifacts; keep report and v2 sidecar.

Never recursively delete a computed path before containment and registered-worktree checks pass.
