# Implement Plan

## Purpose

The single planning + implementation skill. Self-contained and tool-agnostic: it understands the
codebase to **Claude Code plan-mode quality**, interviews the user to lock verifiable criteria,
writes a simplified plan to `.plans/`, **stops for explicit approval**, then — and only then —
dispatches auto-scaled implementers and runs a verification + review pass. It does **not** depend on
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
Phase 0  Understand        (READ-ONLY)  tool-native explorer + lean interview
Phase 1  Design & plan     (READ-ONLY except the plan file)  decompose, auto-scale, write .plans/{feature}.md
───────  APPROVAL GATE  ──────────────  nothing else is written until the user approves
Phase 2  Implement         scaffold + red tests (TDD depth only) → auto-scaled code-implementers
Phase 3  Verify            build/test/diff + optional code-review-lite (cap 2 loops) + AC check
Phase 4  Report            (+ optional docs-sync for structural changes)
```

## Design notes

### No changes before approval
Planning is read-only except the plan file itself — like Claude Code plan mode, where the plan file
is the only editable artifact. Scaffold, tests, and all implementation happen strictly after the
user approves the plan at the Approval Gate.

### Default Simplify, optional TDD
Default depth is **plan → implement → verify**. **TDD depth** (main agent scaffolds stubs, then a
qa-engineer writes failing tests before implementation) is opt-in, chosen during planning for
logic-heavy, unit-testable work and recorded in the plan's Context.

### Agent routing
Planning uses the tool-native explorer (`Explore` in Claude Code, `explorer` in Codex) for read-only
codebase discovery. Implementation uses `code-implementer`, pinned separately from the main agent
(Codex: `gpt-5.5` + medium reasoning).

### Auto-scaled implementers
Implementer count scales by file count (1–3→1, 4–6→2, 7–9→3, 10+→dependency-ordered batches), so
small plans run lean without a separate "lite" skill. Independent tasks parallelize; `Depends on`
edges sequence. Don't rely on real concurrency for correctness (Codex may serialize).

### Simplified native plan file
Plans use the Claude Code native shape (`Context → Goal → Acceptance Criteria → Tasks →
Verification`) at a flat `.plans/{feature-name}.md`. Each task carries a lightweight `Status` and a
`Done when` line; a full Definition-of-Done checklist appears only in TDD depth.

### Main agent owns plan-file writes
Sub-agents read the plan and report status; the main agent records it — no parallel-write collision.

### Cross-tool
Both Claude Code and Codex expose the named agents used by this skill. The skill uses tool-agnostic
prose prompts (no literal call syntax); agent files define runtime/model choices. Blockers use a
**fresh agent** (no `SendMessage`/resume dependency).

## Changelog

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
