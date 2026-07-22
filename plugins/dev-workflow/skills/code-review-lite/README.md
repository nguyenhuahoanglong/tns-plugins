# Code Review Lite

## Purpose

Adaptive, low-cost production-code review for quick checks and pre-merge validation. Version 4.1.1
attests the host runtime/session before repository reads, partitions production from evidence-only
and excluded files, verifies tests deterministically, and supports controlled multi-specialist
escalation to Pro.

## Pain Points

- Model children waste tokens when used for deterministic branch/build execution.
- File/line size alone misses small but risky API, auth, schema, state, dependency, async, and configuration changes.
- Inline diffs and inherited conversation history bloat semantic-child context.
- Mixed gate/agent reporting obscures what used model tokens and whether cache counters were exposed.
- Remote sibling worktrees are difficult for child agents to discover reliably.
- Requirement findings become speculative without reverse behavior and collateral-impact evidence.
- Displayed model labels can drift from the actual host runtime unless evidence is attested.
- Tests/docs are valuable evidence but must not become defect targets or inflate production scope.
- A single overwritten test result hides failures in multi-run or multi-repository reviews.

## Profiles

| Profile | Pipeline |
|---|---|
| No Production Code | Retain report, record-v3 sidecar, and runtime/scope/not-applicable test evidence; execute no review work |
| Code Tiny | Deterministic branch/build/test gates; main code review; zero semantic children |
| Lite | Deterministic gates; mandatory deep Requirement Validator plus at most one specialist |
| Pro escalation | More than one family with explicit-user `auto`, or an accepted `ask`, routes to `code-review-pro`; write no Lite report or sidecar |
| Bounded Lite | A declined `ask` runs gates, Requirement Validator, and at most one priority specialist when gates pass |

Tiny means at most 3 files and 100 changed lines, with no elevated shared behavior, API, schema, auth, dependency, async/lifecycle, state, or configuration risk.

## Escalation policy and decision table

Invocation accepts `Escalation Policy: auto|ask`; omission defaults to `ask`, so multiple families
pause for user consent. Only explicit user-authored `auto` invokes Pro immediately. With `ask`, explain each triggered family and why Pro is
recommended before asking. Acceptance follows Pro-only routing; decline continues bounded Lite.

| Triggered families | Policy / response | Outcome | Lite fields |
|---|---|---|---|
| 0 or 1 | `auto` or `ask` | Lite | `not-needed`; selected `{Family} Reviewer` or `None`; unreviewed `None` |
| 2+ | explicit-user `auto`, or `ask` accepted | Pro | no Lite artifact |
| 2+ | `ask` declined; gates pass | Bounded Lite | `pro-declined`; select Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard Reviewer; other families unreviewed |
| 2+ | `ask` declined; branch FAIL | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |
| 2+ | `ask` declined; build/test fail, timeout, or gap | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |

Lite reports use `Escalation Policy`, `Escalation Policy Provenance`, `Escalation Decision`, `Selected Specialist`, and
`Unreviewed Risk Families`; the record-v3 sidecar mirrors them as `escalationPolicy`, `escalationPolicyProvenance`,
`escalationDecision`, `selectedSpecialist`, and `unreviewedRiskFamilies`. A passing bounded Lite
selects exactly one persisted specialist value by Security Reviewer > Philosophy Reviewer >
Performance Reviewer > Standard Reviewer. For every Lite route, branch FAIL selects `None` and
starts no semantic agents; build/test failures, timeouts, and gaps select `None`, run Requirement
Validator only, and leave every triggered family unreviewed. Residual families are reported by the
main workflow as unreviewed, never injected into the selected role.

`Selected Specialist` and sidecar `selectedSpecialist` accept only `Security Reviewer`,
`Philosophy Reviewer`, `Performance Reviewer`, `Standard Reviewer`, or `None`.

## Runtime routing

Shared runtime/session preflight runs before repository reads and is re-evaluated against the
packaged runtime policy during report verification. Branch, build, and test gates are local
deterministic scripts and have no model runtime. Semantic agent
metadata owns cross-tool routing: Requirement Validator uses `deep` (Claude Opus; Codex Sol/high),
and named specialists use `standard` (Claude Sonnet; Codex Terra/medium). Lite launches fresh,
isolated children from a compact context manifest; reports keep known runtime fields and use
`not exposed` only for unavailable provider token/cache counters.

## Output

Reports remain at `.CodeReview/{safe-branch}.lite.md`; metadata is
`.CodeReview/.{safe-branch}.lite.review-meta.json`. They retain hash-bound runtime, scope, and test
artifacts; separate deterministic gates from semantic agents; include behavior/collateral/scope
drift evidence; and record per-child context mode plus token/cache counters.

Production findings may target only `productionFiles`; tests/docs may still be cited as evidence.
Test evidence aggregates every repo/command under `executions[]`. Missing direct tests for changed
symbols emits exact `use-unit-testing` without suppressing a selected specialist. Blocking branch
outcomes route no semantic agents; blocking build or test outcomes route only the Requirement
Validator. In either case, `Selected Specialist` is `None` and every triggered family is unreviewed.

## Changelog

### 2026-07-22 - v4.1.1 consent-first escalation

- Omitted escalation policy now means `ask`; only explicit user-authored `auto` may escalate immediately.
- Added escalation-policy provenance to reports and record-v3 sidecars.

### 2026-07-21 - v4.1.0 explicit multi-family escalation policy

- Added `Escalation Policy: auto|ask`, defaulting to `auto` for unchanged immediate-Pro behavior.
- Added ask/accept Pro-only routing and ask/decline bounded Lite routing with deterministic
  Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard Reviewer selection
  and residual-family reporting.
- Added report and record-v3 sidecar fields for the policy, decision, selected specialist, and
  unreviewed risk families; Pro paths continue to write no Lite artifacts.

### 2026-07-21 - v4.0.0 attested runtime and production scope

- Added mandatory shared runtime/session clearance before repository reads; blocked runtimes stop and existing sessions require a recorded override.
- Restricted findings to persistent production allowlists; docs/tests are evidence-only and evidence-only diffs return `No Production Code`.
- Added deterministic direct/affected test evidence, exact `use-unit-testing` advisory, and Requirement-Validator-only routing for test failures/gaps.
- Added record-v3 hash-verified Lite sidecars and v4 verifier enforcement while retaining Lite escalation and isolated children.

### 2026-07-13 - v3.0.0 deterministic gates and isolated semantic review

- Replaced Lite's model Build Validator with deterministic `build_gate.py` while preserving dependency preparation and `JS-SKIPPED` handling.
- Made Docs Tiny and Code Tiny zero-semantic-child profiles; Lite always runs the deep Requirement Validator and runs at most one specialist, concurrently after passing builds.
- Added the compact review-context manifest, isolated dispatch placeholders, separate gate/agent reporting, numeric-or-`not exposed` usage counters, and behavior-preservation/collateral-impact evidence.
- Kept branch-failure stop behavior and multi-specialist escalation to `code-review-pro` unchanged.

### 2026-07-11 - GPT-5.6 intent routing

- Documented portable fast/standard/deep routing for Build, Requirement, and specialist reviewers.
- Refreshed verifier help and representative fixtures to Luna/Terra/Sol without changing report semantics.

### 2026-07-09 - v2.2.0 lockfile-gated worktree installs

- `prepare_worktree_deps.py` now performs a frozen, lockfile-gated install (`npm ci` / `yarn install --frozen-lockfile` / `pnpm install --frozen-lockfile`) in the worktree when the source repo's `node_modules` is missing or stale; opt out with `--no-install`.
- Added `--require-bin {tool}` (repeatable): a build-tool-aware source-deps health check. A production-only source `node_modules` (populated `.bin` but missing the build tool, e.g. `vite` as a devDependency) is now judged unusable and re-installed instead of junctioning a broken tree that fails with "vite is not recognized". The workflow passes the tool the approved build command invokes.
- Fixed `branch_work_item_gate.py`: dropped the `--fields` argument to `az boards work-item show` (rejected by newer az-devops with "expand parameter can not be used with the fields parameter"), reading work-item type/title/state from the returned `fields` object — this was producing a false gate FAIL on every review.
- Extended `JS-SKIPPED` reasons to `deps changed`, `no lockfile`, and `install failed`; the Build Validator is never dispatched against a project whose JS deps could not be made usable.
- Added `NOT RUN (environment)` build status for a missing build tool, so an environment gap is never reported as a build FAIL.
- Capped Build Validator error/warning listings at 10 each, with `(+N more)` totals beyond that.

### 2026-07-07 - v2.1.2 branch gate warning mode

- Added `WARN` branch gate status for non-standard or mismatched branch prefixes when the ADO work item ID exists and has an allowed type.
- Kept `FAIL` for missing/unresolvable IDs and ADO work item types outside `User Story`, `Bug`, or `Issue`.

### 2026-07-06 - v2.1.1 optional branch slug

- Relaxed Branch Work Item Gate branch parsing so `US/{id}`, `BUG/{id}`, and `ISSUE/{id}` pass without a slug.
- Preserved optional `-{slug}` support and strict Azure DevOps work item type validation.

### 2026-06-29 - v2.1.0 PR-centric review and scope discipline

- Added enforced **PR-only mode**: "review PR {id}" requires a resolvable PR (gated by `ado_work_item.py pr-required`) and errors instead of falling back to other scopes.
- PR scope reviews the **merge preview** (source merged into target) via `ado_work_item.py merge-preview`, with server-merge → local-merge → source-head fallback.
- Added a **scope-drift** block (code → requirement): changes that trace to no requirement are flagged HIGH/MEDIUM "justify or revert"; advisory only, never blocks.
- Enriched requirements with **design-doc context** harvested via the repo `AGENTS.md` design-doc root.
- Added `prepare_worktree_deps.py`: junctions unchanged `node_modules` into worktrees (no install) or marks `JS-SKIPPED`; teardown removes only the junction.
- Report header gains `PR-Only` and `Merge Preview` fields; build status accepts `JS-SKIPPED`.

### 2026-06-24 - Branch work item gate

- Added Branch Work Item Gate as a first gate using the Build Validator runtime.
- Validates `US/`, `BUG/`, and `ISSUE/` branch IDs against Azure DevOps work item existence and type through `az`.
- Added Lite report, verifier, and eval coverage for PASS/FAIL/SKIPPED gate status.

### 2026-06-19 - v2.0.0 adaptive classifier and visible runtime

- Added strict Tiny eligibility: `<=3` files, `<=100` changed lines, and no elevated risk category.
- Added zero-agent Docs Tiny and main-agent Code Tiny profiles.
- Replaced fixed Critical/Quality reviewers with a dedicated Requirement Validator and at most one named risk-triggered specialist.
- Added automatic escalation to `code-review-pro` when multiple specialist families trigger.
- Defined exact child runtime profiles and required trigger/skip visibility in reports.
- Moved worktrees under `.CodeReview/.worktrees/` and added child-read preflight.
- Added concise requirement evidence rules, deterministic output verification, tests, and four profile/escalation evals.
- Preserved `.lite.md` reports and ADO autolink safety.

### 2026-05-03 - Pattern consistency

- Added neighbor discovery and convention comparison to the prior fixed Quality Reviewer pipeline.

### 2026-04-24 - Initial creation

- Created the low-cost sibling of `code-review-pro`.
- Preserved parallel build gates and `.lite.md` report isolation.
