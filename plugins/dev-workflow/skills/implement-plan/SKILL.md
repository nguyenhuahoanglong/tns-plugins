---
name: implement-plan
description: "Self-contained implement workflow: interview to lock verifiable criteria, write plan.md, scaffold, generate tests, then dispatch parallel implementers that must pass them. Use for '/implement-plan'."
version: 2.0.0
---

# Implement Plan

End-to-end implementation skill. **You (main agent) are the brain** — you interview the user, lock verifiable criteria, write the plan, scaffold the contracts, then dispatch sub-agents to write tests and code. **Sub-agents are the hands.**

**You NEVER write production logic.** Dispatch code-implementers for ALL implementation work. Two narrow exceptions only: (1) **scaffolding** — empty stubs, interfaces, and signatures with no logic (Phase 2); (2) trivial 1-line fixes found during verification (missing import, typo).

This skill is **self-contained and tool-agnostic** — it does its own planning via interview, so it does **not** depend on Claude Code plan mode or any Codex planning step, and it runs the same way in both tools. Express every dispatch as "dispatch a code-implementer / qa-engineer sub-agent" — never assume a specific tool's call syntax, model tier, or that agents truly run concurrently (Codex may serialize; correctness must not depend on real parallelism).

## Input Resolution

| Input | Resolution |
|---|---|
| Inline text / idea | Treat as the starting requirement; interview to flesh out; plan folder = `.plans/{feature-name}/` |
| No argument | Ask the user what to build, then interview |
| Path to a `requirement.md` / backlog `.md` | Read as source requirement; interview only to fill gaps; plan folder = parent directory |
| Path to an existing plan file (`*-plan.md`) | Treat as a pre-written plan; skip the interview unless it lacks Definition-of-Done criteria; plan folder = parent directory |
| Folder path (e.g., `.backlog/{feature}/`) | Look for `{feature-name}-plan.md`, then `requirement.md`; plan folder = the folder |
| Work item ID (numeric) | Fetch via `azdevops-operations` skill; interview to fill gaps; plan folder = `.plans/{feature-name}/` |

Whatever the input, the skill **always produces** `{plan-folder}/{feature-name}-plan.md` and drives implementation from it.

## Plan Folder & File Resolution

Resolve the plan folder and feature name **once**, before any file writes:

| Input type | Plan folder | Feature name |
|---|---|---|
| Inline / idea / work item ID | `.plans/{feature-name}/` | Kebab-case of the subject (truncate to ~5 words) |
| File path | Parent directory of the file | Folder basename (or filename minus `-requirement`/`-plan` if the folder is generic like `.backlog`/`.plans`/`docs`) |
| Folder path | The folder itself | Folder basename |

**Plan file path** = `{plan-folder}/{feature-name}-plan.md`. If the input is itself a plan file, keep its name. Create the folder if it doesn't exist.

## Phase 0: Interview & Lock Criteria

**Goal:** understand what to build and lock the **verifiable criteria** before any planning. This phase is the ONLY one with user interaction — after confirmation, the skill runs autonomously.

The single most important output of this phase is the **Definition Criteria** — see `references/definition-criteria.md`. If the user cannot articulate how a task will be verified, that gap must be resolved here, before code exists.

### 0.1 Read context
- Read the input (per Input Resolution).
- Read the project's `AGENTS.md` and coding standards.
- Spawn **one** `Explore` sub-agent (medium thoroughness) for codebase context: structure, stack, patterns relevant to the change, and the files it will touch. Distil findings into per-task "patterns to follow" so implementers don't each re-explore (token win).

### 0.2 Lean, criteria-focused interview
Follow `references/interview-guide.md`. **Keep it lean: 1–2 rounds, ~5 questions max.** Skip anything the input already answers. Center every round on producing:
- **Scope** — what's in, what's explicitly out.
- **Design choices** — where the code lives, patterns to follow, contracts.
- **Acceptance Criteria** (plan-level) — testable conditions for the whole feature.
- **Definition of Done** (per task) — mechanically checkable assertions.

Do not proceed until you can state: *"I know what to build, how to verify each piece, and how I'd know the whole thing is done."*

If the input is already a complete plan file with Definition-of-Done criteria, skip the interview.

### 0.3 Confirm
Present a short summary — scope + Acceptance Criteria + per-task Definition of Done — and get explicit confirmation. **On confirmation, autonomous mode begins; no more user questions** (except an optional code-review prompt is never needed here — review is always on).

## Phase 1: Plan & Decompose

**Goal:** turn the locked criteria into a concrete, parallel-ready plan on disk.

### 1.1 Feasibility & decomposition
Follow `references/plan-analysis.md`:
- **Files exist / patterns hold?** Glob/grep — don't trust assumptions.
- **Decompose by feature slice** (logical), not by layer. Each task: name, file list, contracts/signatures, description, **Definition of Done**, relevant ACs, unit-testable flag.
- **File isolation:** no two tasks share a file. If files must overlap → merge those tasks.
- **Dependency ordering:** mark each task's `Depends on`. Group into independent sets (parallelizable) and dependency chains (sequential). File isolation prevents file conflicts; dependency marking prevents logical ones (Task B imports a surface Task A creates).

### 1.2 Determine agent count
| Scope | Implementers |
|---|---|
| 1–3 files | 1 |
| 4–6 files | 2 |
| 7–9 files | 3 |
| 10+ files | Split into dependency-ordered batches; dispatch one batch at a time |

### 1.3 Write the plan file
Write `{plan-folder}/{feature-name}-plan.md` using `references/plan-template.md`: goal, Acceptance Criteria, tasks (each with `Status: pending`, contracts, **Definition of Done**), verification block, iteration log. Set Meta `Status: implementing` when you proceed.

If the plan file already exists from a prior run: resume if tasks are mid-flight; otherwise overwrite with a fresh decomposition (preserve the iteration log).

## Phase 2: Scaffold

**You (main agent) write the scaffold — signatures, interfaces, and empty stubs only, NO logic.** This is a deliberate, bounded exception to "main agent writes no production code." It exists so that:
- the generated tests in Phase 3 **compile** against real surfaces (true red, not imaginary APIs);
- parallel implementers in Phase 4 integrate against **shared interfaces that already exist**, rather than guessing each other's surfaces.

Write each task's contracts (from Phase 1.1) as stubs that compile and fail at runtime (e.g. `throw new NotImplementedException()`, `raise NotImplementedError`, `return null /* TODO */`). Do not implement behavior. Record in the iteration log that the scaffold landed.

## Phase 3: Test-First

Dispatch a **qa-engineer** sub-agent using the `unit-testing` skill. See `references/agent-prompts.md`.

- Input: the plan path + each task's Definition of Done + the scaffold surfaces.
- The qa-engineer writes **failing (red) unit tests** that are the executable form of each task's Definition of Done.
- For tasks flagged **not unit-testable** (config, infra, pure UI tweaks): qa-engineer records "no unit test — review-only gate" for that task instead of forcing a test.
- **Verify:** read the test files — they exist, reference the scaffold, and map to the DoD. Tests should be red (nothing implemented yet).

## Phase 4: Implement

Dispatch code-implementer sub-agents per task, **in dependency order** — parallelize within an independent set, sequence across `Depends on` edges. See `references/agent-prompts.md`.

**Dispatch rules:**
- Independent tasks → dispatch together (the tool parallelizes as it can).
- Each agent receives: the plan path + its task heading. Don't inline file contents or the whole plan — agents read what they need.
- **Definition of Done for each task includes making its scoped unit tests pass (green).** An implementer's task is not complete until its tests pass.
- **The main agent owns ALL `plan.md` status writes.** Implementers do **not** edit plan.md — they return a compact status (`complete` / `blocked` + summary). This avoids parallel write collisions on the plan file. After each agent returns, the main agent records its task `Status`.

### Blocker handling (fresh-agent pattern)
If an agent reports a blocker it cannot resolve:
1. Decide the specific question (architecture/pattern/ambiguity).
2. Dispatch a **fresh** code-implementer carrying: the plan path, the task heading, the blocker question + your decision, and the partial-progress summary the blocked agent returned. (A fresh agent is used rather than resuming the same one, so the pattern works identically in Claude Code and Codex.)
3. Single retry. If still blocked, set the task `Status: blocked` and report to the user.

## Phase 5: Verify & Guardrail Loop

**Always on.** Confirm the implementation satisfies the locked criteria.

### 5.1 Per-task Definition-of-Done check
For each task, verify every Definition-of-Done item is met (its tests are green; build clean; behavior present). Update each task `Status` in plan.md.

### 5.2 Build & full test
Run the project's build + full test suite **once** (`dotnet build` / `npm test` / `pytest`, etc.). Update Verification.Build / Verification.Tests in plan.md.

### 5.3 Code review
Dispatch `code-review-lite` over the changed files (or run the skill). Collect must-fix vs advisory findings.

### 5.4 Loop
If any DoD item fails, tests are red, or review returns **must-fix**:
- Dispatch a **fresh** code-implementer for the *failing task(s) only*, with the specific findings → re-run that task's tests → re-review.
- **Cap: 2 iterations.** If still failing, set Meta `Status: blocked` and report to the user with full context. Do not loop indefinitely.

### 5.5 AC check
Update plan.md Acceptance-Criteria checkboxes from the evidence (`- [x] AC-N` when clearly met; leave unchecked with a note otherwise). If critical ACs are unmet after the loop → Meta `Status: blocked`, report.

## Phase 6: Report (+ optional docs-sync)

### 6.1 Finalize
If all tasks complete, DoD met, and ACs satisfied: set Meta `Status: complete`, append an iteration-log entry.

### 6.2 Optional docs-sync
If the change is **structural** (new modules, scripts, folders, commands), offer to sync project docs (`AGENTS.md`, `README.md`, index tables). For each affected file, dispatch a sub-agent to make surgical edits. Skip for pure behavior changes.

### 6.3 Report
Summarize: plan path, files changed (count + list), AC status, Definition-of-Done results, build/test results, review verdict, and anything needing manual attention.

## Quick Reference: Error Handling

| Situation | Action |
|---|---|
| User can't state how a task is verified | Resolve in Phase 0 — don't plan a task without a Definition of Done |
| Agent hits blocker | Fresh code-implementer with the question + partial progress (1 retry); `blocked` if unresolved |
| Tests red / DoD unmet / review must-fix | Fresh implementer for the failing task → re-test → re-review (cap 2 loops) |
| Loop exhausted | Meta `Status: blocked`, report with full context |
| Scope 10+ files | Dependency-ordered batches, one batch at a time |
