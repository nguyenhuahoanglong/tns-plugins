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

Phase 2 runs Approach Assessment (orchestrator inline, {{effort.deep}}) in parallel with Build Validator ({{effort.fast}}). If either fails, write a short report and stop — no deep dive. The Approach Gate has a strict 4-criteria REJECT bar (`references/approach-gate.md`) to prevent false-positive rejections; when in doubt → PASS, surface concerns as P1 findings.

### Worktree isolation

Replaces the old in-place checkout. Each reviewed repo gets its own `../{repo}-review-{branch}/` worktree. User's working tree is never touched; multi-repo reviews are clean. Cleanup runs unconditionally in Phase 5 — even on REJECT, build fail, or mid-deep-dive errors.

### Priority-weighted synthesis

Sub-agents use {{effort.standard}} for broad review while the orchestrator uses {{effort.deep}} for gate + synthesis work. Synthesis verifies findings with effort scaled by tier (P1 Requirement → P5 Convention) — most rigor on P1, light pass on P5. See `references/analysis-framework.md`.

## Changelog

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

- Renamed Convention Checker -> Standard Reviewer; moved standard review to {{effort.standard}}
- Added Pattern Consistency lens reading neighbor exemplars (sibling files, same suffix, same feature folder)
- Added Phase 1 Neighbor Discovery step (Glob 2-3 exemplars per changed file, cap 3)
- Promoted standards-discovery §3 from fallback to mandatory step
- Severity: divergence from >=3-neighbor dominant pattern -> HIGH (was capped MEDIUM)

### 2026-04-22 - Gate-driven redesign with worktree isolation

- Added Phase 2 Quick Gate: Approach Assessment (orchestrator {{effort.deep}} inline) + Build Validator ({{effort.fast}}) running in parallel; either fails → short report → stop
- Added quick mode triggered by "quick review" / "quick code review" phrase
- Replaced in-place git checkout with `git worktree add` per repo (multi-repo support, preserves user's working tree)
- Moved Requirement Validator and Performance Reviewer to {{effort.standard}}; orchestrator now does {{effort.deep}} reasoning at gates and synthesis instead
- Added priority-tier synthesis (P1 Requirement → P5 Convention) with effort scaling (verification depth, fix-suggestion quality, cross-checking)
- New references: `approach-gate.md`, `short-reports.md`
- Trimmed `requirement-validation.md` to orchestrator-side scope; deleted the old Phase 4 that duplicated the agent prompt
- Updated `report-template.md` to reflect new model lineup and approach pre-findings; added cross-ref to short-reports
