# Agent Dispatch Prompts

Tool-agnostic prompt templates for the sub-agents this skill dispatches. **Dispatch the same way your tool delegates** — Claude Code spawns agents in a single message for parallelism; Codex delegates per its own mechanism (and may serialize). Never hardcode a model tier (Claude uses sonnet/opus; Codex uses the global model + reasoning effort) and never assume true concurrency — correctness comes from `Depends on` ordering, not from agents literally running at once.

The plan file is the single source of truth. **The main agent owns every status write** — sub-agents read the plan and report status back; they do **not** edit plan.md.

## Context sizing

| Content | Rule |
|---|---|
| Plan file | Pass the **path** — never inline it. The agent reads its own task. |
| File content | Never inject — agents read via their file tools. |
| Coding standards | Point at `AGENTS.md`; the agent reads it. |
| Patterns | One-line note from the Phase 0 Explore pass (e.g. "follow `UserRepository.cs`"). |

---

## Phase 2 — Scaffold (NO dispatch)

The **main agent** writes the scaffold itself — interfaces, signatures, empty stubs, no logic. There is no sub-agent here. Stub each task's Contracts so they compile and fail at runtime (`throw new NotImplementedException()` / `raise NotImplementedError` / `return null /* TODO */`). Mark those tasks `scaffolded` in the plan.

---

## Phase 3 — qa-engineer (test-first)

Dispatch one qa-engineer using the `unit-testing` skill.

```
Dispatch a qa-engineer sub-agent:

Generate failing unit tests for the plan below, in spec-first mode.

## Project
Path: {project-root} — read AGENTS.md for test conventions.

## Plan
File: {plan-folder}/{feature-name}-plan.md
Read it. For each task with `Unit-testable: yes`, write unit tests that are the executable
form of that task's Definition of Done. The scaffold (stubs/signatures) already exists — bind
tests to those real surfaces. Tests are EXPECTED to be red (nothing is implemented yet).

For tasks marked `Unit-testable: no`, write no test — note "review-only gate" and move on.

## Rules
- Use the unit-testing skill's conventions for the stack (xUnit / Vitest / etc.).
- Do NOT implement the source files — only tests. Those belong to the implementers.
- Name each test after the DoD item it verifies.
- Return a list of test files written and which task/DoD item each covers.
```

**Verify:** read the test files — they exist, reference the scaffold, map to the DoD, and are red.

---

## Phase 4 — code-implementer (per task, dependency-ordered)

Dispatch independent tasks together; sequence across `Depends on`.

```
Dispatch a code-implementer sub-agent:

Implement task: {task-name}

## Project
Path: {project-root} — read AGENTS.md before writing code.

## Plan
File: {plan-folder}/{feature-name}-plan.md
Your task heading: ### Task {N}: {task-name}
Read the plan. The Goal and ACs apply to the whole feature; your work is your task heading only.

## Patterns to follow
{one-line note from Phase 0 Explore, if any}

## Definition of Done (your task is NOT complete until ALL are met)
{paste this task's Definition of Done checklist — including "its unit tests pass (green)"}

## Workflow
1. Read the plan file and your scoped unit tests.
2. Implement ONLY the files listed under your task heading (replace the scaffold stubs with real logic).
3. Run your scoped unit tests until they pass.
4. Do NOT edit the plan file. Return: status (complete | blocked), files changed, and which
   DoD items now pass. If blocked, return partial progress + the specific question.

## Rules
- Only modify files listed under your task heading. Match existing patterns; no extra abstractions.
- Make your scoped tests green — that is your done-signal.
```

After each agent returns, **the main agent** records its task `Status` in plan.md.

## Blocker resolution (fresh agent)

No `SendMessage`/agent-resume dependency — works in both tools. When an agent reports a blocker, decide the question, then dispatch a **fresh** code-implementer:

```
Dispatch a code-implementer sub-agent:

Continue task: {task-name} — a prior attempt hit a blocker.

## Project / Plan
{project-root}; plan file {plan-folder}/{feature-name}-plan.md; task heading ### Task {N}.

## Blocker + decision
{the specific question} → {your decision/approach}

## Prior progress
{partial-progress summary the blocked agent returned}

## Workflow
Finish the task per the decision above; make your scoped tests pass; return status + summary.
Do NOT edit the plan file. If you hit a new blocker, return it.
```

Single retry. Still blocked → main agent sets task `Status: blocked` and reports to the user.

---

## Phase 5 — review & rework loop

Run `code-review-lite` over the changed files (skill or sub-agent). For must-fix findings or red tests, dispatch a **fresh** code-implementer for the *failing task(s) only*:

```
Dispatch a code-implementer sub-agent:

Fix issues in task: {task-name}

## Project / Plan
{project-root}; plan {plan-folder}/{feature-name}-plan.md; task heading ### Task {N}.

## Findings to fix
{must-fix items from code-review-lite, and/or failing test names + output}

## Workflow
Address every finding in the listed files only; make the scoped tests pass; return status + summary.
Do NOT edit the plan file. No unrelated changes.
```

Re-run that task's tests → re-review. **Cap: 2 loop iterations.** Still failing → Meta `Status: blocked`, report.

---

## Optional Phase 6 — docs-sync (per file)

Only for structural changes (new modules/scripts/folders/commands):

```
Dispatch a sub-agent (cheapest capable tier):

Update {absolute-path} for structural changes from "{feature-name}".
Changes: {git diff --stat summary + description of new modules/scripts}.
Make surgical edits to affected sections only — do not rewrite unrelated content.
```
