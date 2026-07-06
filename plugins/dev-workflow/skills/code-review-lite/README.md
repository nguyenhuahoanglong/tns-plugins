# Code Review Lite

## Purpose

Adaptive, low-cost code review for quick checks and pre-merge validation. Version 2 classifies changes before dispatch, keeps truly small work local, and escalates changes whose risk needs multiple specialists.

## Pain Points

- Fixed reviewer counts waste runtime on documentation and tiny changes.
- File/line size alone misses small but risky API, auth, schema, state, dependency, async, and configuration changes.
- Hidden runtime substitutions make review cost and depth hard to audit.
- Remote sibling worktrees are difficult for child agents to discover reliably.
- Requirement findings become speculative when evidence rules are vague.

## Profiles

| Profile | Pipeline |
|---|---|
| Docs Tiny | Main-agent documentation review; zero child agents |
| Code Tiny | Build Validator per repo; main-agent code review |
| Lite | Build Validator per repo, Requirement Validator, then at most one named specialist |
| Escalation | More than one specialist trigger routes to `code-review-pro` |

Tiny means at most 3 files and 100 changed lines, with no elevated shared behavior, API, schema, auth, dependency, async/lifecycle, state, or configuration risk.

## Output

Reports remain at `.CodeReview/{safe-branch}.lite.md`. Each report records combined skill/version provenance, selected profile, main runtime, triggered/skipped actors, reasons, and child runtime profiles.

Worktrees remain repo-local at `.CodeReview/.worktrees/{safe-branch}`. Every child must pass a read-token preflight before review work starts.

## Changelog

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
