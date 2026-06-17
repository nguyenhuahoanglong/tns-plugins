# Code Review Lite

## Purpose

Lightweight parallel code review skill optimized for repeated low-cost reviews. Dispatches 2 sonnet reviewers (Critical + Quality) and N haiku build validators (1 per detected project type) in parallel, synthesizes inline without opus, and writes the result to `.CodeReview/{Branch}.lite.md`. Designed for repeated use within a single quota window — pre-merge sanity checks, quick review cycles, and multi-project (BE+FE) reviews that would burn too much quota on the full 6-agent pipeline.

## Pain Points

- **Quota burn from full pipeline** — the original `code-review-pro` skill dispatches 6 sub-agents (2 opus inline + 4 sonnet + 1 haiku) per review. On a constrained quota window this can consume most of the budget in a single review.
- **Deep reasoning is expensive for routine checks** — the Approach Gate and synthesis in the full skill use opus inline. Most pre-merge checks don't need that depth.
- **Quick mode rehomed** — "quick review" / "quick code review" triggers previously routed to the original skill's Quick Mode. That mode has been removed from `code-review-pro` and is now served entirely by this skill.
- **Multi-project reviews (BE+FE) still needed** — lite preserves the N-parallel-haiku build pattern so a .NET + React repo pair still gets a build gate per project type.
- **Lightweight ADO integration** — lite now auto-detects and fetches the linked user story via the bundled `scripts/ado_work_item.py` (az CLI), non-blocking — failure or skip never stops a review. Full work item confirmation and a dedicated requirement validator agent remain in `code-review-pro`.

## Design Notes

### 2-reviewer architecture

Two sonnet sub-agents run in parallel after the build gate passes:
- **Critical Reviewer** — security (OWASP Top 10, input tracing, secrets) + correctness (gap analysis against any user-provided requirement text; skipped if none provided)
- **Quality Reviewer** — 3 lenses merged into one agent: performance (algorithmic/DB/async checks), philosophy (SOLID/DRY/KISS/YAGNI), and convention (project AGENTS.md / .editorconfig / linter configs)

### N fast builds, no cap

One haiku build-validator sub-agent per detected project type (`.csproj`/`.sln` for .NET, `package.json` with `build` script for Node/React). Fast validation is cheap enough that there is no reason to limit. Any `FAIL` → short Build Fail report + cleanup + STOP.

### No deep reasoning

Synthesis is done inline by the orchestrator. Deduplication, severity tagging, and report writing don't require deep reasoning — they're mechanical. opus is intentionally excluded to stay within quota.

### Worktree clean-state rule

Create worktree IFF (target branch ≠ HEAD) OR (working tree dirty) OR (staged changes present). If HEAD is already the target and the tree is clean, review in place. Cleanup runs unconditionally in Phase 5.

### Report path: `.lite.md`

Lite writes to `.CodeReview/{BranchName}.lite.md` to avoid overwriting a prior full review report at `.CodeReview/{BranchName}.md`. Both files can coexist in the same directory.

## Changelog

### 2026-05-03 — Pattern consistency added to Quality Reviewer

- Added Phase 1 Neighbor Discovery step (Glob 2-3 exemplars per changed file)
- Quality Reviewer Lens 3 now reads exemplars and flags divergence from dominant codebase patterns
- Severity: divergence from >=3-neighbor dominant pattern -> HIGH
- No new agent — keeps the 2-reviewer Pro-quota budget

### 2026-04-24 — Initial creation

- Created `code-review-lite` as the lightweight sibling of `code-review-pro` (then named `code-review`; renamed 2026-05-21)
- Rehomed "quick review" / "quick code review" trigger from original `code-review-pro` (Quick Mode removed there)
- 2-sonnet reviewer design (Critical + Quality with 3 merged lenses) replaces 5-agent deep dive
- N-haiku build gate preserved; opus removed; synthesis inline
- `.lite.md` report path avoids collision with full review reports
