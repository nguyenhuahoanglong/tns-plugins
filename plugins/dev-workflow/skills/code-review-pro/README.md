# Code Review

## Purpose

Multi-agent parallel code review for Azure DevOps PRs and local branches. Combines a fail-fast gate phase (architectural sanity + build) with a priority-weighted deep dive across requirement, performance, security, philosophy, and convention concerns. Runs across multiple repos via git worktrees so the user's working tree is never disturbed.

## Pain Points

- **Wasted deep-dive tokens on broken PRs** — running 6 review agents on code that doesn't compile or has wrong architecture is pure waste
- **No early signal on architectural mistakes** — wrong-layer logic surfaces only after every agent has finished
- **Slow reviews when only a sanity check is needed** — full pipeline for every PR even pre-merge gut-checks
- **Multi-repo PRs not supported** — paired BE/FE repos need separate reviews
- **In-place checkout disrupts user's working tree** — review steps clobber pending work and force checkout/restore dance

## Design Notes

### Gate-driven funnel

Phase 2 runs Approach Assessment (orchestrator inline, opus) in parallel with Build Validator (haiku). If either fails, write a short report and stop — no deep dive. The Approach Gate has a strict 4-criteria REJECT bar (`references/approach-gate.md`) to prevent false-positive rejections; when in doubt → PASS, surface concerns as P1 findings.

### Worktree isolation

Replaces the old in-place checkout. Each reviewed repo gets its own `../{repo}-review-{branch}/` worktree. User's working tree is never touched; multi-repo reviews are clean. Cleanup runs unconditionally in Phase 5 — even on REJECT, build fail, or mid-deep-dive errors.

### ADO work-item retrieval

Self-contained via the bundled `scripts/ado_work_item.py` (az CLI based) — no personal global functions required. Detects the work item from PR-linked items, branch name, or commit messages; fetches the item and its parent; strips ADO HTML; returns prompt-ready markdown. Requires Azure CLI (`az login` or `AZURE_DEVOPS_EXT_PAT`).

### Priority-weighted synthesis

Sub-agents use sonnet for broad review while the orchestrator uses opus for gate + synthesis work. Synthesis verifies findings with effort scaled by tier (P1 Requirement → P5 Convention) — most rigor on P1, light pass on P5. See `references/analysis-framework.md`.

## Changelog

### 2026-06-11 - Token optimization + incremental follow-up mode

- **Diff-to-file**: full diff written once to `.CodeReview/.{branch}.diff`; dispatch prompts pass the path, never the content (was: full diff pasted into 4-5 agent prompts as orchestrator output)
- **Self-loading agent prompts**: agents read their own `references/agents/*.md` from the skill dir; orchestrator no longer reads/re-emits them. Standards + exemplars passed as paths, not captured content
- **Reference dedupe**: `analysis-framework.md` trimmed to orchestrator-only content (priority levels, P1-P5 tiers, effort scaling, action classification); SKILL.md Phase 4 defers synthesis mechanics to `report-template.md` §Synthesis Guidelines
- **Leaner agent output contracts**: Clean Files lists → single count line; mandatory one-line format for MEDIUM/LOW findings; Notes capped at 3 sentences; Philosophy table notes only on Warn
- **Follow-up mode (new)**: `references/followup-review.md` + `references/agents/delta-reviewer.md`. Re-review of an already-reviewed branch reuses a meta sidecar (`.CodeReview/.{branch}.review-meta.json` — reviewedCommit, workItemId, standardsPaths, exemplarMap, reviewedFiles, iteration), diffs only `{reviewedCommit}..HEAD`, and runs 2 agents (Build + Delta Reviewer) instead of 6. Escalates to the full 5-agent fan-out when delta >400 lines or touches files outside the original review. Regenerates the full report with stable `[mf:slug]` tags — `code-review-publish` iteration diffing unaffected
- Report header gains `Reviewed Commit` + `Iteration` lines

### 2026-04-24 - Quick Mode removed (rehomed to code-review-lite)

- Dropped Quick Mode from decision tree, Phase 2 decision, and standalone section in SKILL.md
- Removed Quick Pass Report variant from short-reports.md
- Users seeking quick sanity checks should invoke `code-review-lite` skill instead

### 2026-04-23 - By-file report organization

- Restructured final report: Detailed Findings grouped by file, not by severity; severity becomes an inline `[CRITICAL]`/`[HIGH]` tag
- Fix 1: `SKILL.md` Phase 4 now opens with explicit `Read references/report-template.md` instruction (U-curve high-attention position); prior "merge findings into template" phrasing read as a pointer and the template was never loaded — session trace on US-1909 review confirmed
- Fix 2 (Ship 2): Flipping 5 deep-dive agent prompts (Requirement, Performance, Security, Philosophy, Convention) from severity-first sections to per-file sections with inline severity tags; Build Validator unchanged (already file-grouped within project scope)
- Added `Must Fix Before Merge` bulleted shortlist at top of report (file:line refs, capped ~10) to preserve "what blocks merge?" at-a-glance view
- Removed 3-tier Action Items block (Must Fix / Should Fix / Consider) — duplicated Detailed Findings and was the internal contradiction that biased the orchestrator toward severity organization

### 2026-05-03 — Codebase pattern consistency check

- Renamed Convention Checker -> Standard Reviewer; moved standard review to sonnet
- Added Pattern Consistency lens reading neighbor exemplars (sibling files, same suffix, same feature folder)
- Added Phase 1 Neighbor Discovery step (Glob 2-3 exemplars per changed file, cap 3)
- Promoted standards-discovery §3 from fallback to mandatory step
- Severity: divergence from >=3-neighbor dominant pattern -> HIGH (was capped MEDIUM)

### 2026-04-22 - Gate-driven redesign with worktree isolation

- Added Phase 2 Quick Gate: Approach Assessment (orchestrator opus inline) + Build Validator (haiku) running in parallel; either fails → short report → stop
- Added quick mode triggered by "quick review" / "quick code review" phrase
- Replaced in-place git checkout with `git worktree add` per repo (multi-repo support, preserves user's working tree)
- Moved Requirement Validator and Performance Reviewer to sonnet; orchestrator now does opus reasoning at gates and synthesis instead
- Added priority-tier synthesis (P1 Requirement → P5 Convention) with effort scaling (verification depth, fix-suggestion quality, cross-checking)
- New references: `approach-gate.md`, `short-reports.md`
- Trimmed `requirement-validation.md` to orchestrator-side scope; deleted the old Phase 4 that duplicated the agent prompt
- Updated `report-template.md` to reflect new model lineup and approach pre-findings; added cross-ref to short-reports
