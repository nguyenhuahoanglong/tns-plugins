# Agent Dispatch Templates

Prompt templates for dispatching code-implementer sub-agents in Phase 2. Fill placeholders before dispatching.

## Context Sizing Guidelines

| Content | Rule |
|---------|------|
| Plan context per agent | ~500 words max — relevant ACs + design decisions for this task only |
| File content | Never inject — agents read files themselves via Read tool |
| Coding standards | Point to AGENTS.md path — agents read it themselves |
| Codebase patterns | Brief note on patterns to follow (e.g., "follow existing repository pattern in `UserRepository.cs`") |

## Code-Implementer Dispatch

Dispatch one agent per task. All tasks in a **single message** for parallel execution.

```
Agent({
  subagent_type: "code-implementer",
  description: "Implement: {task-name}",
  prompt: `
Implement task: {task-name}

## Project
Path: {project-root}
Read the project's AGENTS.md for coding standards before writing any code.

## Plan Context
{relevant portion of plan — what this task achieves, ~500 words max}

## Task Scope
**Files to create or modify:**
{file list with brief description of changes per file}

**Acceptance Criteria this task addresses:**
{relevant ACs from the plan}

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

When an agent reports a blocker, continue it with guidance — this preserves all context the agent has built (files read, partial edits, mental model).

```
SendMessage({
  to: "{agent-id-or-name}",
  message: `
Guidance on your blocker:

{opus's analysis and decision on the specific question}

Continue implementing with this approach. If the guidance resolves your concern,
complete the remaining work. If you encounter another issue, report what you've
completed and the new blocker.
  `
})
```

**When to use SendMessage vs fresh Agent:**
- **SendMessage** — agent hit a design/pattern question, needs guidance, has partial work done
- **Fresh Agent** — build failure retry (clean slate with error output is more effective)

## Build-Failure Retry

When Phase 3 build check fails, dispatch a fresh code-implementer with the error context. A clean context focused on the error is more effective than continuing an agent that produced the broken code.

```
Agent({
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
{brief context — what the original task was trying to achieve}

## Rules
- Focus ONLY on fixing the build error
- Do not refactor or add features beyond what's needed for the fix
- If the error requires an architectural change, report it instead of guessing
  `
})
```

## Example: 2-Agent Parallel Dispatch

For a plan with two logical tasks (e.g., "Add user endpoint" + "Add user notification"):

```
// Single message, two Agent calls — true parallelism
Agent({
  subagent_type: "code-implementer",
  description: "Implement: user endpoint",
  prompt: `... task 1 details ...`
})

Agent({
  subagent_type: "code-implementer",
  description: "Implement: user notification",
  prompt: `... task 2 details ...`
})
```

Both agents run simultaneously. Neither touches the other's files (enforced by Phase 1 decomposition).
