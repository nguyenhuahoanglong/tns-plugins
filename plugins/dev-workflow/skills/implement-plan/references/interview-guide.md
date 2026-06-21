# Interview Guide (lean, criteria-focused)

Phase 0 interview. **Lean by design: 1–2 rounds, ~5 questions max.** Skip anything the input already answers. The goal is not exhaustive requirements gathering — it is to lock enough scope, design, and especially **verifiable criteria** (see `definition-criteria.md`) to write a parallel-ready plan.

If the input is already a complete plan with per-task Definition of Done, skip the interview entirely.

## What every interview must end with

Before planning, you must be able to state all of:
1. **Scope** — what's in, what's explicitly out.
2. **Design** — where the code lives, patterns/contracts to follow.
3. **Acceptance Criteria** — testable conditions for the whole feature.
4. **Definition of Done per task** — mechanically checkable assertions.

If any is "I'm not sure," ask one more targeted question. If you'd need **more than ~5 questions across 2 rounds**, the request is too open for this skill — tell the user it needs to be scoped down, or capture the answers and proceed with explicit assumptions stated back to them.

## Question bank (pick the few that matter)

**Scope & purpose**
- What problem does this solve, and what's the smallest change that solves it?
- What is explicitly out of scope / must NOT be touched?

**Design & contracts**
- Where should this live — new module or extend existing? Any pattern to follow?
- What are the key signatures/interfaces? (inputs → outputs, endpoint shapes) — *needed for the scaffold step.*
- Any libraries/services to use or avoid? Backward-compat constraints?

**Criteria (spend most of the budget here)**
- How will you verify this works? Give concrete input → expected output examples.
- What are the error/edge scenarios, and what should happen for each?
- What's the bar for "done"? (specific tests pass, build clean, no warnings)
- Which parts are genuinely unit-testable vs. config/UI that only a review can check?

## Technique

- **Round 1** — ask the 3–5 highest-value questions, weighted toward criteria. Listen for implicit assumptions.
- **Round 2 (only if needed)** — fill gaps the answers exposed; confirm contracts and that each task's Definition of Done is concrete and checkable.
- **Confirm** — state scope + ACs + per-task DoD back to the user, get explicit sign-off, then go autonomous.

Translate every answer into a criterion, not prose. "It should be fast" → "responds in <200ms for 1k rows." If it can't be made checkable, it isn't done criteria yet.
