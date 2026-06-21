---
name: design-scaffold
description: "Brainstorm to lock requirements, then scaffold structure (interfaces, signatures, flow) with no implementation. Use when stubbing out a design doc or work item before writing tests or code."
version: 1.0.0
---

# Design Scaffold

Senior-role skill for **Step 3** of the dev workflow: turn a locked design into a scaffold-only commit. You **brainstorm with the user to genuinely understand the requirement and approach**, hold a hard gate until decisions are locked, then generate **structure only** — interfaces, types, class/module layout, method signatures, and flow wiring — with **no implementation bodies**.

**You write structure, never logic.** Every method body is a non-implementing stub. Tests (Step 4) and implementation (Step 5) are done later by the developer — not here. You also do **not** commit; you leave files staged-ready for the user to review and commit.

This skill is the deliberately narrow sibling of `implement-plan` (which bundles scaffold + tests + implementation). Use this when scaffold is its own reviewable commit.

## Decision Tree — Phase 0: Resolve the source of truth

The design is the input you scaffold from. **Resolve it precisely — never guess what the user wants.**

```
Argument given?
|-- Path to a design doc / requirement.md  -> read it in full
|-- Path to a user story file              -> read its content
|-- Numeric work item ID                   -> fetch via `azdevops-operations` skill
|-- No argument                            -> look in `.docs/` for the design document(s)
|                                             |-- exactly one match  -> read it, confirm it's the right one
|                                             |-- several / ambiguous -> ask which one
|                                             |-- none found          -> ask the user for the requirement
```

After reading, post a short **"Here's what I understand"** summary and confirm it before moving on. If anything is unclear or missing, **ask — do not infer**. This input step is load-bearing for everything downstream.

## Phase 1: Brainstorm & lock (the heart of this skill)

This is the most important phase. The goal is shared, explicit understanding of **what** to build and **how** — not a guessed structure. Do not proceed to scaffold until the user confirms decisions are locked.

Interview to close the gaps that matter for structure. Ask only what the design didn't already answer:

- **Problem & scope** — what this must do, and the boundaries (what's explicitly out).
- **Key entities / data** — the nouns the code revolves around and their shapes.
- **Approach & architecture** — present 1–3 viable approaches with trade-offs, recommend one, get an explicit pick. This drives the shape of the scaffold.
- **Integration points** — what it calls, what calls it, external services, existing code to extend.
- **Contracts** — public surface, inputs/outputs, error/edge behavior the signatures must accommodate.

Surface assumptions out loud and let the user correct them. One clarifying question beats one wrong scaffold. When ready, write a concise **Locked Decisions** block:

- If you resolved from / produced a design doc, persist it to `.docs/` (e.g. `.docs/<feature>-design.md`) capturing the locked approach and contracts.
- Otherwise, post the Locked Decisions summary in-conversation.

**Gate:** ask the user to confirm "decisions locked" (or equivalent). Only then continue.

## Phase 2: Propose the scaffold shape

Detect the stack(s) from the repo (`.csproj`/`.sln` → C#; `package.json` + `.tsx` → React/TS; `pyproject.toml`/`.py` → Python). Then present the **planned structure for approval before writing**:

- File/folder tree showing where scaffold files land in the real source layout.
- Interfaces / types and the public method signatures on each.
- A short flow description: how the pieces call each other end to end.

Iterate on this outline until the user approves. Match existing project conventions (naming, folder layout, DI patterns) — read a neighboring file if unsure.

**Apply design principles as you shape it** — the scaffold is where structural quality is set (full detail in `references/design-principles.md`):

- **SOLID** — one responsibility per type (no god classes); small focused interfaces (ISP); depend on injected abstractions, not concretions (DIP); design seams for expected variation (OCP); document contracts so implementations stay substitutable (LSP).
- **DRY** — extract a shared interface/base/DTO instead of duplicating signatures.
- **KISS / YAGNI** — the simplest structure that satisfies the locked design; no speculative methods or extension points. Self-check: *"would a senior engineer call this overcomplicated?"* Every signature traces to a locked decision.
- **Per CLAUDE.md** — push back if a simpler shape exists, match existing style, and mention (don't fix) unrelated smells. Name the principle when it drives a non-obvious choice.

## Phase 3: Generate the scaffold (structure, no logic)

Write the approved structure into the real source locations. Rules for every file:

- **Signatures, not bodies.** Each method/function body is a stub idiomatic to the stack — see `references/stub-idioms.md`. C#: `throw new NotImplementedException();` · Python: `raise NotImplementedError` · TS/React: `throw new Error("Not implemented");`.
- **Document the contract, not the code.** Use XML doc / docstring / JSDoc on each member to state responsibility, params, returns, and notable edge cases — so the test author (Step 4) and implementer (Step 5) know the intent without any logic present.
- **Wire the flow by shape.** Declare dependencies, constructor params, interface implementations, and call sites — but the calls live inside stubbed bodies that throw. No control flow, no data transformation, no real returns.
- **No tests, no config logic, no TODO-disguised implementation.** A `// TODO: implement` comment is fine; actual logic is not.

## Verify Output & Hand Off (Phase 4)

Run the guardrail to confirm no implementation leaked:

```bash
scripts/verify_output.py <scaffold-path>
```

Fix any FAIL (a body with real logic and no stub marker is the main failure mode). Then hand off:

- **Do not commit.** Report the files written and tell the user they're ready to review and commit as the Step 3 scaffold commit.
- Point to what's next: Step 4 (developer writes unit tests against these signatures), Step 5 (implementation until tests pass).

## Reference

- `references/stub-idioms.md` — per-stack stub bodies, contract-doc conventions, and worked examples.
- `references/design-principles.md` — SOLID/DRY/KISS/YAGNI applied to scaffolding, plus the user's CLAUDE.md coding philosophy.

---

**Triggers:** scaffold this, create scaffold structure, stub out the design, generate interfaces/signatures with no implementation, Step 3 scaffold. **Never** write business logic, tests, or commit — brainstorm, lock, scaffold, stop.
