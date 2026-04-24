---
name: implement-plan-lite
description: "Lightweight single-agent plan executor for Claude Pro. Requires a plan file. Use for 'implement plan lite', 'lite implement', or 'run plan lite'."
version: 1.0.0
---

# Implement Plan Lite

Execute an existing plan using a single code-implementer sub-agent. You (main agent) are the brain — gate the plan, dispatch the implementer, verify results.

**NEVER write production code yourself — DELEGATE to the code-implementer sub-agent.**
**NEVER proceed without a plan file — reject and redirect per the input contract below.**

## Input Resolution

| Input | Action |
|-------|--------|
| Path to `.md` plan file | Read as plan |
| `.backlog/{feature}/` folder | Read `plan.md` (+ `requirement.md` if present) |
| No argument | Ask user for plan file path — do NOT offer inline alternative |
| Inline text / free-form description | REJECT — respond: "implement-plan-lite requires an existing plan file. Use `/plan` or `implement-feature` to generate one first, then invoke lite with the resulting plan path." |
| Work item ID (numeric) | REJECT — lite has no ADO integration. Use the original `implement-plan` skill for ADO-sourced plans. |

## Phase 1: Read and Gate

**Goal:** Confirm the plan is implementable before dispatching.

1. Resolve input per the table above — reject immediately if input type is disallowed
2. Read the plan file
3. Read the project's `AGENTS.md` for coding standards

**Plan-quality gate** — verify the plan contains ALL of:
1. A stated goal or purpose (1+ sentence)
2. Explicit file list or target scope
3. Acceptance criteria OR verification steps

If any item is missing → STOP. Respond: "Plan is too thin — missing: {list}. Flesh out the plan or use `implement-feature` for combined planning + implementation."

**Scope gate** — count files in the plan:
- 1-6 files: proceed to Phase 2
- 7+ files: respond: "This plan covers {n} files. Use `implement-feature` or split the plan into smaller pieces for lite execution."

## Phase 2: Implement

**MUST dispatch exactly one code-implementer sub-agent.** Use the template from `references/implementer-prompt.md`.

```
Task({
  subagent_type: "code-implementer",
  description: "Implement: {plan-title}",
  prompt: {filled template from references/implementer-prompt.md}
})
```

**If Task tool calls = 0 after Phase 2, the workflow is INCOMPLETE.**

On completion, read the agent's result and check for blockers. If the agent reports a blocker, continue it via SendMessage once (see `references/implementer-prompt.md`).

## Phase 3: Verify

1. Run `git diff` — confirm changes align with the plan's intent
2. Run build/lint/test if the project has them (`dotnet build`, `npm test`, `pytest`, etc.)
   - If build fails → dispatch ONE fresh code-implementer with error output (see `references/implementer-prompt.md` Build-Failure Retry template)
   - If retry fails → report to user with full context
3. Check each acceptance criterion:

| Status | Meaning |
|--------|---------|
| Met | Change clearly addresses the AC |
| Partial | Partially addressed — note what is missing |
| Not addressed | AC not covered by any change |

4. Report to user: files changed, AC status, build results, anything needing follow-up

## Constraints

- Only dispatch sub-agents for implementation — never edit production files directly (exception: trivial 1-line fixes like a missing import)
- Scope limit is 6 files — if plan grows during Phase 1, gate it before dispatching
- No ADO integration — do not attempt to fetch work items or update work item state
- Single dispatch — no parallel agents; lite is linear by design
