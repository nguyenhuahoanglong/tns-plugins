# Implementer Prompt Templates

Tool-agnostic templates for the single code-implementer sub-agent in Phase 2. Fill placeholders, then **dispatch the way your tool delegates** (Claude Code spawns a sub-agent; Codex delegates per its own mechanism). Never hardcode a model tier.

The plan file is the single source of truth. The implementer reads it, sets its task `Status` to `in-progress`, implements, then sets `Status` to `complete`.

## Context sizing

| Content | Rule |
|---|---|
| Plan file | Pass the path — do NOT inline. Agent reads it itself. |
| File content | Never inject — agent reads files via its tools. |
| Coding standards | Point to AGENTS.md path. |
| Patterns | Brief note (e.g., "follow `UserRepository.cs`"). |

## Implementer dispatch (single agent, full scope)

```
Dispatch a code-implementer sub-agent:

Implement the plan in the file below.

## Project
Path: {project-root} — read AGENTS.md for coding standards first.

## Plan
File: {plan-file-path}
Your task heading: ### Task {N}: {task-name}   (typically Task 1 in lite)
Read the plan. The Goal and ACs apply; your work covers the files under your task heading.

## Patterns to follow
{brief note, if identified in Phase 1}

## Workflow
1. Read {plan-file-path}.
2. Set your task's Status from `pending` to `in-progress` in the plan.
3. Implement — only modify files listed under your task heading.
4. Set your task's Status to `complete` when done.
5. Return a brief summary of what changed.

## Rules
- Only modify files under your task heading (plus the plan's status line). Match existing patterns;
  no unnecessary abstractions.
- If you hit a blocker you cannot resolve, set Status to `blocked`, return partial progress and the
  specific question.
```

> Lite is single-agent, so the implementer updating its own status line is safe (no parallel writers). This differs from the flagship `implement-plan`, where the main agent owns status writes.

## Blocker resolution (fresh agent)

When the agent reports a blocker, decide the question and dispatch a **fresh** code-implementer — this works in both Claude Code and Codex (no reliance on resuming a live agent). Use once; if still blocked, set the task `Status: blocked` and report to the user.

```
Dispatch a code-implementer sub-agent:

Continue the plan — a prior attempt hit a blocker.

## Project / Plan
{project-root}; plan file {plan-file-path}; task heading ### Task {N}.

## Blocker + decision
{the specific question} → {your decision/approach}

## Prior progress
{partial-progress summary the blocked agent returned}

## Workflow
Finish per the decision; set the task Status to `complete`; return a summary.
If you hit a new blocker, report it.
```

## Build-failure retry (fresh agent)

When the Phase 3 build check fails, dispatch a fresh code-implementer with the error context.

```
Dispatch a code-implementer sub-agent:

Fix the build error in project: {project-root}. Read AGENTS.md for standards.

## Plan
File: {plan-file-path} — read for context on what was being built.

## Build error
{full error output}

## Files involved
{files from the task that likely caused the error}

## Workflow
1. Read the plan for context.
2. Diagnose and fix the build error.
3. If a specific task caused it, update that task's Status to reflect the fix.
4. Return a brief summary.

## Rules
- Focus ONLY on fixing the build error. No refactors or new features.
- If the fix needs an architectural change, report it instead of guessing.
```
