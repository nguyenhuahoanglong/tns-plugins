# Code Review Pro

## Purpose

Adaptive evidence-driven production-code review for PRs, branches, staged changes, and follow-up iterations. Version 3.0.2 attests runtime/session evidence advisorily (never blocking), classifies No-production-code, Tiny, or Pro scope, and binds reports to deterministic artifacts.

## Pain Points

- Fixed fan-out spends specialist agents on low-risk diffs.
- File/line size alone can misclassify small but dangerous API, schema, auth, dependency, lifecycle, state, or configuration changes.
- Requirement review disappears when no work item exists, leaving regressions and unrelated behavior unchecked.
- External worktrees and unreadable child paths cause brittle agent runs.
- Reports lack machine-verifiable skill, runtime, trigger, skip, and profile provenance.
- Lite escalation must never become a Pro run without recorded user consent.
- Follow-ups can use different review rules from initial reviews and lose reproducibility.

## Design Notes

### Adaptive profiles

- No-production-code: terminal evidence-only outcome; no worktree, build/test, semantic agents, or findings.
- Tiny: at most 3 files and 100 changed lines with no risk triggers; one Build Validator per repo, then main-agent all-lens review.
- Pro: Build Validator per repo, Requirement Validator always, and only risk-triggered specialists.

### Requirement contract

Direct task/acceptance criteria are binding. Parent items supply context but do not broaden scope. Without a work item, Requirement Validator switches to regression-only mode and compares base versus new behavior across symbols, callers, consumers, events, state, tests, and unrelated behavior.

### Isolation and provenance

Worktrees live under each repo at `.CodeReview/.worktrees/{safe-branch}`. Build children perform a read preflight before other children run. Reports carry exact skill/runtime/profile/actor provenance. Only record version 3 is valid: the sidecar hash-binds runtime, scope, and test artifacts and retains branch, PR, dependency, repository, and follow-up provenance.

### Runtime routing

Agent metadata owns cross-tool model selection. Build Validator uses the `fast` intent (Claude
Haiku; Codex Luna/low), Requirement Validator uses `deep` (Claude Opus; Codex Sol/high), and named
specialists use `standard` (Claude Sonnet; Codex Terra/medium). Reports and sidecars record the
actual launch runtime for the main agent instead of assuming one.

## Changelog

### 2026-07-22 - v3.0.2 advisory runtime preflight

- Runtime preflight is now advisory and never hard-blocks: unverifiable or below-recommended runtime records a `trustLevel` (`verified|self-reported|unknown`) and reminds the user to switch to a recommended model + high thinking, then continues. Fixes hard-stops under GitHub Copilot VS Code and Claude CLI without a status line.
- Capability is enforced by tier (sonnet+), not raw generation, so flagship Claude Opus 4.8 is no longer rejected (`claude.minimumGeneration` `[5]`→`[4]`).
- Reports/sidecars carry `trustLevel`; self-report is accepted only as labeled, untrusted metadata.

### 2026-07-22 - v3.0.1 Lite escalation provenance

- Added direct-user versus Lite-escalation invocation provenance to reports and record-v3 sidecars.
- Reject Lite-originated Pro artifacts without `user-confirmed` or explicit-user `auto` consent.

### 2026-07-21 - v3 runtime, scope, and test evidence

- Require shared runtime/session preflight before repository reads; existing sessions need an explicit recorded override.
- Restrict semantic review and findings to manifest `productionFiles`; tests/docs are evidence-only and generated/vendor/binary paths are excluded.
- Persist deterministic test discovery/execution and the exact `use-unit-testing` advisory for missing direct tests.
- Require `executions[]` for multi-repo runs; failed/timeout runs remain valid blocking evidence only when their status, exit code, counts, report, and `testGate` agree.
- Upgrade reports/sidecars and verifier to strict v3-only hash-bound artifacts while retaining branch, classifier, actor, PR, dependency, and follow-up guards.

### 2026-07-11 - GPT-5.6 intent routing

- Documented portable fast/standard/deep routing for Build, Requirement, and specialist reviewers.
- Refreshed active follow-up examples, verifier help, and representative fixtures to Luna/Terra/Sol.
- Preserved v2 report and sidecar semantics plus historical runtime entries.

### 2026-07-09 - v2.2.0 deps auto-install and token optimization

- `prepare_worktree_deps.py` now performs a frozen, lockfile-gated install (`npm ci` / `yarn install --frozen-lockfile` / `pnpm install --frozen-lockfile`) inside the worktree when source `node_modules` is missing or unusable and a lockfile exists; junctioning remains the default when source deps are usable. New `--install-timeout` (default 480s) and `--no-install` flags.
- `jsDepsStrategy` roll-up gains `install`; failed installs report `install-failed` (surfaced, not fatal).
- Added `--require-bin {tool}` (repeatable): a build-tool-aware source-deps health check. A production-only source `node_modules` (populated `.bin` but missing the build tool, e.g. `vite` as a devDependency) is judged unusable and re-installed rather than junctioning a broken tree that fails with "vite is not recognized". Checked uniformly against each project's `.bin` (bin names don't reliably map to package names — `tsc` ships from `typescript` — so a declared-dependency filter would be unsound). The workflow passes the tool the approved build command invokes.
- Fixed `branch_work_item_gate.py`: dropped the `--fields` argument to `az boards work-item show` (rejected by newer az-devops with "expand parameter can not be used with the fields parameter"), reading work-item type/title/state from the returned `fields` object — this was producing a false gate FAIL on every review.
- Fixed a false build FAIL: a project whose deps could not be made usable (`skip-build` or `install-failed`) is reported `JS-SKIPPED ({reason})`, and the Build Validator is never dispatched with that project's JS build command — an environment gap is never reported as a code failure.
- Build Validator reports `NOT RUN (environment)` when the approved build command's own tool is missing (e.g. absent from `node_modules/.bin`), and caps Errors/Warnings output at 10 verbatim entries plus `(+N more)`.
- Token optimization (Balanced tier): full-context diff narrowed from `-U50` to `-U20` (children read full files from the worktree when a hunk needs more context); added `references/agents/_shared-contract.md` holding the preflight and finding-output contract shared by Requirement Validator and the four specialists, trimming each role prompt to its lens-specific content; Synthesize re-verifies only Critical/High findings, accepting Medium/Low on cited evidence; standards exemplar discovery moved from 2-3 per changed file to 2-3 per repo/stack.

### 2026-07-07 - v2.1.2 branch gate warning mode

- Added `WARN` branch gate status for non-standard or mismatched branch prefixes when the ADO work item ID exists and has an allowed type.
- Kept `FAIL` for missing/unresolvable IDs and ADO work item types outside `User Story`, `Bug`, or `Issue`.

### 2026-07-06 - v2.1.1 optional branch slug

- Relaxed Branch Work Item Gate branch parsing so `US/{id}`, `BUG/{id}`, and `ISSUE/{id}` pass without a slug.
- Preserved optional `-{slug}` support and strict Azure DevOps work item type validation.

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
