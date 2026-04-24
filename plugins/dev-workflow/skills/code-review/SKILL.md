---
name: code-review
description: Multi-agent parallel code review with fail-fast gates (approach + build) and quick mode. Use for code reviews, PR reviews, quick sanity checks, or when receiving review feedback.
---

# Code Review

You are the **orchestrator**. Phase 1 sets up worktrees and gathers context. Phase 2 runs fail-fast gates (Approach + Build) in parallel. Phase 3 dispatches deep-dive agents. Phase 4 synthesizes with priority-weighted effort. Phase 5 cleans up.

## Decision Tree

```
SITUATION?
|
+-- "Review this code" / "Do a code review"
|   -> Full pipeline: Phases 1-5
|
+-- "Quick review" / "Quick code review"
|   -> Quick mode: Phases 1-2 + short report + Phase 5
|
+-- Received code review feedback
|   -> Feedback reception protocol (below)
|
+-- Need others to review my work
    -> Requesting review protocol (below)
```

## Agent Pipeline

| Stage | Owner | Model | Phase |
|---|---|---|---|
| Approach Gate | Orchestrator (inline) | opus | 2a |
| Build Validator | Sub-agent | haiku | 2b |
| Requirement Validator (P1) | Sub-agent | sonnet | 3 |
| Performance Reviewer (P2) | Sub-agent | sonnet | 3 |
| Security Reviewer (P3) | Sub-agent | sonnet | 3 |
| Philosophy Reviewer (P4) | Sub-agent | sonnet | 3 |
| Convention Checker (P5) | Sub-agent | haiku | 3 |
| Synthesis | Orchestrator | opus | 4 |

All sub-agents use `subagent_type: code-reviewer`. P1-P5 = synthesis effort tiers (see `references/analysis-framework.md`).

## Phase 1: Pre-Work (Orchestrator)

Run independent steps in parallel.

- **Determine scope** — PR ID, branch, staged, or specific files (`references/review-workflow.md` §1)
- **Collect changes** — file list + full diff with context (`references/review-workflow.md` §2)
- **Detect project types** — `.csproj`/`.sln` for .NET, `package.json` with `build` script for Node/React. Scope builds to changed project paths only.
- **Discover standards** — `AGENTS.md`, `CLAUDE.md`, `.editorconfig`, `*.instructions.md`, linter configs (`references/standards-discovery.md`). Capture content for the Convention Checker.
- **Resolve work item** — PR linked items → commit messages → branch name → ask user (`references/requirement-validation.md`). If none, mark Approach Gate inconclusive.
- **Worktree setup** — `git worktree add` per repo touched by the PR (`references/review-workflow.md` §4). Multi-repo discovery via PR link, user prompt, or asking.

## Phase 2: Quick Gate (Parallel)

Dispatch 2a and 2b together — orchestrator's inline reasoning runs concurrent with the Build Validator.

### 2a. Approach Assessment (Orchestrator inline, opus)

Read diff + work item + standards. Apply the strict 4-criteria REJECT bar from `references/approach-gate.md`. The bar is intentionally high — when in doubt → PASS. PASS-with-concerns surfaces concerns as P1 findings during synthesis.

### 2b. Build Validator (sub-agent, haiku)

Dispatch using `references/agents/build-validator.md`. The first line of agent output is `Gate Result: PASS | FAIL` — use it for deterministic branching.

### Decision

REJECT and FAIL apply regardless of mode (quick or full):

- **2a REJECT** → write Reject report → Phase 5 → STOP
- **2b FAIL** → write Build Fail report → Phase 5 → STOP
- **Quick mode + both PASS** → write Quick Pass report → Phase 5 → STOP
- **Full mode + both PASS** → continue to Phase 3

Short report formats: `references/short-reports.md`. If both gates fail, Reject takes precedence (architectural fail is more fundamental than build fail).

## Phase 3: Deep Dive (Parallel, full mode only)

Dispatch all 5 agents in a SINGLE message for true parallelism. Each agent reads its prompt from `references/agents/`:

| Agent | File | Context to inject |
|---|---|---|
| Requirement Validator | `agents/requirement-validator.md` | Changed files + summary, full work item details, **Approach pre-findings (if any)** |
| Performance Reviewer | `agents/performance-reviewer.md` | Full diff, project type |
| Security Reviewer | `agents/security-reviewer.md` | Full diff, project type |
| Philosophy Reviewer | `agents/philosophy-reviewer.md` | Full diff |
| Convention Checker | `agents/convention-checker.md` | Changed files, full diff, discovered standards |

Pass the worktree path to each agent. Build Validator runs builds there; deep-dive agents work from the injected diff and consult full files in the worktree when context is needed (e.g., Performance Reviewer checking hot-path callers). Agents do not run git commands — orchestrator owns all git operations.

**Skip rules:**
- Skip Requirement Validator if no work item — note in report
- Other agents (Performance, Security, Philosophy, Convention) are never skipped

## Phase 4: Priority-weighted Synthesis (Orchestrator, opus)

**Read `references/report-template.md` in full before writing anything.** The template defines the exact section order, the by-file organization rule, and the Must Fix shortlist shape — without it loaded, severity-bucketed agent inputs will bias the output.

Apply effort scaling from `references/analysis-framework.md`:

- **P1 (Requirement)** — re-read every flagged file, trace callers and dependents, write concrete patch sketch, re-quote acceptance criteria
- **P2-P3 (Performance, Security)** — spot-check highest-severity findings, describe fix with example
- **P4-P5 (Philosophy, Convention)** — trust the agent unless finding looks off, one-line note

Deduplicate (same `file:line` from multiple agents → one entry with multi-tag, highest severity wins). Build errors → CRITICAL, warnings → MEDIUM. Approach pre-findings get `[Approach]` tag and feed the Requirement Fulfillment section. Write the final report to `.CodeReview/{BranchName}.md`.

**Organize Detailed Findings by file, never by severity.** Each agent emits severity-tagged findings per file; the report has one `### {file-path}` subsection per touched file. Severity appears only as an inline tag — never as a section heading. The Must Fix Before Merge shortlist at the top gives the at-a-glance severity view.

## Phase 5: Cleanup (Orchestrator)

**Run unconditionally** — even on REJECT, build fail, or mid-deep-dive errors. The worktree leaks if you skip.

For each worktree from Phase 1: `git worktree remove "{WORKTREE_PATH}"` (full recipe in `references/review-workflow.md` §5).

Synthesis (Phase 4) re-reads code from worktrees, so cleanup runs AFTER Phase 4 — never after Phase 3.

## Quick Mode

Trigger phrases: "quick review", "quick code review", or reasonable variants. Flow: Phase 1 → Phase 2 → short report → Phase 5 → STOP. No deep dive.

Use for pre-merge sanity checks. Run full review (`code review`) for the actual merge gate.

## Feedback Reception Protocol

When receiving code review feedback: READ → UNDERSTAND → VERIFY → EVALUATE → RESPOND → IMPLEMENT. No performative agreement. Verify suggestions against the codebase before implementing. Push back with technical reasoning when wrong. Implement one item at a time. Full protocol: `references/feedback-reception.md`.

## Requesting Review Protocol

When you need others to review your work: provide commit range, what was implemented, requirements, and areas of concern. Act on feedback by priority — Critical immediately, High before merge, Low for later. Full protocol: `references/requesting-review.md`.

## Constraints

- Each agent reviews ALL changed files through its own lens — split by concern, not by file
- Focus on changed code; mention unchanged code only if impacted by changes
- Use paths relative to the worktree root
- Assume warning suppressions are intentional; flag TODO comments without blocking
- Sub-agents are first-pass signals; orchestrator (opus) re-verifies P1-P3 during synthesis
- Never delegate REJECT decisions — the orchestrator owns the Approach Gate
