# Agent Dispatch Prompts

Tool-agnostic prompt templates for the sub-agents this skill dispatches. **Dispatch the named agent
types** and let their configured frontmatter/TOML select model/runtime. Claude Code may parallelize;
Codex may serialize. Correctness comes from `Depends on` ordering.

Phase 0 tool-native explorer dispatch is read-only and happens before approval (Claude Code:
`Explore`; Codex: `explorer`). Phase 2+ dispatch happens only AFTER the Approval Gate.
Implementer **count auto-scales** by file count (Phase 1.3): 1–3→1,
4–6→2, 7–9→3, 10+→batches.
The plan file is the single source of truth; **the main agent owns every status write** —
sub-agents read the plan and report back, they do **not** edit it.

**Context sizing:** pass the plan **path** (`.plans/{feature-name}.md`), never inline it or file
contents (agents read via their file tools); point at `AGENTS.md` for standards; add a one-line
patterns note from the Phase 0 Explore pass (e.g. "follow `UserRepository.cs`").

**Anti-pre-judging (reviewer & quick-check dispatches):** never tell a dispatched agent what NOT to
flag and never pre-rate a finding's severity — forbidden phrasings: "do not flag", "don't treat X as
a defect", "at most Minor", "the plan chose this so it's fine". Hand it the plan's Global Constraints
block verbatim instead of interpreting it for the agent.

## Phase 0 — tool-native explorer (read-only planning)

Dispatch 1–3 explorer sub-agents per `plan-analysis.md`.

```
Dispatch a tool-native explorer sub-agent:
Map codebase context for: {feature/change summary}
Project: {project-root} — read AGENTS.md and relevant docs.
Focus: {specific area/question; one focus per agent when parallel}

## Rules
- Read-only. No edits, installs, formatting, builds, or long tests.
- Return relevant files, existing patterns to reuse, risks/questions, and suggested task boundaries.
- Keep output concise; include file paths and line anchors where useful.
```

## Phase 1.1 — Plan agent (architect, read-only design)

Dispatch 0–3 tool-native architect sub-agents scaled by complexity — 0 for a trivial change
(typo/rename/1-file), 1 for a standard change, up to 3 with distinct perspectives (e.g.
minimal-change vs clean-architecture vs risk-first) for a complex/multi-area change. Claude Code:
the built-in `Plan` agent; Codex: an explorer given a design brief.

```
Dispatch a tool-native Plan/architect sub-agent:
Design an implementation approach for: {feature/change summary}
Project: {project-root} — read AGENTS.md and relevant docs.
Phase 0 findings: {relevant files}, {patterns to reuse}, {constraints/risks}.
Requirements + Acceptance Criteria: {paste from the interview/requirement}

Propose a step-by-step implementation approach: name the concrete files to touch, the task
boundaries, the dependency order between tasks, and the trade-offs you considered.

## Rules
- Read-only. No edits, installs, formatting, builds, or tests.
- Return a concise plan proposal — files, task boundaries, dependency order, trade-offs.
```

The main agent reconciles the proposal(s) — one if solo, or multiple distinct perspectives when
parallel — into a single approach and owns the decision.

## Phase 1.5 — Plan quick-check (3+ task plans only)

One cheap, read-only, fresh-eyes sub-agent — skip for 1–2-task plans.

```
Dispatch a lightweight sub-agent:
Read ONLY the plan file at .plans/{feature-name}.md. For each task, answer: could you execute it
from the plan text alone, without asking a single question?
Return AT MOST a short list of "Task N: not executable because X" items, or "All tasks executable."
Keep your entire response under ~15 lines. Do not read other files, do not suggest improvements
beyond executability gaps.
```

The main agent fixes any flagged tasks, then proceeds to the Approval Gate.

## Phase 2.1 — Scaffold + test-first (TDD DEPTH ONLY)

*Skip this whole section in the default Simplify depth.*

**Scaffold (NO dispatch):** the **main agent** writes interfaces/signatures/empty stubs that compile
and fail at runtime (`throw new NotImplementedException()` / `raise NotImplementedError` /
`return null /* TODO */`) — no logic. Mark those tasks `scaffolded`.

**qa-engineer (failing tests):** dispatch one qa-engineer using the `unit-testing` skill.

```
Dispatch a qa-engineer sub-agent:
Generate failing unit tests for the plan below, in spec-first mode.
Project: {project-root} — read AGENTS.md for test conventions.
Plan: .plans/{feature-name}.md
Read it. For each unit-testable task, write unit tests that are the executable form of that task's
Definition of Done. The scaffold (stubs/signatures) already exists — bind tests to those real
surfaces. Tests are EXPECTED to be red (nothing is implemented yet).

For tasks without a meaningful unit-test surface (config/infra/UI), write no test — identify the
build, manual, or static check that verifies its Definition of Done. Do not enable code review as a
fallback.

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
Project: {project-root} — read AGENTS.md before writing code.
Plan: .plans/{feature-name}.md
Your task heading: ### Task {N}: {task-name}
Read the plan. The Goal, Global Constraints, and ACs apply to the whole feature; your work is your
task heading only.

## Patterns to follow
{one-line note from Phase 0 Explore, if any}

## Done when (your task is NOT complete until this is met)
{paste this task's "Done when" line — or, in TDD depth, its Definition of Done checklist including
"its scoped unit tests pass (green)"}

## Workflow
1. Read the plan file (and, in TDD depth, your scoped unit tests).
2. Implement ONLY the files listed under your task heading (in TDD depth, replace the scaffold stubs).
3. Confirm your "Done when" is met (TDD depth: run your scoped tests until they pass).
4. Do NOT edit the plan file. End with exactly one status below, plus files changed.

## Report contract (end with exactly one)
- **DONE** — every "Done when" criterion met; include the evidence.
- **DONE_WITH_CONCERNS** — works, but list concerns (risk, assumption, scope judgment call).
- **NEEDS_CONTEXT** — specific question(s); no changes made beyond what's reported.
- **BLOCKED** — cannot proceed; reason + what was attempted.

It is always OK to stop and report BLOCKED — bad work is worse than no work.

## Rules
- Only modify files listed under your task heading. Match existing patterns; no extra abstractions.
```

### Main-agent handling per status

- **DONE** → verify as usual (below), then record `Status: complete`.
- **DONE_WITH_CONCERNS** → resolve every listed concern before recording `complete`; a concern is not
  automatically fine just because the agent proceeded past it.
- **NEEDS_CONTEXT** → answer the question(s), then dispatch a **fresh** agent carrying the answers
  (don't resume the same agent).
- **BLOCKED** → never ignore the escalation and never re-dispatch the same prompt unchanged — fix the
  input (plan, context, or scope) first; see Blocker resolution below.

### Main-agent verification after each DONE return

Before recording `complete`, the main agent: (1) reads the diff / changed files, (2) checks the
reported Done-when evidence actually holds, (3) confirms no files outside the task heading were
touched. An evidence mismatch or scope violation means the task is NOT recorded as `complete` — route
it to the Phase 3.3 rework prompt with a fresh implementer instead. Only after verification passes
does the main agent record `Status: complete` in the plan and dispatch dependent tasks.

## Blocker resolution (fresh agent)

When an agent reports a blocker, decide the question, then dispatch a **fresh** code-implementer
(fresh, not resume — no `SendMessage` dependency; works in both tools):

```
Dispatch a code-implementer sub-agent:
Continue task: {task-name} — a prior attempt hit a blocker.
Project/Plan: {project-root}; plan file .plans/{feature-name}.md; task heading ### Task {N}.
Blocker + decision: {the specific question} → {your decision/approach}
Prior progress: {partial-progress summary the blocked agent returned}

## Workflow
Finish the task per the decision above; meet its "Done when"; return status + summary.
Do NOT edit the plan file. If you hit a new blocker, return it.
```

Single retry. Still blocked → main agent sets task `Status: blocked` and reports to the user.

## Phase 3.2 — verification rework

Red tests or unmet Done-when criteria always dispatch a fresh implementer for failing tasks and
re-run verification. This does not enable code review.

## Phase 3.3 — review & rework loop (`Code review: requested` only)

Skip this entire section, including review offer and verdict, when Context says
`Code review: not requested`. Otherwise run `code-review-lite` over changed files, handing it the
plan's Global Constraints block verbatim (see Anti-pre-judging above — do not tell it what to skip).
For must-fix findings, dispatch a **fresh** code-implementer for the *failing task(s) only*:

```
Dispatch a code-implementer sub-agent:
Fix issues in task: {task-name}
Project/Plan: {project-root}; plan .plans/{feature-name}.md; task heading ### Task {N}.
Findings to fix: {must-fix items from code-review-lite}

## Workflow
Address every finding in the listed files only; re-confirm the "Done when"; return status + summary.
Do NOT edit the plan file. No unrelated changes.
```

Re-verify that task → re-review. **Cap: 2 loop iterations.** Still failing → report to the user.

## Phase 4 — docs-sync (optional, per file)

For structural changes only, dispatch the cheapest capable sub-agent to update one docs file with
`git diff --stat` context. Surgical edits only; no unrelated rewrites.
