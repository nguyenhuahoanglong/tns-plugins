---
name: implement-plan
description: "Execute an implementation plan using parallel code-implementer agents. Analyzes feasibility, dispatches implementers, verifies results. Use for '/implement-plan'."
version: 1.0.0
---

# Implement Plan

Execute an existing plan by orchestrating code-implementer sub-agents. You (main agent) are the brain — think, decompose, review. Code-implementers are the hands — they write code.

**You NEVER write production code.** Dispatch code-implementers for ALL implementation work. The only exception: trivial 1-line fixes found during verification (missing import, typo).

## Input Resolution

| Input | Resolution |
|-------|-----------|
| `.backlog/{feature}/` folder | Read `plan.md` + `requirement.md` if present |
| Path to `.md` file | Read as plan |
| Work item ID (numeric) | Fetch from Azure DevOps, extract description + ACs |
| Inline text | Treat as plan description |
| No argument | Ask user for plan location |

## Phase 1: Orient

**Goal:** Understand the plan, verify it's implementable, decompose into tasks.

### 1.1 Read Context

- Read the plan input (resolved per table above)
- Read project's `AGENTS.md` and coding standards
- If plan references unfamiliar code → spawn one `Explore` agent for codebase context

### 1.2 Analyze Plan Feasibility

Follow `references/plan-analysis.md` to verify the plan is implementable:

- **Do target files exist?** Glob/grep — don't assume from the plan text
- **Do assumed patterns still hold?** e.g., "add to the service layer" — is there one?
- **Are changes concrete enough?** Each change should map to specific files and actions
- **Dependency ordering?** Can tasks run in parallel, or must some precede others?
- **Scope accuracy?** Does the plan's file count match reality?

**Interview trigger** — a stale or inaccurate plan (not just ambiguous wording):
- If plan has gaps or is outdated → ask user **1-2 targeted questions** to improve it
- If plan needs >2 clarifications → ask user to flesh it out or use `implement-feature`
- Questions focus on **implementation details**, not requirements gathering

### 1.3 Decompose into Tasks

Group by **feature slice** (logical), not by file type (layer):

- ✅ "Add GetUsers endpoint" → controller + service + test in one task
- ❌ "All controllers" / "All services" / "All tests" as separate tasks

Each task: name, file list, description, relevant ACs from the plan.

**File isolation rule:** No two tasks share the same file. If files must overlap → merge those tasks.

### 1.4 Determine Agent Count

| Scope | Agents | Action |
|-------|--------|--------|
| 1–3 files | 1 code-implementer | Single dispatch |
| 4–6 files | 2 code-implementers | Parallel dispatch |
| 7–8 files | 3 code-implementers | Parallel dispatch |
| 9+ files | — | Suggest `implement-feature` |

## Phase 2: Implement

Dispatch code-implementer agents in parallel. Use templates from `references/agent-prompts.md`.

**Dispatch rules:**
- All agents in a **single message** for true parallelism
- Use `subagent_type: "code-implementer"` — no model override (inherits from project config)
- Don't inject full file contents — agents read files themselves
- Keep plan context to **~500 words max** per agent (relevant ACs + design decisions only)

**On completion**, read each agent's result and check for blockers.

### Blocker Handling (Advice Pattern)

If an agent reports a blocker (can't resolve, needs architectural guidance):

1. **Continue the same agent** via `SendMessage` — preserves its full context (files read, partial edits)
2. Provide your guidance on the specific question
3. This is the single retry — if still blocked, report to user

Tell implementers in the prompt: "If you hit a blocking issue you cannot resolve, return your partial progress and the specific question. You will receive guidance and continue."

## Phase 3: Verify

**Standard verification** — confirm implementation matches the plan.

### 3.1 Build Check

Run build/lint/test commands if the project has them (`npm test`, `dotnet build`, `pytest`, etc.).

- If build fails → dispatch ONE **new** code-implementer with error output + fix instructions (fresh context is better for build fixes)
- If retry fails → report error to user with full context

### 3.2 Diff Review

Read the combined diff (`git diff`):

- Do changes align with the plan's intent?
- Any obvious issues? (missing imports, wrong patterns, leftover debug code, security concerns)
- **Trivial 1-line fixes** → apply directly (only case where main agent edits code)

### 3.3 AC Check

If the plan has acceptance criteria, verify each:

| Status | Meaning |
|--------|---------|
| ✅ Met | Change clearly addresses the AC |
| ⚠️ Partial | Partially addressed, note what's missing |
| ❌ Not addressed | AC not covered by any change |

If critical ACs are not met → report to user (don't auto-retry the whole plan).

### 3.4 Report

Summarize to the user:

- Files changed (count + list)
- AC status (if applicable)
- Build/test results
- Anything needing manual attention or follow-up

## Quick Reference: Error Handling

| Situation | Action |
|-----------|--------|
| Agent hits blocker | SendMessage with guidance to same agent (1 attempt) |
| Build fails after implementation | Fresh code-implementer with error context (1 retry) |
| Retry fails | Report to user, suggest manual fix |
| Scope > 8 files | Suggest `implement-feature` |
| Plan stale or inaccurate | Interview (1-2 questions), or ask user to improve plan |
| Plan needs > 2 clarifications | Redirect to `implement-feature` |
