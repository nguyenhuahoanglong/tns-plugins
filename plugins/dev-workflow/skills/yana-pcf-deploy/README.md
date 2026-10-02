# Yana PCF Deploy

## Purpose

Build and deploy YanaGrid and YanaQuickView sandbox variants from either a pinned release SHA or the checked-out branch after syncing its latest approved source and preserving developer changes.

## Pain Points

- Old workflow required a hand-selected remote branch, defaulted Personal to `Long`, and could not include working changes.
- RC selection must follow active release intent; choosing highest SemVer or guessing from a common ancestor can deploy the wrong code.
- Build/import must be tied to the planned org, and success must include publish and solution readback evidence.

## Intention

- `intent.json` records the active user-approved scope. Historical purpose was reconstructed from the 2026-08-24 source docs and remains unconfirmed; no historical sidecar existed before this update.
- Active revision preserves pinned release deployment and adds approved current-work Personal/RC source handling. See source and approval details in the intention record.

## Changelog

### 2026-10-02 - Current-work source and provenance

- User-approved Option A: extended existing deploy skill while retaining `Pinned` source policy for release orchestration.
- Added current-work source planner/snapshot helper. It proves the merge and WIP in a disposable worktree, rechecks branch/HEAD/WIP immediately before syncing the latest tip into the checked-out branch, and builds from a matching post-sync snapshot.
- Added explicit RC source mapping plus verified branch-creation reflog evidence; ambiguous branch relationship asks once and never infers from common ancestry/highest SemVer.
- Added local-only personal deployment when a branch has no upstream, with an explicit no-remote-update receipt.
- Removed Personal=`Long` default. Personal variant and deployment environment resolve from managed local config.
- Added target-org pin, publish/readback contract guard, package hash receipt, source helper tests, and PCF script patch asset. Target repo patch was not applied by this skill edit.
- Validation: Python helper unittest suite and skill intent/structure checks run on 2026-10-02; PowerShell wrapper syntax and live deployment behavior remain subject to available runtime checks.

### 2026-08-24 - Deploy-only 2.0

- Added explicit source-branch plan/apply workflow with isolated worktree and mocked safety tests.
