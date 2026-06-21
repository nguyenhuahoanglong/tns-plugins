# Implement Plan

## Purpose

The flagship implementation skill. Self-contained and tool-agnostic: it interviews the user to lock **verifiable criteria**, writes a parallel-ready plan to `.plans/`, scaffolds the contracts, generates failing tests, dispatches parallel implementers that must make those tests pass, then runs a verification + review guardrail loop. It does **not** depend on Claude Code plan mode or any Codex planning step — it does its own planning — and runs identically in both tools.

## When to use

- Any feature/change where you want planning + test-driven implementation in one flow.
- Use `/implement-plan "<idea>"` (Claude Code) or `$implement-plan "<idea>"` (Codex), or pass a requirement file / work-item id / existing plan / nothing.

## Skill family

| Skill | Role |
|---|---|
| **implement-plan** | Flagship: interview → plan → scaffold → test-first → parallel implement → verify/review loop. |
| **implement-plan-lite** | Quota-cheap single-shot. Requires an existing plan file; one implementer; no loop; optional review. |
| ~~implement-feature~~ | **Removed from distribution.** See below. |

### Why implement-feature was removed

`implement-feature` originally existed as the "interview + autonomous lifecycle" tier, distinct from
implement-plan's "execute an existing plan" tier. Once implement-plan v2 absorbed the interview,
test-first, and optional docs-sync steps, the two skills overlapped almost entirely — keeping both
meant maintaining two near-identical orchestrators and forcing users to pick between confusingly
similar options.

So implement-feature was **dropped from `base-kit`, `full-kit`, and the `dev-workflow` plugin** — it is
no longer installed anywhere. A thin redirect stub remains in source only, to point any lingering
`/implement-feature` habit at implement-plan. The skill family is now just **implement-plan**
(full, self-contained) and **implement-plan-lite** (single-shot). In the `dev-workflow` plugin,
implement-feature was replaced by **implement-plan** so the team kit still ships the full
plan/implement/review loop.

## Design notes

### Definition Criteria are the spine
Two verifiable-by-construction levels — plan-level Acceptance Criteria and per-task Definition of Done (mechanically checkable assertions). The interview's main job is to extract them; tests, the implementer's done-signal, and the guardrail all read from them. See `references/definition-criteria.md`.

### Scaffold exception
The main agent never writes production *logic*, but it does write the **scaffold** (interfaces/signatures/empty stubs) in Phase 2. This makes the generated tests compile (true red) and lets parallel implementers integrate against shared surfaces instead of guessing.

### Test-first
qa-engineer (via the `unit-testing` skill) writes failing tests before implementation. An implementer's task isn't done until its scoped tests are green. Untestable tasks (config/infra/UI) fall back to a review-only gate.

### Main agent owns plan.md writes
Sub-agents read the plan and report status; the main agent records it. This removes the parallel-write collision that earlier versions hand-waved.

### Cross-tool
Both Claude Code and Codex expose `code-implementer` / `code-reviewer` / `qa-engineer`. The skill uses tool-agnostic prose prompts (no literal call syntax), never hardcodes a model tier, resolves blockers with a **fresh agent** (no `SendMessage`/resume dependency), and relies on `Depends on` ordering rather than real concurrency.

## Changelog

### 2026-06-21 — v2.0.0 — Self-contained flagship
- Added Phase 0 interview (lean, criteria-focused) — no longer depends on plan mode; same usage in Claude Code and Codex.
- Added Phase 2 scaffold (main agent, signatures/stubs only) and Phase 3 test-first via qa-engineer + `unit-testing`.
- Definition Criteria model (plan-level ACs + per-task Definition of Done) as the verification spine; new `references/definition-criteria.md`.
- Phase 5 always-on verify + review guardrail loop (code-review-lite), capped at 2 iterations.
- Plan template gains Contracts, Definition of Done, `Depends on`, and `Unit-testable` fields.
- Main agent owns all plan.md status writes (fixes parallel-write collision).
- Blocker handling switched from `SendMessage` to fresh-agent dispatch; all dispatch prompts made tool-agnostic; dependency-ordered dispatch added.
- Absorbed `implement-feature` (interview + optional docs-sync). implement-feature removed from `base-kit`, `full-kit`, and the `dev-workflow` plugin (replaced by `implement-plan` there); only a redirect stub remains in source.

### v1.1.0 (superseded)
- Plan-as-source-of-truth; up to 3 parallel implementers; main-agent verify (build + diff + AC).
