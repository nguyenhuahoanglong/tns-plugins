# Implementer Prompt Templates

Prompt templates for dispatching the code-implementer sub-agent in Phase 2. Fill placeholders before dispatching.

## Context Sizing Guidelines

| Content | Rule |
|---------|------|
| Plan context | ~500 words max — relevant ACs + design decisions only |
| File content | Never inject — agent reads files itself via Read tool |
| Coding standards | Point to AGENTS.md path — agent reads it itself |
| Codebase patterns | Brief note on patterns to follow (e.g., "follow existing repository pattern in `UserRepository.cs`") |

## Code-Implementer Dispatch

Dispatch a single agent for the full plan scope.

```
Task({
  subagent_type: "code-implementer",
  description: "Implement: {plan-title}",
  prompt: `
Implement the plan described below.

## Project
Path: {project-root}
Read the project's AGENTS.md for coding standards before writing any code.

## Plan Context
{relevant portion of plan — goal, design decisions, ~500 words max}

## Task Scope
**Files to create or modify:**
{file list with brief description of changes per file}

**Acceptance Criteria:**
{ACs from the plan}

## Patterns to Follow
{brief note on existing patterns to match, if identified in Phase 1}

## Rules
- ONLY modify files listed above
- Follow existing code patterns and project conventions
- No unnecessary abstractions — match the codebase style
- If you hit a blocking issue you cannot resolve (architectural decision needed,
  ambiguous requirement, conflicting patterns), return your partial progress and
  describe the specific blocker. You will receive guidance and continue.
  `
})
```

## Blocker Resolution (SendMessage)

When the agent reports a blocker, continue it with guidance — this preserves all context (files read, partial edits, mental model). Use only once; if still blocked, report to user.

```
SendMessage({
  to: "{agent-id}",
  message: `
Guidance on your blocker:

{analysis and decision on the specific question}

Continue implementing with this approach. If the guidance resolves your concern,
complete the remaining work. If you encounter another issue, report what you have
completed and the new blocker.
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

## Build Error
{full error output}

## Files Involved
{files from the failed task that likely caused the error}

## What Was Being Implemented
{brief context — what the original plan was trying to achieve}

## Rules
- Focus ONLY on fixing the build error
- Do not refactor or add features beyond what is needed for the fix
- If the error requires an architectural change, report it instead of guessing
  `
})
```
