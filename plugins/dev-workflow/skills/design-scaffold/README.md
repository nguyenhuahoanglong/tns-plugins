# Design Scaffold

## Purpose

`design-scaffold` is the senior-role skill for **Step 3** of the team dev workflow (design doc → scaffold → tests → implement → review → PR). It brainstorms with the user to lock requirements and approach, then generates **structure only** — interfaces, types, class/module layout, method signatures, and flow wiring — with every method body left as a non-implementing stub. The output is a scaffold-ready set of files the user reviews and commits; tests (Step 4) and implementation (Step 5) happen later, by the developer.

## Pain Points Addressed

- **Guessed structure.** Scaffolds built before the design is understood get reworked. This skill gates on an explicit "decisions locked" confirmation and refuses to infer when unsure.
- **Scaffold/impl bleed.** It's easy to start writing logic while stubbing. The skill enforces stub-only bodies and ships a guardrail (`verify_output.py`) that flags leaked implementation.
- **Heavy alternative.** `implement-plan` bundles scaffold + tests + implementation in one go; sometimes the scaffold needs to be its own reviewable commit. This skill fills that narrow slot.

## Design Notes

- **Input resolution is auto-detect** (chosen by user): reads a design doc from `.docs/`, a user-story file, or an ADO work item ID (via `azdevops-operations`); interviews instead of guessing when input is missing/ambiguous.
- **Does not commit** (chosen by user): writes files into the real source layout and stops, leaving staging/commit to the user / `git-skill`.
- **Brainstorm is built-in** (chosen by user): a focused requirement/approach interview tuned for scaffolding, rather than deferring to the `brainstorming` skill.
- Stub idioms per stack live in `references/stub-idioms.md`; the guardrail's logic-leak heuristics mirror that file's "violation" list.
- Sibling/related skills: `implement-plan`, `brainstorming`.

## Changelog

### 2026-06-21 - Design principles + packaging
- Added `references/design-principles.md` (SOLID/DRY/KISS/YAGNI applied to scaffolding + the user's CLAUDE.md coding philosophy) and a compact principles block in Phase 2.
- Registered the skill in `base-kit` and the `dev-workflow` team plugin (`plugins-config.json`).
- Why: scaffolding is where structural quality is decided; the skill must enforce design principles, and it belongs in the shared dev kits.

### 2026-06-21 - Initial
- Created skill: Design Scaffold (Step 3 of the dev workflow visualized in the "Process workflow visualization" session).
- Motivation: user wanted a dedicated skill that brainstorms to lock requirements + approach, then produces a scaffold-only commit (methods/interfaces/flow, no implementation).
- Files: SKILL.md, references/stub-idioms.md, scripts/verify_output.py (+ tests), evals/evals.json.
- Key decisions: auto-detect design input from `.docs/`/user story/work item; built-in interview; write files but never commit.
