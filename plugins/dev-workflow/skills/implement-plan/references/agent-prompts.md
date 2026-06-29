# Agent Dispatch Prompts

Tool-agnostic prompt templates for the sub-agents this skill dispatches. **Dispatch the way your
tool delegates** (Claude Code parallelizes in one message; Codex may serialize). Never hardcode a
model tier or assume true concurrency — correctness comes from `Depends on` ordering.

**All dispatch below happens only AFTER the Approval Gate** — nothing here runs during planning.
Implementer **count auto-scales** by file count (Phase 1.3): 1–3→1, 4–6→2, 7–9→3, 10+→batches.
The plan file is the single source of truth; **the main agent owns every status write** —
sub-agents read the plan and report back, they do **not** edit it.

**Context sizing:** pass the plan **path** (`.plans/{feature-name}.md`), never inline it or file
contents (agents read via their file tools); point at `AGENTS.md` for standards; add a one-line
patterns note from the Phase 0 Explore pass (e.g. "follow `UserRepository.cs`").

## Phase 2.1 — Scaffold + test-first (TDD DEPTH ONLY)

*Skip this whole section in the default Simplify depth.*

**Scaffold (NO dispatch):** the **main agent** writes interfaces/signatures/empty stubs that compile
and fail at runtime (`throw new NotImplementedException()` / `raise NotImplementedError` /
`return null /* TODO */`) — no logic. Mark those tasks `scaffolded`.

**qa-engineer (failing tests):** dispatch one qa-engineer using the `unit-testing` skill.

```
Dispatch a qa-engineer sub-agent:

Generate failing unit tests for the plan below, in spec-first mode.

## Project
Path: {project-root} — read AGENTS.md for test conventions.

## Plan
File: .plans/{feature-name}.md
Read it. For each unit-testable task, write unit tests that are the executable form of that task's
Definition of Done. The scaffold (stubs/signatures) already exists — bind tests to those real
surfaces. Tests are EXPECTED to be red (nothing is implemented yet).

For tasks with a review-only gate (config/infra/UI), write no test — note it and move on.

## Rules
- Use the unit-testing skill's conventions for the stack (xUnit / Vitest / etc.).
- Do NOT implement the source files — only tests. Those belong to the implementers.
- Name each test after the Definition-of-Done item it verifies.
- Return a list of test files written and which task/item each covers.
```

**Verify:** read the test files — they exist, reference the scaffold, map to the DoD, and are red.

## Phase 2.2 — code-implementer (per task, dependency-ordered)

Dispatch independent tasks together; sequence across `Depends on`.

```
Dispatch a code-implementer sub-agent:

Implement task: {task-name}

## Project
Path: {project-root} — read AGENTS.md before writing code.

## Plan
File: .plans/{feature-name}.md
Your task heading: ### Task {N}: {task-name}
Read the plan. The Goal and ACs apply to the whole feature; your work is your task heading only.

## Patterns to follow
{one-line note from Phase 0 Explore, if any}

## Done when (your task is NOT complete until this is met)
{paste this task's "Done when" line — or, in TDD depth, its Definition of Done checklist including
"its scoped unit tests pass (green)"}

## Workflow
1. Read the plan file (and, in TDD depth, your scoped unit tests).
2. Implement ONLY the files listed under your task heading (in TDD depth, replace the scaffold stubs).
3. Confirm your "Done when" is met (TDD depth: run your scoped tests until they pass).
4. Do NOT edit the plan file. Return: status (complete | blocked), files changed, and how the
   "Done when" is satisfied. If blocked, return partial progress + the specific question.

## Rules
- Only modify files listed under your task heading. Match existing patterns; no extra abstractions.
```

After each agent returns, **the main agent** records its task `Status` in the plan.

## Blocker resolution (fresh agent)

When an agent reports a blocker, decide the question, then dispatch a **fresh** code-implementer
(fresh, not resume — no `SendMessage` dependency; works in both tools):

```
Dispatch a code-implementer sub-agent:

Continue task: {task-name} — a prior attempt hit a blocker.

## Project / Plan
{project-root}; plan file .plans/{feature-name}.md; task heading ### Task {N}.

## Blocker + decision
{the specific question} → {your decision/approach}

## Prior progress
{partial-progress summary the blocked agent returned}

## Workflow
Finish the task per the decision above; meet its "Done when"; return status + summary.
Do NOT edit the plan file. If you hit a new blocker, return it.
```

Single retry. Still blocked → main agent sets task `Status: blocked` and reports to the user.

## Phase 3.3 — review & rework loop

Run `code-review-lite` over the changed files (skill or sub-agent). For must-fix findings or red
tests, dispatch a **fresh** code-implementer for the *failing task(s) only*:

```
Dispatch a code-implementer sub-agent:

Fix issues in task: {task-name}

## Project / Plan
{project-root}; plan .plans/{feature-name}.md; task heading ### Task {N}.

## Findings to fix
{must-fix items from code-review-lite, and/or failing test names + output}

## Workflow
Address every finding in the listed files only; re-confirm the "Done when"; return status + summary.
Do NOT edit the plan file. No unrelated changes.
```

Re-verify that task → re-review. **Cap: 2 loop iterations.** Still failing → report to the user.

## Phase 4 — docs-sync (optional, per file)

Only for structural changes (new modules/scripts/folders/commands):

```
Dispatch a sub-agent (cheapest capable tier):

Update {absolute-path} for structural changes from "{feature-name}".
Changes: {git diff --stat summary + description of new modules/scripts}.
Make surgical edits to affected sections only — do not rewrite unrelated content.
```
