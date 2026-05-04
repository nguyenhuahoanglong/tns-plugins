# Implement Plan Lite

## Purpose

Lightweight single-agent implementation skill for Claude Pro users. Executes an existing plan file using exactly one sonnet code-implementer, with inline orchestration and verification — no parallel dispatch, no ADO integration. Designed to run repeatedly within a single quota window. Use for plans covering up to 6 files where you already have a plan file on disk.

## Pain Points

- **Pro quota burn** — the original `implement-plan` skill dispatches 2-4 agents per run (up to 3 implementers + optional exploration). On Claude Pro's 5-hour message quota, a few full runs exhaust the window.
- **Inline-text plans waste dispatches** — accepting free-form descriptions and prompting for clarification costs messages before any implementation starts.
- **ADO dependency on Pro** — fetching work items over ADO consumes a tool round-trip and requires network/auth that may not be available in lightweight sessions.
- **No strict input gate** — without a mandatory plan file, the orchestrator can end up interviewing the user instead of implementing, burning quota on planning when the user expected execution.

## Design Notes

### Single sonnet agent

One code-implementer handles the full scope. No decomposition step, no parallel dispatch. This keeps dispatch cost to 1 message regardless of plan size (up to the 6-file cap). Blocker resolution uses SendMessage to the same agent, preserving context without spawning a second agent.

### Strict input contract

A plan file is mandatory. Inline text and work item IDs are explicitly rejected at Phase 1 with redirect messages. This prevents the skill from silently degrading into a planning session.

### Plan-quality gate

Before dispatching, the skill verifies the plan has: a stated goal, an explicit file list, and acceptance criteria or verification steps. Any missing item triggers a hard stop. No interview, no partial proceed — this keeps the pattern lean and quota-efficient.

### No opus

The orchestrator runs at whatever model is active in the session (sonnet on Pro). Opus is not invoked. Gate reasoning and AC verification are simple enough that sonnet handles them well for plans in the 1-6 file range.

## Changelog

### 2026-04-26 - v1.1.0 — Plan-as-source-of-truth

- Phase 1.5 added: ensure plan has `Status` fields per task; auto-augment if missing
- Implementer now reads plan.md from disk and updates its task `Status` field (`pending` → `in-progress` → `complete`/`blocked`) so progress is durable and visible between runs
- Phase 3 reads plan.md to verify all tasks complete before declaring done; updates AC checkboxes and Meta Status
- Implementer prompt template references plan path instead of inlining plan context

### 2026-04-24 - Initial creation

- New skill: lightweight single-agent implementer for Claude Pro sessions
- Strict input contract: plan file required; inline text and ADO IDs rejected
- Plan-quality gate: goal + file list + ACs/verification — any missing stops execution
- Scope cap: 6 files; larger plans redirected to `implement-feature`
- Single sonnet dispatch with SendMessage retry on blocker; fresh agent on build failure
- References: `implementer-prompt.md` with Context Sizing, Dispatch, Blocker, and Build-Failure templates
