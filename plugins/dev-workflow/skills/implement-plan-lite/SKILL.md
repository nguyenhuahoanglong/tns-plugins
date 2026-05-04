---
name: implement-plan-lite
description: "Lightweight single-agent plan executor for Claude Pro. Plan must exist on disk; implementer reads it and updates progress. Use for 'implement plan lite', 'lite implement', or 'run plan lite'."
version: 1.1.0
---

# Implement Plan Lite

Execute an existing plan file using a single code-implementer sub-agent. You (main agent) gate the plan, ensure it has progress tracking, dispatch the implementer, and verify results.

**NEVER write production code yourself — DELEGATE to the code-implementer sub-agent.**
**NEVER proceed without a plan file — reject and redirect per the input contract below.**

## Input Resolution

| Input | Action |
|---|---|
| Path to a `.md` plan file | Read as plan; plan folder = parent directory; plan path = the file |
| Folder path (e.g., `.backlog/{feature}/`) | Look for `{feature-name}-plan.md` first, then legacy `plan.md`; plan folder = the folder |
| No argument | Ask user for plan file path — do NOT offer inline alternative |
| Inline text / free-form description | REJECT — respond: "implement-plan-lite requires an existing plan file. Use `/plan` or `implement-feature` to generate one first, then invoke lite with the resulting plan path." |
| Work item ID (numeric) | REJECT — lite has no ADO integration. Use `implement-plan` for ADO-sourced plans. |

The plan file is the single source of truth for the implementer. Lite preserves the input file's name (no rename). There is no `.plans/` fallback — the plan must already exist. **Recommended convention** when creating plans for lite: name them `{feature-name}-plan.md` so the feature/requirement is self-evident from the filename.

## Phase 1: Read & Gate & Prepare

**Goal:** Confirm the plan is implementable and has progress tracking before dispatching.

### 1.1 Resolve input

Per the table above. Reject immediately if input type is disallowed.

### 1.2 Read plan & standards

1. Read the plan file
2. Read the project's `AGENTS.md` for coding standards

### 1.3 Plan-quality gate

Verify the plan contains ALL of:
1. A stated goal or purpose (1+ sentence)
2. Explicit file list or target scope
3. Acceptance criteria OR verification steps

If any item is missing → STOP. Respond: "Plan is too thin — missing: {list}. Flesh out the plan or use `implement-feature` for combined planning + implementation."

### 1.4 Scope gate

Count files in the plan:
- 1-6 files: proceed
- 7+ files: respond: "This plan covers {n} files. Use `implement-feature` or split the plan into smaller pieces for lite execution."

### 1.5 Ensure progress tracking

The implementer needs a `Status` field on each task to update. Check the plan file for status fields:

- **Already has** task headings with `Status:` lines (e.g., `### Task 1: ...` with `- **Status**: pending`) → use as-is
- **Has tasks but no Status fields** → Edit the plan file to add `- **Status**: pending` under each task heading
- **No task structure** (single monolithic plan) → Edit the plan file to append:
  ```markdown
  ## Tasks

  ### Task 1: Implement plan
  - **Status**: pending
  - **Files**: {file list from gate}
  - **Description**: See Goal above.
  - **ACs**: All
  ```

Also ensure the plan has a Meta block with `Status` (set to `implementing`). Add if missing.

## Phase 2: Implement

**MUST dispatch exactly one code-implementer sub-agent.** Use the template from `references/implementer-prompt.md`.

```
Task({
  subagent_type: "code-implementer",
  description: "Implement: {plan-title}",
  prompt: {filled template from references/implementer-prompt.md — includes plan path}
})
```

The prompt passes `{plan-file-path}` path; the agent reads it, sets task Status to `in-progress`, implements, then sets Status to `complete`.

**If Task tool calls = 0 after Phase 2, the workflow is INCOMPLETE.**

On completion, read the agent's result and verify the task Status was updated in plan.md. If the agent reports a blocker, continue it via SendMessage once (see `references/implementer-prompt.md`).

## Phase 3: Verify

1. Read `{plan-file-path}` — every task should be `Status: complete`. Investigate any `pending` / `in-progress` / `blocked` task.
2. Run `git diff` — confirm changes align with the plan's intent
3. Run build/lint/test if the project has them (`dotnet build`, `npm test`, `pytest`, etc.)
   - If build fails → dispatch ONE fresh code-implementer with error output (see `references/implementer-prompt.md` Build-Failure Retry template)
   - If retry fails → set Meta `Status: blocked` in plan.md, report to user with full context
4. Check each acceptance criterion and update plan.md AC checkboxes (`- [x]` for met):

| Status | Meaning |
|---|---|
| Met | Change clearly addresses the AC |
| Partial | Partially addressed — note what is missing |
| Not addressed | AC not covered by any change |

5. If all complete: set Meta `Status: complete` in plan.md, append iteration log entry.
6. Report to user: plan path, files changed, AC status, build results, anything needing follow-up.

## Constraints

- Only dispatch sub-agents for implementation — never edit production files directly (exceptions: trivial 1-line fixes like a missing import; plan.md status/AC updates main agent makes during Phase 1.5 and Phase 3)
- Scope limit is 6 files — if plan grows during Phase 1, gate it before dispatching
- No ADO integration — do not attempt to fetch work items or update work item state
- Single dispatch — no parallel agents; lite is linear by design
