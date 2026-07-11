# Implement Plan

## Purpose

The single planning + implementation skill. Self-contained and tool-agnostic: it understands the
codebase to **Claude Code plan-mode quality**, interviews the user to lock verifiable criteria,
writes a simplified plan to `.plans/`, **stops for explicit approval**, then — and only then —
dispatches auto-scaled implementers, always verifies, and runs code review only when selected. It does **not** depend on
Claude Code plan mode or any Codex planning step, and runs identically in both tools.

## When to use

- Any feature/change where you want planning then implementation in one flow.
- Use `/implement-plan "<idea>"` (Claude Code) or `$implement-plan "<idea>"` (Codex), or pass a
  requirement file / work-item id / existing plan / folder / nothing.

## Pain Points

- Planning discovery should be cheap and read-only, not done by high-effort implementation agents.
- Implementation agents need stable runtime settings so Codex does not silently inherit the main
  agent's high-effort configuration.

## Workflow at a glance

```
Phase 0  Understand        (READ-ONLY)  explorer + lean interview + unit-test/review choices
Phase 1  Design & plan     (READ-ONLY except the plan file)  Plan-agent design (1-3, scaled by
                            complexity) → decompose + per-task actionability gate → auto-scale →
                            write .plans/{feature}.md (incl. Agent Assignment) → plan quick-check
                            (3+ tasks)
───────  APPROVAL GATE  ──────────────  nothing else is written until the user approves
Phase 2  Implement         scaffold + red tests (TDD depth only) → auto-scaled code-implementers →
                            verify-before-accept (main agent checks diff + Done-when evidence before
                            recording complete)
Phase 3  Verify            existing build/test/diff + selected code-review-lite (cap 2 loops) + AC check
Phase 4  Report            (+ optional docs-sync for structural changes)
```

## Design notes

### No changes before approval
Planning is read-only except the plan file itself — like Claude Code plan mode, where the plan file
is the only editable artifact. Scaffold, tests, and all implementation happen strictly after the
user approves the plan at the Approval Gate.

### Default Simplify, optional TDD
Planning resolves two independent multiple-choice preferences before writing the plan: new unit
tests and code review. Missing choices block plan creation; explicit request text or existing exact
Context flags skip their matching questions. Unit tests selected means **TDD depth** (main agent
scaffolds stubs, then qa-engineer writes failing tests); not selected means no new tests while
existing suites still run. Code review selected means `code-review-lite` with a two-iteration cap;
not selected means no offer, fallback, or verdict. Both choices are recorded in Context.

### Plan-agent design step
Before decomposition, Phase 1.1 dispatches **1–3 tool-native architect agents** scaled by
complexity: trivial (typo/rename/1-file) → skip straight to decomposition; standard → 1 agent;
complex/multi-area → up to 3 in parallel, each with a distinct perspective (e.g. minimal-change vs
clean-architecture vs risk-first). **Claude Code:** the `Plan` agent. **Codex:** an explorer sub-agent
given a design brief (same intent, different name). Each agent gets Phase 0 findings, requirements,
and ACs; the **main agent reconciles** the proposal(s) into ONE approach before decomposing — on
divergence it picks the approach that best fits scope/ACs rather than averaging them.

### Per-task Actionability Gate + plan quick-check
Every task must pass a 5-item **Actionability Checklist** (`references/plan-analysis.md`) before it
is written to the plan: files confirmed via glob/read, the pattern/signature was read in the actual
file (not assumed), the description is executable by a sub-agent with zero conversation context,
"Done when" is mechanically checkable, and `Depends on` is stated. A task that fails any item is
resolved first — it does not go in the plan. Plans with **3 or more tasks** then get ONE cheap,
read-only, fresh-eyes sub-agent that reads only the plan file and flags any task it could not execute
without asking a question; token-lean by design, and skipped for 1–2-task plans.

### Orchestrator verify-before-accept
Phase 2 no longer records `complete` from an implementer's self-report. After each implementer
returns, the main agent (a) reads the diff/changed files, (b) checks the task's **Done when** against
that evidence, and (c) confirms no files outside the task's scope were touched — only then is
`Status: complete` recorded and dependent tasks released. An evidence mismatch is treated as rework,
routed through the existing fresh-agent blocker pattern, not accepted as `complete`.

### Agent Assignment section
The plan template's **Agent Assignment** section (wave / task / agent / verified-by) is mandatory —
it declares which sub-agent handles which task in which dispatch wave. Waves derive from each task's
`Depends on` edges (one independent set = one wave), and Phase 2 dispatch follows the table exactly;
the main agent verifies each row before advancing to the next wave.

### code-implementer contract alignment
`code-implementer`'s primary input is now **plan path + task heading** (it reads the plan itself)
rather than inlined files/plan text, matching how Phase 2 dispatches it. It reports a
machine-checkable `Status: complete | blocked` / `Files changed` / `Done-when evidence` /
`Issues` block instead of a free-form summary, and its self-check is now lean — re-read its own diff,
run the scoped build/tests, confirm Done-when — rather than an embedded `code-review-lite` pass,
which was redundant with Phase 3's single review over all changed files.

### Agent routing
Planning uses the tool-native explorer (`Explore` in Claude Code, `explorer` in Codex) for read-only
codebase discovery. Implementation uses `code-implementer` with the portable `standard` intent,
separate from the main agent (Claude: Sonnet; Codex: Terra with medium reasoning).

### Auto-scaled implementers
Implementer count scales by file count (1–3→1, 4–6→2, 7–9→3, 10+→dependency-ordered batches), so
small plans run lean without a separate "lite" skill. Independent tasks parallelize; `Depends on`
edges sequence. Don't rely on real concurrency for correctness (Codex may serialize).

### Simplified native plan file
Plans use the Claude Code native shape (`Context → Goal → Acceptance Criteria → Tasks → Agent
Assignment → Verification`) at a flat `.plans/{feature-name}.md`. Each task carries a lightweight
`Status` and a `Done when` line; a full Definition-of-Done checklist appears only in TDD depth.

### Main agent owns plan-file writes
Sub-agents read the plan and report status; the main agent records it — no parallel-write collision.

### Cross-tool
Both Claude Code and Codex expose the named agents used by this skill. The skill uses tool-agnostic
prose prompts (no literal call syntax); agent files define runtime/model choices. Blockers use a
**fresh agent** (no `SendMessage`/resume dependency).

## Changelog

### 2026-07-11 — v3.3.0 — Explicit unit-test and review choices
- Added independent multiple-choice planning questions for new unit tests and code review; questions
  are skipped only when request or existing plan already resolves them.
- Made new-test generation, TDD, review, review rework, and review verdict conditional on recorded
  Context flags while keeping existing build/test verification mandatory.
- Replaced automatic review fallback for non-unit-testable TDD tasks with build/manual/static checks.

### 2026-07-11 — GPT-5.6 intent routing
- Replaced the prior provider-specific implementation example with the portable `standard` intent: Claude
  resolves it to Sonnet and Codex resolves it to Terra with medium reasoning.
- Kept the main-agent runtime user-selected and kept historical runtime-routing entries intact.

### 2026-07-10 — v3.2.0 — Plan-mode parity + orchestrator verification
- **Plan-mode-parity design step**: Phase 1 now dispatches 1–3 tool-native architect agents
  (Claude Code `Plan`, Codex explorer with a design brief), scaled by complexity, with main-agent
  reconciliation before decomposition.
- **Per-task Actionability Gate**: a 5-item checklist (files confirmed, pattern read in the actual
  file, description executable by a context-free sub-agent, mechanically-checkable "Done when",
  `Depends on` stated) gates every task before it enters the plan; plans with 3+ tasks also get a
  token-lean, fresh-eyes plan quick-check before the Approval Gate.
- **Verify-before-accept**: the main agent now validates each implementer's diff and Done-when
  evidence and confirms file scope before recording `Status: complete` — mismatches route to rework
  instead of being accepted.
- **Mandatory Agent Assignment section** in the plan template (wave / task / agent / verified-by);
  waves derive from `Depends on`, and Phase 2 dispatch follows the table.
- **`code-implementer` realigned** to the dispatch contract: plan-path + task-heading input, a
  Done-when evidence report; dropped the embedded `code-review-lite` self-review and the
  `implement-plan` skill preload.

### 2026-06-30 — v3.1.1 — Use built-in explorers
- Replaced the custom `explore-agent` dependency with each tool's built-in explorer for Phase 0
  planning discovery: Claude Code `Explore`, Codex `explorer`.
- Kept Codex runtime pinning for `code-implementer` so implementation still uses the predefined
  model/effort.

### 2026-06-30 — v3.1.0 — Codex agent runtime routing (superseded)
- Temporarily added `explore-agent` for fast/read-only planning discovery; superseded by v3.1.1,
  which uses built-in explorers instead.
- Pinned Codex runtime for `code-implementer` separately from the main agent, with medium reasoning
  for implementation work.
- Added `codexModel` support to ek agent generation so source agents can carry Claude and Codex model
  settings without leaking tool-specific fields across targets.

### 2026-06-29 — v3.0.0 — Merged single skill, gated planning
- **Merged the lightweight `lite` variant into this skill and retired it.** Quota concerns are now
  handled by auto-scaling implementer count by file size — no separate single-agent skill. Removed
  the lite variant from `base-kit`, `full-kit`, and the `dev-workflow` plugin.
- **Added a hard Approval Gate.** Planning (Phases 0–1) is read-only except the plan file; scaffold,
  tests, and implementation only run after explicit user approval (ExitPlanMode in Claude Code).
- **Planning raised to plan-mode quality** — parallel explore agents for understanding, optional
  Plan agents for design, clarifying interview, then approval.
- **Default depth is Simplify** (plan→implement→verify); **TDD** (scaffold + failing tests) is now
  optional and decided during planning, not always-on.
- **Simplified, consistent plan template** in the native shape (`Context → Goal → Acceptance Criteria
  → Tasks → Verification`); removed the Meta block, per-task Contracts subfields, and Iteration Log.
- **Plans always written to a flat `.plans/{feature-name}.md`.**

### 2026-06-21 — v2.0.0 — Self-contained flagship (superseded)
- Phase 0 interview, Phase 2 scaffold, Phase 3 test-first via qa-engineer, always-on verify/review
  loop, Definition Criteria as the spine, main agent owns plan.md writes, fresh-agent blocker
  handling, absorbed `implement-feature`.

### v1.1.0 (superseded)
- Plan-as-source-of-truth; up to 3 parallel implementers; main-agent verify (build + diff + AC).
