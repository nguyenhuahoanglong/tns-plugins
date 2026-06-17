---
name: code-review-pro
description: "Multi-agent parallel code review pipeline with fail-fast gates (approach + build). Use for PR/branch reviews or receiving review feedback. For quick sanity checks, use code-review-lite. (Renamed from code-review to avoid collision with built-in /code-review in Claude Code 2.1.146+.)"
---

# Code Review

You are the **orchestrator**. Phase 1 sets up worktrees and gathers context. Phase 2 runs fail-fast gates (Approach + Build) in parallel. Phase 3 dispatches deep-dive agents. Phase 4 synthesizes with priority-weighted effort. Phase 5 cleans up.

## Decision Tree

```
SITUATION?
|
+-- "Review this code" / "Do a code review"
|   -> Prior report + meta sidecar exist for this branch?
|      (.CodeReview/{BranchName}.md + .CodeReview/.{BranchName}.review-meta.json)
|   |   -> YES: Follow-up mode -> references/followup-review.md
|   |   -> NO:  Full pipeline: Phases 1-5
|
+-- "Follow up review" / "Re-review" / "Check my fixes"
|   -> Follow-up mode -> references/followup-review.md
|
+-- "Quick review" / "Quick code review"
|   -> Use code-review-lite skill instead
|
+-- Received code review feedback
|   -> Feedback reception protocol (below)
|
+-- Need others to review my work
    -> Requesting review protocol (below)
```

## Agent Pipeline

| Stage | Owner | Runtime Effort | Phase |
|---|---|---|---|
| Approach Gate | Orchestrator (inline) | opus | 2a |
| Build Validator | Sub-agent | haiku | 2b |
| Requirement Validator (P1) | Sub-agent | sonnet | 3 |
| Performance Reviewer (P2) | Sub-agent | sonnet | 3 |
| Security Reviewer (P3) | Sub-agent | sonnet | 3 |
| Philosophy Reviewer (P4) | Sub-agent | sonnet | 3 |
| Standard Reviewer (P5) | Sub-agent | sonnet | 3 |
| Synthesis | Orchestrator | opus | 4 |

All sub-agents use code-reviewer delegation (`Task(subagent_type="code-reviewer", prompt="...", description="...")`). P1-P5 = synthesis effort tiers (see `references/analysis-framework.md`). On follow-up reviews (iteration 2+) the deep-dive fan-out is replaced by a single Delta Reviewer — see Follow-up Review below.

**Dispatch pattern (token rule)** — never paste file contents (agent prompts, diffs, standards docs) into dispatch prompts. Every sub-agent prompt follows this shape:

> Read `{skill-dir}/references/agents/{agent}.md` and follow it exactly — it defines your role and output format.
> Worktree: `{WORKTREE_PATH}`
> Diff file: `{absolute path to .CodeReview/.{BranchName}.diff}`
> {role-specific context — file paths and short inline items only}

The orchestrator does not read the agent prompt files itself; agents self-load them.

## Phase 1: Pre-Work (Orchestrator)

Run independent steps in parallel.

- **Determine scope** — PR ID, branch, staged, or specific files (`references/review-workflow.md` §1)
- **Collect changes** — file list + full diff with context, written ONCE to `.CodeReview/.{BranchName}.diff` (`references/review-workflow.md` §2). Agents read the diff from this file; the orchestrator reads it once for the Approach Gate and synthesis.
- **Detect project types** — `.csproj`/`.sln` for .NET, `package.json` with `build` script for Node/React. Scope builds to changed project paths only.
- **Discover neighbors** — for each changed file, use Glob/Grep to find 2–3 exemplars (same folder, same suffix e.g. `*Service.cs` / `*Handler.ts` / `*.test.tsx`, same feature folder). Cap 3 per changed file. Skip if file is in a brand-new folder or has no siblings. Output: `{changed_file: [exemplar_paths]}` map. Pass **paths only** to the Standard Reviewer — the agent reads the exemplars itself.
- **Discover standards** — AGENTS.md, CLAUDE.md, .editorconfig, *.instructions.md, linter configs (`references/standards-discovery.md`). Capture **file paths** for the Standard Reviewer (the agent reads the content itself).
- **Resolve work item** — run `python <code-review-pro-skill>/scripts/ado_work_item.py context [--pr {pr-id}]` (detects from PR/branch/commits, fetches + strips HTML, includes parent). On exit 3/2 follow the fallback chain in `references/requirement-validation.md` (ado-context.md alias lookup → ask user). If none, mark Approach Gate inconclusive.
- **Worktree setup** — `git worktree add` per repo touched by the PR (`references/review-workflow.md` §4). Multi-repo discovery via PR link, user prompt, or asking.

## Phase 2: Quick Gate (Parallel)

Dispatch 2a and 2b together — orchestrator's inline reasoning runs concurrent with the Build Validator.

### 2a. Approach Assessment (Orchestrator inline, opus)

Read diff + work item + standards. Apply the strict 4-criteria REJECT bar from `references/approach-gate.md`. The bar is intentionally high — when in doubt → PASS. PASS-with-concerns surfaces concerns as P1 findings during synthesis.

### 2b. Build Validator (sub-agent, haiku)

Dispatch with the standard path-based prompt pointing at `references/agents/build-validator.md` (context: worktree path + detected project paths; no diff needed). The first line of agent output is `Gate Result: PASS | FAIL` — use it for deterministic branching.

### Decision

- **2a REJECT** → write Reject report → Phase 5 → STOP
- **2b FAIL** → write Build Fail report → Phase 5 → STOP
- **Both PASS** → continue to Phase 3

Short report formats: `references/short-reports.md`. If both gates fail, Reject takes precedence (architectural fail is more fundamental than build fail).

## Phase 3: Deep Dive (Parallel)

Dispatch all 5 agents in a SINGLE message for true parallelism, using the standard path-based prompt (worktree + diff file path + the role-specific context below). Each agent self-loads its prompt file from `references/agents/`:

| Agent | File | Role-specific context |
|---|---|---|
| Requirement Validator | `agents/requirement-validator.md` | Changed-file list, full work item details (inline — small), **Approach pre-findings (if any)** |
| Performance Reviewer | `agents/performance-reviewer.md` | Project type |
| Security Reviewer | `agents/security-reviewer.md` | Project type |
| Philosophy Reviewer | `agents/philosophy-reviewer.md` | — |
| Standard Reviewer | `agents/standard-reviewer.md` | Changed-file list, **standards file paths**, **exemplar map (paths only, from Neighbor Discovery)** | Build Validator runs builds in the worktree; deep-dive agents read the diff file and consult full files in the worktree when context is needed (e.g., Performance Reviewer checking hot-path callers). Agents do not run git commands — orchestrator owns all git operations.

**Skip rules:**
- Skip Requirement Validator if no work item — note in report
- Other agents (Performance, Security, Philosophy, Standard Reviewer) are never skipped

## Phase 4: Priority-weighted Synthesis (Orchestrator, opus)

**Read `references/report-template.md` in full before writing anything.** The template defines the exact section order, the by-file organization rule, the ADO autolink safety rule, and the Must Fix shortlist shape — without it loaded, severity-bucketed agent inputs will bias the output.

Apply effort scaling from `references/analysis-framework.md`:

- **P1 (Requirement)** — re-read every flagged file, trace callers and dependents, write concrete patch sketch, re-quote acceptance criteria; re-verify the agent's blast-radius caller traces before accepting any CRITICAL regression finding
- **P2-P3 (Performance, Security)** — spot-check highest-severity findings, describe fix with example
- **P4 (Philosophy)** — trust the agent unless finding looks off, one-line note
- **P5 (Standard Reviewer)** — spot-check pattern consistency findings against exemplars; trust convention findings unless they look off

Merge agent findings per the template's Synthesis Guidelines (deduplication, build mapping, approach pre-findings, Must Fix selection — all defined there, not repeated here). Write the final report to `.CodeReview/{BranchName}.md`.

Then write/update the meta sidecar `.CodeReview/.{BranchName}.review-meta.json` — `{reviewedCommit, targetBranch, workItemId, standardsPaths[], exemplarMap{}, reviewedFiles[], iteration, reviewedAt}` (schema: `references/followup-review.md`). It is consumed by follow-up mode; without it every re-review pays the full pipeline again.

After writing any report, run the ADO autolink guard from the `code-review-publish` skill:

```bash
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{BranchName}.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{BranchName}.md"
```

Do not declare the review complete until the guard passes. Raw `#123` is allowed only for intentional work-item links.

**Organize Detailed Findings by file, never by severity.** Each agent emits severity-tagged findings per file; the report has one `### {file-path}` subsection per touched file. Severity appears only as an inline tag — never as a section heading. The Must Fix Before Merge shortlist at the top gives the at-a-glance severity view.

## Phase 5: Cleanup (Orchestrator)

**Run unconditionally** — even on REJECT, build fail, or mid-deep-dive errors. The worktree leaks if you skip.

For each worktree from Phase 1: `git worktree remove "{WORKTREE_PATH}"` (full recipe in `references/review-workflow.md` §5). Also delete the diff file `.CodeReview/.{BranchName}.diff` — but KEEP the report and the meta sidecar (follow-up mode needs them).

Synthesis (Phase 4) re-reads code from worktrees, so cleanup runs AFTER Phase 4 — never after Phase 3.

## Follow-up Review (iteration 2+)

When the branch was already fully reviewed (report + meta sidecar exist), do NOT re-run the full pipeline. Read `references/followup-review.md` and follow it. In short:

- **Reuse the sidecar** — skip scope determination, standards discovery, neighbor discovery, work item resolution, and the Approach Gate
- **Delta only** — diff `{reviewedCommit}..HEAD` into the diff file; if empty, report "no changes since last review" and stop
- **2 agents instead of 6** — Build Validator gate + one **Delta Reviewer** (`references/agents/delta-reviewer.md`) that verifies prior findings (Resolved/Unresolved/Partial) and regression-scans the delta across all lenses
- **Escalation** — delta >400 changed lines OR new files outside the original review's file set → fall back to the full 5-agent fan-out on the delta (still reusing the sidecar)
- **Full report regenerated** — stable `[mf:slug]` tags, carry-forward of untouched findings; stays compatible with `code-review-publish` iteration diffing

## Feedback Reception Protocol

When receiving code review feedback: READ → UNDERSTAND → VERIFY → EVALUATE → RESPOND → IMPLEMENT. No performative agreement. Verify suggestions against the codebase before implementing. Push back with technical reasoning when wrong. Implement one item at a time. Full protocol: `references/feedback-reception.md`.

## Requesting Review Protocol

When you need others to review your work: provide commit range, what was implemented, requirements, and areas of concern. Act on feedback by priority — Critical immediately, High before merge, Low for later. Full protocol: `references/requesting-review.md`.

## Constraints

- Prerequisite: Azure CLI for work-item retrieval — first run: `az config set extension.use_dynamic_install=yes_without_prompt`; auth via `az login` or `AZURE_DEVOPS_EXT_PAT`
- Each agent reviews ALL changed files through its own lens — split by concern, not by file
- Focus on changed code; mention unchanged code only if impacted by changes
- Use paths relative to the worktree root
- Assume warning suppressions are intentional; flag TODO comments without blocking
- Sub-agents are first-pass signals; orchestrator with opus re-verifies P1-P3 during synthesis
- Never delegate REJECT decisions — the orchestrator owns the Approach Gate
