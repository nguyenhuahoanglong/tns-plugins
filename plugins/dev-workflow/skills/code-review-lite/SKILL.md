---
name: code-review-lite
description: "Lightweight parallel code review: N fast build gates + 2 standard reviewers (critical + quality). Use for quick review, lite review, pre-merge sanity checks."
---

# Code Review Lite

## Decision Tree

```
SITUATION?
|
+-- "Quick review" / "lite review" / "pre-merge sanity check"
|   -> This skill: Phases 0-5 below
|
+-- Full review with ADO work items, requirement validation
|   -> Use original `code-review-pro` skill instead
|
+-- Received code review feedback
|   -> Feedback reception protocol in `references/feedback-reception.md`
|
+-- Need others to review my work
    -> Requesting review protocol in `references/requesting-review.md`
```

## Agent Pipeline

| Phase | Actor | Model |
|-------|-------|-------|
| 0. Scope Clarify | Orchestrator inline | — |
| 1. Gather | Orchestrator inline | — |
| 2. Build Gate | N sub-agents (1 per project type) | {{effort.fast}} |
| 3. Review | 2 sub-agents (parallel) | {{effort.standard}} |
| 4. Synthesize | Orchestrator inline | — |
| 5. Cleanup | Orchestrator inline | — |

## Phase 0: Scope Clarify

If scope is explicit (branch name, PR ID, file list, "staged changes"), skip to Phase 1.

If scope is vague, ask at most 2 questions:
1. "What branch or files should I review? (or 'staged changes' to review what's staged)"
2. "Any specific requirement text to validate against? (optional — skip to focus on security/quality only)"

## Phase 1: Gather

Run all steps in parallel:
- **Scope** — PR metadata, target branch, or staged diff (`references/workflow.md` §1)
- **Diff** — full diff with context (`references/workflow.md` §2)
- **Project types** — detect `.csproj`/`.sln` for .NET; `package.json` with `build` for Node/React
- **Standards** — discover {{standards.discoveryFiles}}; capture for Quality Reviewer
- **Neighbors** — use {{tool.fileSearch}} to find 2–3 exemplars per changed file (same folder, same suffix e.g. `*Service.cs` / `*Handler.ts` / `*.test.tsx`, same feature folder); cap 3 per file; skip if no siblings exist (`references/workflow.md` §1.5). Output: `{changed_file: [exemplar_paths]}` map.
- **Worktree** — create IFF (target branch ≠ HEAD) OR (working tree dirty) OR (staged changes present); full recipe in `references/workflow.md` §3

## Phase 2: Build Gate

MUST spawn one {{effort.fast}} `build-validator` sub-agent per detected project type. No cap on count. Run all in parallel.

```
{{agent.spawn.codeReviewer}}
Prompt content: [references/agents/build-validator.md content]
Project path: {path}
Worktree: {WORKTREE_PATH}
Description: Build: {ProjectName}
```

**Decision after all build agents return:**
- Any `Gate Result: FAIL` → write Build Fail report (`references/workflow.md` — Build Fail Short Report) → Phase 5 → STOP
- All `Gate Result: PASS` → continue to Phase 3

**NEVER proceed to Phase 3 on a build failure.**

## Phase 3: Review

MUST spawn exactly 2 {{effort.standard}} sub-agents in a single message for true parallelism:

**Critical Reviewer** (`references/agents/critical-reviewer.md`):
- Inject: full diff, changed file list, requirement text (if provided in Phase 0, else omit)

**Quality Reviewer** (`references/agents/quality-reviewer.md`):
- Inject: full diff, project type, discovered standards content, **exemplar paths + excerpts (from Neighbor Discovery)**

Both agents work from the worktree path. They do not run git commands.

## Phase 4: Synthesize (Inline)

Read `references/report-template.md` before writing. Then:

1. Deduplicate: same `file:line` from both agents → one entry, multi-tag, highest severity wins
2. Build errors → CRITICAL; build warnings → MEDIUM
3. Write Must Fix shortlist (Critical + High only, severity-sorted, capped ~10)
4. Organize Detailed Findings by file (never by severity)
5. Write report to `.CodeReview/{BranchName}.lite.md` — **never** `.CodeReview/{BranchName}.md`
6. Run the ADO autolink guard from the `code-review-publish` skill:

```bash
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{BranchName}.lite.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{BranchName}.lite.md"
```

Do not declare the review complete until the guard passes. Raw `#123` is allowed only for intentional work-item links.

## Phase 5: Cleanup

**Run unconditionally** — even on build fail or mid-review errors. Recipe in `references/workflow.md` §4.

---

## Enforcement

**NEVER run review lenses yourself — DELEGATE all review work to sub-agents.**
If delegation calls = 0 at the end of Phase 3, the workflow is INCOMPLETE.

**NEVER use {{effort.deep}} in any phase.** Lite is designed for fast quota budgets — deep-effort orchestration is excluded by design.

**NEVER write to `.CodeReview/{BranchName}.md`** — always use `.CodeReview/{BranchName}.lite.md` to avoid overwriting full review reports.

**DO NOT duplicate** feedback-reception or requesting-review protocols here — those live in the original `code-review-pro` skill references.
