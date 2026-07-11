# Interview Guide (lean, criteria-focused)

Phase 0 interview — the clarifying-question step, like the questions Claude Code plan mode asks
before writing a plan. **Lean by design: 1–2 rounds, ~5 questions max.** Skip anything the input
already answers. The goal is not exhaustive requirements gathering — it is to lock enough scope,
design, and **verifiable criteria** (see `definition-criteria.md`) to write the plan. Its output
feeds the **plan file**, not code — no implementation happens until the plan is approved.

If input already answers a topic, do not ask it again. Existing plans may skip scope/design/criteria
questions, but they skip preference questions only when both exact Context flags are present.

## Required implementation preferences

Resolve these two choices independently before creating or rewriting any plan. Use the tool's
multiple-choice question UI; do not ask as open text. Ask only unresolved choices, in one prompt
when both are missing:

1. **Write unit tests?** — `No (Recommended)` or `Yes — use TDD flow`.
2. **Run code review?** — `No (Recommended)` or `Yes — use code-review-lite`.

An explicit request/decline in the initial input, an existing plan's exact Context flag, or a
multiple-choice selection resolves that choice. Ambiguous wording does not. Plan creation stays
blocked until both resolve. These two fixed preference questions do not count against the lean
criteria-question budget.

## What every interview must end with

Before planning, you must be able to state all of:
1. **Scope** — what's in, what's explicitly out.
2. **Design** — where the code lives, patterns/contracts to follow.
3. **Acceptance Criteria** — testable conditions for the whole feature.
4. **"Done when" per task** — a mechanically checkable bar (a full Definition of Done only when TDD
   depth is chosen).
5. **Implementation preferences** — unit tests and code review each explicitly requested or not
   requested.

If any is "I'm not sure," ask one more targeted question. If you'd need **more than ~5 questions across 2 rounds**, the request is too open for this skill — tell the user it needs to be scoped down, or capture the answers and proceed with explicit assumptions stated back to them.

## Question bank (pick the few that matter)

**Scope & purpose**
- What problem does this solve, and what's the smallest change that solves it?
- What is explicitly out of scope / must NOT be touched?

**Design & contracts**
- Where should this live — new module or extend existing? Any pattern to follow?
- What are the key signatures/interfaces? (inputs → outputs, endpoint shapes) — *needed if TDD depth is chosen (the scaffold step).*
- Any libraries/services to use or avoid? Backward-compat constraints?

**Criteria (spend most of the budget here)**
- How will you verify this works? Give concrete input → expected output examples.
- What are the error/edge scenarios, and what should happen for each?
- What's the bar for "done"? (build clean, no warnings, specific behavior/tests)

## Technique

- **Round 1** — ask the 3–5 highest-value questions, weighted toward criteria. Listen for implicit assumptions.
- **Round 2 (only if needed)** — fill gaps the answers exposed; confirm each task's "Done when" is concrete and checkable.
- **Hand off to planning** — only after both implementation preferences resolve, answers feed Phase
  1, which writes the plan file. The user's
  explicit sign-off comes later, at the **Approval Gate** (after the plan is written), not here.

Translate every answer into a criterion, not prose. "It should be fast" → "responds in <200ms for 1k rows." If it can't be made checkable, it isn't done criteria yet.
