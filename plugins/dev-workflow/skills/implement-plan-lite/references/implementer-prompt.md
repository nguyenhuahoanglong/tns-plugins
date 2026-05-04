# Implementer Prompt Templates

Prompt templates for dispatching the code-implementer sub-agent in Phase 2. Fill placeholders before dispatching.

The plan file is the single source of truth. The implementer reads it, sets its task `Status` to `in-progress`, implements, then sets `Status` to `complete`.

## Context Sizing Guidelines

| Content | Rule |
|---|---|
| Plan file | Pass the path — do NOT inline. Agent reads it itself. |
| File content | Never inject — agent reads files via Read tool |
| Coding standards | Point to AGENTS.md path — agent reads it itself |
| Codebase patterns | Brief note on patterns to follow (e.g., "follow existing repository pattern in `UserRepository.cs`") |

## Code-Implementer Dispatch

Dispatch a single agent for the full plan scope.

```
Task({
  subagent_type: "code-implementer",
  description: "Implement: {plan-title}",
  prompt: `
Implement the plan described in the file below.

## Project
Path: {project-root}
Read the project's AGENTS.md for coding standards before writing any code.

## Plan
**File**: {plan-file-path}
**Your task heading**: ### Task {N}: {task-name}   (typically Task 1 in lite)

Read the plan file first. The Goal and ACs at the top apply; your work covers the
files listed under your task heading.

## Patterns to Follow
{brief note on existing patterns to match, if identified in Phase 1}

## Workflow
1. Read {plan-file-path}
2. Edit plan.md to set your task's **Status** from \`pending\` to \`in-progress\`
3. Implement the task — only modify files listed under your task heading
4. When done, edit plan.md to set your task's **Status** to \`complete\`
5. Return a brief summary of what you changed

## Rules
- ONLY modify files listed under your task heading in plan.md (plus plan.md itself for status updates)
- Follow existing code patterns and project conventions
- No unnecessary abstractions — match the codebase style
- If you hit a blocking issue you cannot resolve (architectural decision, ambiguous
  requirement, conflicting patterns), set your task **Status** to \`blocked\` in plan.md,
  return your partial progress, and describe the specific blocker. You will receive
  guidance and continue.
  `
})
```

## Blocker Resolution (SendMessage)

When the agent reports a blocker, continue it with guidance — this preserves all context (files read, partial edits, mental model). Use only once; if still blocked, set task Status to `blocked` in plan.md and report to user.

```
SendMessage({
  to: "{agent-id}",
  message: `
Guidance on your blocker:

{analysis and decision on the specific question}

Continue implementing. When done, set your task **Status** in {plan-file-path}
to \`complete\`. If you encounter another issue, report what you have completed and
the new blocker.
  `
})
```

**When to use SendMessage vs fresh agent:**
- **SendMessage** — agent hit a design/pattern question; has partial work done
- **Fresh agent** — build failure retry (clean slate with error output is more effective)

## Build-Failure Retry

When Phase 3 build check fails, dispatch a fresh code-implementer with the error context.

```
Task({
  subagent_type: "code-implementer",
  description: "Fix build: {error-summary}",
  prompt: `
Fix the build error in project: {project-root}
Read the project's AGENTS.md for coding standards.

## Plan
**File**: {plan-file-path} — read for context on what was being built.

## Build Error
{full error output}

## Files Involved
{files from the failed task that likely caused the error}

## Workflow
1. Read plan.md for context
2. Diagnose and fix the build error
3. If a specific task in plan.md was the cause, update its **Status** to reflect the fix
4. Return a brief summary

## Rules
- Focus ONLY on fixing the build error
- Do not refactor or add features beyond what is needed for the fix
- If the error requires an architectural change, report it instead of guessing
  `
})
```
