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
git diff --no-prefix -U20 {base}..HEAD > ".CodeReview/.{safe-branch}.diff"
git diff --name-only {base}..HEAD
git diff --shortstat {base}..HEAD
```

For staged scope, use `git diff --cached`. Count `changedLines` as additions + deletions, not diff-file line count. Pass the absolute diff path to children; never paste the diff into every prompt. Child agents read the full file from the worktree whenever a hunk needs more surrounding context than the 20 lines shown.

## 3. Persist Scope and Test Evidence

Before classifier or worktree creation, run `review_harness scope-manifest` over the complete changed-path list and save the JSON beneath `.CodeReview/`. Its `files` entries are the authority: `productionFiles`, `evidenceFiles`, and `excludedFiles` must be unique, non-overlapping, and exactly recomputable from them. Count changed files/lines and derive risk only from production paths. Empty `productionFiles` sets `scopeStatus: no-production-code`; run only the applicable Branch Work Item Gate, then stop without worktree, build/test, semantic review, or findings.

For production scope, run `discover-tests` from changed symbols, then one deterministic `test-gate` command per reviewed repository. Persist a single test artifact with `discovery` and non-empty `executions[]`. Each execution records unique `repo`, command argv, `pass | fail | timeout`, exit code, duration, passed/failed/skipped counts, bounded stdout/stderr, and truncation state. Missing direct tests require non-empty `changedSymbols`, empty `directTests`, and exactly `advisory: use-unit-testing`; the advisory is not a finding. A failed/timeout execution is structurally valid only when the artifact status is `blocked`, report Test Evidence is `BLOCKED`, and sidecar `testGate` is `{status: BLOCKED, blocking: true}`.

Hash each runtime/scope/test artifact and record only a contained relative `path` plus lowercase SHA-256 in the v3 sidecar. Never replace or rewrite an artifact after computing its digest.

## 4. Gather Context

In parallel:

- Detect repos and changed projects (`.sln`/`.csproj`, `package.json`, other build manifests).
- Discover instruction/standard paths and 2-3 exemplars per repo/stack (not per changed file).
- Resolve work item:

```text
python <skill-dir>/scripts/ado_work_item.py context [--pr {id}] --repo {repo-root}
```

Exit 3 means no item; exit 2 means CLI/auth unavailable. Neither blocks review. For Pro, use regression-only requirement mode when direct requirement context remains unavailable.

## 5. Repo-Local Worktrees

No-production-code creates no worktree. For Tiny/Pro, create one worktree inside each repo after scope/test evidence is persisted:

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
python <skill-dir>/scripts/prepare_worktree_deps.py --worktree {worktree} --repo {REPO_ROOT} --diff {diff-path} --require-bin {build-tool} --json
```

Pass `--require-bin` with the exact tool the approved build command invokes (e.g. `vite` for `npm run build:dev` → `vite build`, `tsc`, `webpack`, `react-scripts`, `vitest`); repeat the flag for multiple tools. This makes the health check tool-aware: a **production-only** source `node_modules` (populated `.bin` but missing the build tool — e.g. `vite`, a devDependency — resolved uniformly against each project's `.bin`) is judged unusable and re-installed, rather than junctioning a broken tree that then fails with "{tool} is not recognized". It junctions the source repo's `node_modules` when usable (exists with a non-empty `.bin` **and** all `--require-bin` tools resolve, or the project has no deps). When source deps are missing/unusable and a lockfile exists, it performs a frozen, lockfile-gated install inside the worktree project (`npm ci --prefer-offline --no-audit --no-fund` / `yarn install --frozen-lockfile` / `pnpm install --frozen-lockfile --prefer-offline`) — strategy `install`; a failed install is `install-failed`, surfaced but not fatal. Otherwise it signals `skip-build` with reason `deps changed` or `no lockfile` (add `--no-install` to force `skip-build` with reason `deps unavailable` instead of installing). Record the `jsDepsStrategy` roll-up (`link | skip | install | mixed | none`).

**Dependency installs are performed ONLY by `prepare_worktree_deps.py`** (frozen, lockfile-gated) — child agents never install. Installs can take minutes: run the script itself with an extended command timeout (up to 10 minutes), independent of its own `--install-timeout` (default 480s).

**Critical orchestration rule**: a project whose deps could not be made usable (script result `skip-build` or `install-failed`) gets build row `JS-SKIPPED ({reason})` with reason `deps changed` | `no lockfile` | `install failed`, and the Build Validator is **not** dispatched with that project's JS build command. An environment gap must never be reported as a build FAIL. A project whose strategy is `install` succeeded and is safe to build normally — its PASS reflects freshly installed dependencies, not stale ones.

Agents receive absolute paths for worktree, diff, role prompt, standards, prior report, and changed files. Requirement Validator and the four specialist reviewers also receive `references/agents/_shared-contract.md` alongside their role prompt.

## 6. Branch Work Item Gate

For PR and branch scope, run this gate in parallel with the first Build Validator and record it with `haiku / default`:

```text
python <skill-dir>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{sourceBranch}" --repo "{repo}"
```

For staged, working, and files scope, run it with the same command and record `SKIPPED`. The script validates branch format `{slug}/{work-item-id}` with optional `-{text}` and calls `az boards work-item show` to ensure the ID exists and its `System.WorkItemType` is `User Story`, `Bug`, or `Issue`. `WARN` means the ID/type is valid but the branch prefix is non-standard or mismatched; continue review. `FAIL` blocks Requirement Validator and specialists; synthesize a report with completed build results and a CRITICAL Must Fix.

## 7. Child-Read Preflight

Create `{worktree}/.code-review-preflight` with a random review token. Include its absolute path and token in every child prompt, plus role prompt, worktree, diff, and role-specific paths.

Every child must read the sentinel first and emit `Child Read: PASS {token}` before analysis. Missing/unreadable/mismatched token emits `Child Read: FAIL` and stops that child. Do not accept output lacking the exact PASS. Semantic children also receive the persistent diff, production allowlist, evidence paths, scope-manifest path, and test-evidence path; they run no git command and may target findings only at allowlisted production paths.

The first child per repo is its Build Validator. Repair/retry any failed Build child before dispatching Requirement or specialists. Later children repeat the same preflight; a failed preflight is infrastructure failure, not an intentional skip.

## 8. Cleanup

Run unconditionally after synthesis/verification or infrastructure failure:

1. Resolve and verify each worktree path is still under its repo-local `.CodeReview/.worktrees`.
2. Remove the exact sentinel and temporary applied-diff artifact inside the verified worktree.
3. Remove `node_modules` junctions from the verified worktree **before** removing the worktree, so `git worktree remove` cannot recurse into a junction and delete the source repo's real `node_modules`:
   ```text
   python <skill-dir>/scripts/prepare_worktree_deps.py --teardown --worktree {worktree}
   ```
4. Remove only those exact worktrees through `git worktree remove --force`.
5. Prune worktree metadata.
6. Delete temporary review diff artifacts only after verification; keep report, v3 sidecar, and hash-bound evidence artifacts.

Never recursively delete a computed path before containment and registered-worktree checks pass.
