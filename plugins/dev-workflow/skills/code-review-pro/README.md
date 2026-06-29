# Code Review Pro

## Purpose

Adaptive evidence-driven code review for PRs, branches, staged changes, and follow-up iterations. Version 2.1.0 classifies each diff as Docs-only, Tiny, or Pro, then runs the minimum valid review topology without weakening requirement or regression coverage.

## Pain Points

- Fixed fan-out spends specialist agents on low-risk diffs.
- File/line size alone can misclassify small but dangerous API, schema, auth, dependency, lifecycle, state, or configuration changes.
- Requirement review disappears when no work item exists, leaving regressions and unrelated behavior unchecked.
- External worktrees and unreadable child paths cause brittle agent runs.
- Reports lack machine-verifiable skill, runtime, trigger, skip, and profile provenance.
- Follow-ups can use different review rules from initial reviews and lose reproducibility.

## Design Notes

### Adaptive profiles

- Docs-only: main-agent documentation review, zero agents.
- Tiny: at most 3 files and 100 changed lines with no risk triggers; one Build Validator per repo, then main-agent all-lens review.
- Pro: Build Validator per repo, Requirement Validator always, and only risk-triggered specialists.

### Requirement contract

Direct task/acceptance criteria are binding. Parent items supply context but do not broaden scope. Without a work item, Requirement Validator switches to regression-only mode and compares base versus new behavior across symbols, callers, consumers, events, state, tests, and unrelated behavior.

### Isolation and provenance

Worktrees live under each repo at `.CodeReview/.worktrees/{safe-branch}`. Build children perform a read preflight before other children run. Reports carry combined skill/version provenance plus Review Profile, Main Runtime, Agents Triggered, and Agents Skipped fields. Sidecars use record version 2 and include `skillName`, `skillVersion`, and `reviewProfile`.

## Changelog

### 2026-06-29 - v2.1.0 PR-centric review and scope discipline

- Added enforced **PR-only mode**: "review PR {id}" requires a resolvable PR (gated by `ado_work_item.py pr-required`, exit 4 = not found) and errors instead of silently falling back to branch/working scope.
- PR scope now reviews the **merge preview** (source merged into target) via `ado_work_item.py merge-preview`, with server-merge → local-merge → source-head fallback tiers; always fetches remote first.
- Added a **scope-drift** pass (code → requirement): every changed hunk must trace to a requirement or is flagged HIGH/MEDIUM "justify or revert". Flags for author judgment; never blocks merge.
- Enriched requirements with **design-doc context** harvested via the repo `AGENTS.md` design-doc root and `.docs/ado-context.md`, as elaboration of the AC (not new binding criteria).
- Added `prepare_worktree_deps.py`: junctions unchanged-dependency `node_modules` into fresh worktrees (no implicit install) or signals `JS-SKIPPED` when deps changed; teardown removes only the junction so the source `node_modules` is never deleted.
- Sidecar v2 gains additive fields `prOnlyMode`, `prMergePreview`, `mergePreviewStrategy`, `jsDepsStrategy`; verifier and tests assert them.

### 2026-06-24 - Branch work item gate

- Added Branch Work Item Gate as a first gate using the Build Validator runtime.
- Validates `US/`, `BUG/`, and `ISSUE/` branch IDs against Azure DevOps work item existence and type through `az`.
- Added report, sidecar, verifier, and eval coverage for PASS/FAIL/SKIPPED gate status.

### 2026-06-19 - v2.0.0 adaptive review pipeline

- Added Docs-only, Tiny, and Pro classifier with strict Tiny thresholds and risk exclusions.
- Replaced fixed specialist fan-out with Pro-only, risk-triggered specialists.
- Made Requirement Validator mandatory for Pro; added regression-only mode when no work item exists.
- Added exact cross-tool runtime routing; Codex uses Build `gpt-5.4-mini/low`, Requirement inherited/high, and specialists inherited/medium.
- Added profile/trigger announcements, exact report provenance fields, v2 sidecar schema, and same-classifier follow-ups.
- Moved worktrees repo-local and added Build Validator child-read preflight.
- Strengthened base/new behavior, caller/consumer/event/state/test evidence and severity rules.
- Added Tiny, Pro, and PR 75635 evals plus deterministic output verification tests.
- Reduced `SKILL.md` and `report-template.md` below validation limits.

### 2026-06-11 - Token optimization and incremental follow-up mode

- Wrote the diff once and passed paths to self-loading agents.
- Added follow-up metadata, stable Must Fix slugs, and delta-only re-review.

### 2026-04-24 - Quick Mode moved to code-review-lite

- Routed explicit quick/lite review requests to the dedicated lightweight skill.

### 2026-04-23 - By-file report organization

- Grouped detailed findings by file with inline severity tags and a Must Fix shortlist.

### 2026-04-22 - Gate-driven redesign

- Added build validation, worktree isolation, and requirement/performance/security/design/standard lenses.
