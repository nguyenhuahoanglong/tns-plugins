---
name: yana-pcf-deploy
description: "Use when building or deploying Yana PCF variants to a sandbox, including personal current-work builds and RC checks; production stays CI/CD-only."
---

# Yana PCF Deploy

Build and deploy `Core.Component.PCF` Grid and QuickView variants from source that matches the user's intent. Use `CurrentWork` for developer testing and `Pinned` for release orchestration. Current-work first syncs the identified latest source into the checked-out branch, preserving WIP, then builds a disposable snapshot of that synced checkout plus WIP.

## Setup

1. Resolve PCF repo root and read `AGENTS.local.md` for already-known PCF preferences. Never copy that private file into a build snapshot.
2. Run the bundled `scripts/pcf_setup.py status --repo <repo> --scope deploy`. If `NEEDS_SETUP`, read [setup guide](references/setup.md) and complete only missing setup. Reuse saved preferences and setup receipts on later runs. Do not repeat the setup interview when values already exist.
3. Use saved setup receipt's `runtimes.python` as `-PythonExecutable` or `YANA_PCF_PYTHON`; do not use a Microsoft Store `WindowsApps` alias. Reuse the same saved executable path at plan and apply.
4. For `Personal` only, resolve the variant from `personal_variant`. If absent, ask once for an alphanumeric, non-reserved name, save it with setup, then continue. RC uses the shared `RC` variant and must not ask for a personal variant. Never default a personal variant to `Long`.
5. Deployment environment comes from `deploy_environment_url`, defaulting to DevQA only when no saved URL exists. A user-specified sandbox URL takes precedence for that run. Production is never a local target.

Setup stores preferences and executable paths only. PAC authentication and Azure sign-in remain in their native tools. Confirm active org at each deployment because saved config cannot prove live sign-in state.

## Resolve intent and source

Read the request, current branch, upstream, Git status, and saved `release_sources` mapping before choosing source. Do not ask for facts already evident from those sources.

| User intent | Source policy | Behavior |
| --- | --- | --- |
| “Deploy my variant” / personal test | `CurrentWork` + `Personal` | Use the checked-out branch. Fetch and merge its configured upstream tip into that branch, then snapshot committed code plus safe staged, unstaged, and untracked source changes. Use the configured personal variant. |
| Personal test on branch without upstream | `CurrentWork` + `Personal` | Deploy local branch and WIP as-is; clearly report that there is no remote upstream to update. |
| “Deploy RC” on exact `X.Y.Z` release branch | `CurrentWork` + `RC` | Fetch latest from that exact release branch and merge it into the checked-out branch. Use shared variant `RC`. |
| “Deploy RC” on work branch with saved `release_sources` mapping | `CurrentWork` + `RC` | Fetch mapped exact release branch and merge latest into the checked-out branch, preserving work-branch commits and WIP. |
| “Deploy RC” on work branch with reflog showing it was created from exact `origin/X.Y.Z` | `CurrentWork` + `RC` | Use that release only when the recorded creation commit is an ancestor of both current HEAD and latest release tip; otherwise ask for the exact source. |
| “Deploy RC” on work branch with no proven mapping or creation evidence | Ask one focused question | Ask which exact `X.Y.Z` branch this work branch targets. Do not infer from common ancestor or choose highest SemVer. After confirmation, save mapping with setup and continue. |
| Release orchestrator supplies exact approved branch and SHA | `Pinned` | Build exactly that remote SHA in an isolated worktree. Do not merge upstream or include current-checkout WIP. |
| Production | blocked | Production deployment remains CI/CD from `master`; never import locally. |

An explicit current-run RC source supplied by the user can resolve the question without changing the saved mapping. A configured mapping means user-confirmed branch relationship; still require shared Git history before merge. A common ancestor alone is not evidence of which release the user intends.

## Plan and deploy

Use the bundled helper by absolute path when current directory differs from skill directory. `Pinned` remains default for compatibility with release orchestration; direct developer testing must select `CurrentWork`.

```powershell
& '<skill-root>\scripts\deploy-target.ps1' -Target Personal -SourcePolicy CurrentWork -Repo '<repo>' -PythonExecutable '<saved-runtimes.python>' -Plan
& '<skill-root>\scripts\deploy-target.ps1' -Target RC -SourcePolicy CurrentWork -Repo '<repo>' -PythonExecutable '<saved-runtimes.python>' -Plan
& '<skill-root>\scripts\deploy-target.ps1' -Target RC -SourcePolicy Pinned -Branch '<X.Y.Z>' -ExpectedSourceSha '<sha>' -Repo '<repo>' -PythonExecutable '<saved-runtimes.python>' -Plan
& '<skill-root>\scripts\deploy-target.ps1' -PlanFile '<plan.json>' -Apply -ConfirmSourceSha '<planned-sha>'
```

Before apply, show source branch and SHA, current branch/HEAD, local-change hash when present, merge strategy, variant, environment, and build mode. Tell the user when syncing will create a local merge commit. An explicit, resolved request to deploy authorizes the deployment; do not add another confirmation step. Ask only when source, setup, target, or another required decision remains unresolved. Apply rechecks source freshness, branch/HEAD, local WIP and excluded private-file fingerprints, and exact active PAC org. Any source drift or WIP edit during preflight stops before merge. The helper first proves the complete merge in a disposable worktree, then syncs the latest source into the current branch and snapshots the post-sync code plus WIP. Conflicts or overlapping local edits stop without stashing, discarding, or resolving for the user. Do not create a separate source commit, push, cherry-pick, bump version, edit ADO/PR/notes, or remove deployed variants. A Git-created merge commit is allowed only when the planned strategy is `merge-commit` and is disclosed before apply.

The isolated build snapshot contains the checked-out branch after source sync, local commits, staged and unstaged tracked changes, and non-ignored untracked source files. It excludes `AGENTS.local.md`, environment files, credentials, private key material, and ignored outputs, including accidentally tracked files matching private-file rules. The helper records original and synced HEADs, source branch/SHA, local-change fingerprint, merge strategy, and source/snapshot hashes. Variant build stamps exist only in the disposable snapshot.

Restore package-lock dependencies inside snapshot with `npm ci --ignore-scripts --no-audit --no-fund`; then tracked deploy script builds both controls and unmanaged solution. Network restore failure blocks deployment before import. Build receipt records package SHA-256 separately from source SHA and timestamp technical version.

## Target and result checks

Before build, verify `pac org who` matches exact planned HTTPS org origin. Before import, bundled wrapper requires `Solution/scripts/deploy-variant.ps1` to support `ExpectedOrgUrl` and publish readback contract. If source branch lacks that contract, stop before build/import and provide [the narrow patch](assets/deploy-variant-contract.patch) for review/application in the PCF repository; do not silently patch the user's checkout.

The target script must recheck expected org immediately before import, fail if `PublishAllXml` cannot complete, and read back the exact unmanaged variant solution. Receipt success requires all of: build success, import success, publish success, solution readback, and package hash. If import succeeds but publish or readback fails, report partial deployment; do not emit a successful receipt.

`Pinned` source uses exact `Branch` or exact `SourceVersion`; `latest` never means highest SemVer. `Preview` remains pinned `origin/dev`. `Prod` always blocks. Preserve variant, source version, timestamp technical version, and environment as separate receipt fields.

## Recovery

- Source SHA changed after plan: re-plan and show the new SHA before apply.
- Local files changed after plan: re-plan to capture new local fingerprint.
- Merge or overlapping WIP conflict: stop before build; keep all checkout changes and ask user to resolve the conflict.
- Wrong PAC org: stop before build/import; ask user to select intended profile, then recheck.
- Target script contract missing: stop before build/import; provide patch asset, then retry after repository update.
- Build failed: no successful import claim; keep receipt/log and identify failing command.
- Import succeeded but publish/readback failed: report partial state and exact repair command; retry only publish/readback when target script supports that recovery.
