---
name: implement-plan
description: "Gated workflow: inspect + interview for unit-test/review choices, write an approved plan to .plans/, dispatch auto-scaled implementers, then verify. Use for '/implement-plan'."
---

# Implement Plan

End-to-end planning + implementation skill. **You (main agent) are the brain** — understand the
codebase, lock criteria, write the plan, then dispatch sub-agents (**the hands**) to do the work.

**Self-contained and tool-agnostic** — it does its own plan-mode-quality planning, so it does not
depend on Claude Code plan mode or any Codex step and runs the same in both tools. Use the tool-native
explorer for planning (`Explore` in Claude Code, `explorer` in Codex); use named agents
(`code-implementer`, `qa-engineer`) for implementation after approval.

## Two hard rules

1. **NO CHANGES BEFORE APPROVAL.** Planning (Phases 0–1) is **read-only except the plan file
   itself** — no scaffold, tests, implementation, or config edits until the user approves the plan
   at the **Approval Gate**. Mirrors Claude Code plan mode (plan file = only editable artifact).
2. **NEVER write production logic yourself.** After approval, dispatch code-implementers for ALL
   implementation. Two narrow exceptions: (a) **scaffolding** stubs/signatures with no logic, only
   in **TDD depth** (Phase 2); (b) trivial 1-line fixes during verification (missing import, typo).

## Input Resolution

| Input | Resolution |
|---|---|
| Inline text / idea | Treat as the starting requirement; interview to flesh out |
| No argument | Ask the user what to build, then interview |
| Path to a `requirement.md` / backlog `.md` | Read as source requirement; interview only to fill gaps |
| Path to an existing plan file (`.plans/*.md`) | Treat as a pre-written plan; keep its path; ask only for missing criteria or preference flags |
| Folder path (e.g., `.backlog/{feature}/`) | Look for a `*-plan.md` / `requirement.md` inside; read as source |
| Work item ID (numeric) | Fetch via the `azdevops-operations` skill; interview to fill gaps |

The skill **always produces** `.plans/{feature-name}.md` (unless the input *is* already a plan file
— then keep its path) and drives implementation from it after approval.

## Plan File & Feature Name

Resolve **once**, before any writes: plan folder is always the project's `.plans/` (create if
absent); plan file is always flat `.plans/{feature-name}.md` (keep an input plan file's own path);
feature name = kebab-case of the subject, ~5 words (e.g. `csv-export`).

## Phase 0 — Understand (READ-ONLY)

Understand what to build and the code it touches, to **Claude Code plan-mode quality**. No writes.

- **Context:** resolve the input; read the project's `AGENTS.md` + coding standards; dispatch
  **parallel tool-native explorer sub-agents** (read-only; up to 3, usually 1 — scale per
  `references/plan-analysis.md`) for structure, stack, patterns to reuse, and files to touch. Prefer reusing existing functions
  over new code; distil findings into per-task "patterns to follow".
- **Read the critical files yourself** that the agents flagged (the ones you'll modify or
  pattern-match against) — deepen understanding before planning; don't rely on summaries alone.
- **Lean interview** (`references/interview-guide.md`, ~5 questions, like plan-mode clarifications):
  lock **scope** (in/out), **design** (where code lives, patterns), **Acceptance Criteria**, and a
  per-task **"Done when"**. Don't proceed until you can state *what to build, how each piece is
  verified, and how you'd know the whole thing is done.*
- **Resolve two independent preferences** with multiple-choice questions when the request or an
  existing plan does not already answer them: **Write unit tests?** and **Run code review?** Skip
  only questions already answered explicitly. Do not create or rewrite a plan until both choices
  are resolved; a multiple-choice selection counts as an explicit request. Record the exact Context
  flags from `references/plan-template.md`.

## Phase 1 — Design & Write Plan (READ-ONLY except the plan file)

Turn understanding into a concrete plan on disk. The **plan file is the only write allowed here.**

### 1.1 Design via Plan agents

Dispatch **1–3 tool-native architect agents**, scaled by complexity (`references/plan-analysis.md`):
trivial (typo/rename/1-file) → skip, go straight to decomposition; standard → 1 agent; complex or
multi-area → up to 3 in parallel, each given a **distinct perspective** (e.g. minimal-change vs
clean-architecture vs risk-first). **Claude Code:** dispatch the `Plan` agent. **Codex:** dispatch an
explorer sub-agent given a design brief (same intent, different name). Each agent gets Phase 0
findings, requirements, and ACs, and returns a concrete implementation approach (prompt template in
`references/agent-prompts.md`). The **main agent reconciles** the proposal(s) into ONE approach
before decomposing — on divergence, pick the approach that best fits the locked scope/ACs, don't
average them.

### 1.2 Decompose + Actionability Gate

Decompose the reconciled approach by **feature slice** (not by layer) — each task gets a name, file
list, description, **Done when**, ACs, and a `Depends on` edge. **File isolation:** no two tasks
share a file (merge if they must). Group into independent sets (parallelize) and chains (sequence).
Glob/grep to confirm files exist and patterns hold.

Before a task is written to the plan file, it must pass the **per-task Actionability Checklist**
(`references/plan-analysis.md`): a task you cannot verify as actionable does not go in the plan —
resolve it first.

**Derive depth from the resolved unit-test choice:** `not requested` → **Simplify**
(plan→implement→verify, no new test files); `requested` → **TDD** (Phase 2 scaffold + failing unit
tests). Never infer TDD from task shape. Record both independent preferences in Context.

### 1.3 Auto-scale implementers

| Scope | Implementers |
|---|---|
| 1–3 files | 1 |
| 4–6 files | 2 |
| 7–9 files | 3 |
| 10+ files | Dependency-ordered batches, one at a time |

### 1.4 Write the plan

**Write** `.plans/{feature-name}.md` from `references/plan-template.md` (native shape:
`Context → Goal → Global Constraints → Acceptance Criteria → Tasks → Agent Assignment →
Verification`). The template's
**Agent Assignment** section (wave / task / agent / verified-by) is mandatory — Phase 2 dispatch must
follow it. In TDD depth, expand each task's `Done when` into a `Definition of Done` checklist
(`references/definition-criteria.md`). If a plan already exists: resume if mid-flight, else overwrite
with a fresh decomposition.

### 1.5 Plan quick-check (3+ tasks only, token-lean)

For plans with **3 or more tasks**, dispatch **ONE cheap read-only fresh-eyes sub-agent** that reads
**only the plan file** (no other context) and answers: *"which tasks could you NOT execute without
asking a question?"* (prompt in `references/agent-prompts.md`). Fix any flagged tasks, then proceed to
the Approval Gate. **Skip this step for 1–2-task plans.**

## Approval Gate

**Stop and get explicit user approval of the written plan before any further action.** In **Claude
Code**, request approval via **ExitPlanMode** (the user reviews the plan file); **Codex fallback** —
present a short summary + plan path and ask the user to reply to approve. Until approved: **no
scaffold, tests, implementation, or other writes.** On approval, autonomous mode begins.

## Phase 2 — Implement (AFTER approval)

**Continuous execution:** once approved, do not pause for "should I continue?" check-ins or long
progress narration between tasks — stop only for a BLOCKED escalation, genuine ambiguity, or
completion.

- **(Unit tests requested / TDD only) Scaffold + test-first** — otherwise create no new test files.
  The main agent writes
  signatures/stubs that compile and fail at runtime (no logic; mark tasks `scaffolded`). Then
  dispatch a **qa-engineer** (via the `unit-testing` skill) to write failing tests that are the
  executable form of each task's Definition of Done (`references/agent-prompts.md`); verify they
  bind to the scaffold and are red **for the expected reason** — an assertion about missing behavior,
  failing output captured as evidence. Compile/import errors are not valid RED; a passing new test
  means it tests existing behavior — fix the test.
- **Dispatch implementers** per task, **auto-scaled** and **in dependency order** — parallelize an
  independent set, sequence across `Depends on` (`references/agent-prompts.md`). Before dispatching,
  record the current HEAD as that task's **base SHA**. Each agent gets the
  plan path + its task heading (don't inline files/plan). A task is complete only when its **Done
  when** is met (TDD: scoped tests green — the minimal implementation that turns RED to GREEN; resist
  adding unrequested options/config, YAGNI). **The main agent owns ALL plan-file status writes** —
  implementers return one of four statuses (`references/agent-prompts.md`) + summary; the main agent
  records each `Status`.
- **Verify before accept:** after each implementer returns, before recording anything, the main agent
  (a) reads the diff via `git diff <base>..HEAD` — **never `HEAD~1`**, which silently drops all but
  the last commit of a multi-commit task — (b) checks the task's **Done when** against that evidence,
  and (c) confirms no files outside the task's scope were touched. Only then record `Status: complete`
  and release dependent tasks. An **evidence mismatch is rework**, not a `complete` — route it through
  the fresh-agent blocker/rework pattern below.
- **Blocker (fresh-agent pattern):** decide the specific question, then dispatch a **fresh**
  code-implementer carrying the plan path, task heading, the question + your decision, and the
  partial-progress summary. Single retry; if still blocked, set `Status: blocked` and report.

## Phase 3 — Verify

- **Per-task check:** verify each task's **Done when** (TDD: tests green; build clean; behavior
  present); update each `Status` in the plan.
- **Build & test:** run the project's build + existing test suite **once** + `git diff` to confirm
  changes match intent; record results in the plan's Verification. This remains required when new
  unit tests were not requested. Red tests trigger fresh-implementer rework for failing tasks.
- **Code review (only when `Code review: requested`):** run `code-review-lite` over changed files.
  On **must-fix** findings or red tests, dispatch **ONE** fresh code-implementer carrying the complete
  findings list — never one agent per finding — for the *failing task(s) only* → re-verify →
  re-review. **Cap: 2 iterations**, then report with full context.
- **AC check:** tick the plan's Acceptance-Criteria checkboxes from evidence (note any left unmet).

## Phase 4 — Report (+ optional docs-sync)

If all tasks complete and ACs satisfied, mark the plan done. For **structural** changes (new
modules/scripts/folders/commands), offer to sync project docs (`AGENTS.md`, `README.md`, index
tables) via a sub-agent per file; skip for pure behavior changes. **Report:** plan path, files
changed (count + list), AC status, build/test results, manual follow-ups, and review verdict only
when code review was requested.

## Quick Reference: Error Handling

| Situation | Action |
|---|---|
| User can't state how a task is verified | Resolve in Phase 0 — don't plan a task without a "Done when" |
| About to change code before approval | STOP — only the plan file is writable until the gate clears |
| Agent hits blocker | Fresh code-implementer with the question + partial progress (1 retry); `blocked` if unresolved |
| Tests red / Done-when unmet | Fresh implementer for the failing task → re-verify (cap 2 loops) |
| Review must-fix (`Code review: requested` only) | Fresh implementer for the failing task → re-verify → re-review (cap 2 loops) |
| Implementer reports complete but evidence doesn't hold | Treat as must-fix rework (fresh implementer); do not record complete |
| Loop exhausted | Report with full context |
| Scope 10+ files | Dependency-ordered batches, one batch at a time |
| Context compacted/summarized | Trust the plan file's task `Status` fields + `git log` over recollection; never re-dispatch a task already `complete` |
