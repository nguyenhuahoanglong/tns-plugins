# Plan Exploration, Feasibility & Decomposition

This is the engine behind Phase 0 (understand) and Phase 1.1 (decompose) — it carries the same rigor
Claude Code plan mode applies before it writes a plan. All of it is **read-only**; the only write in
Phase 1 is the plan file itself.

## Phase 0 — Exploration depth (how many explorer agents)

Match plan mode's heuristic: **use the minimum number of tool-native explorer agents that covers the
scope, up to 3 in parallel.** Claude Code uses built-in `Explore`; Codex uses built-in `explorer`.

| Situation | Explorer agents |
|---|---|
| Change is isolated to known files, or the user gave specific paths | **1** |
| Scope is uncertain, or several subsystems/areas are involved | **2–3, in parallel** (one search focus each) |

When you do fan out, give each agent a distinct focus — e.g. one finds existing implementations to
reuse, one maps related components, one surveys testing/convention patterns. Quality over quantity:
3 is the cap, 1 is the common case. Distil their findings into per-task "patterns to follow" so the
implementers don't each re-explore.

## Phase 0 → Phase 1 — Read the critical files yourself

Before finalizing the decomposition, **read the critical files the explorer agents flagged** — don't
plan off their summaries alone. This is plan mode's review step: open the files you'll modify and the
ones you'll pattern-match against, confirm the signatures/patterns are really as reported, and only
then commit to the task breakdown. This is what separates a plan that executes cleanly from one that
turns out to be built on a stale assumption.

## Quick assessment (30 seconds)

1. **Quality decisions resolved?** Apply `quality-assessment.md`; ask only evidence gaps/conflicts.
2. **Can I name specific files for every change?** If no → return to Phase 0.
3. **Does every task have a "Done when"?** If no → not ready (see `definition-criteria.md`).
4. **Is scope manageable?** ≤9 files → normal dispatch; 10+ → dependency-ordered batches.
5. **Has every task passed the Actionability Gate?** If no → not ready (see below).
6. **Type-consistency:** does every symbol mentioned in more than one task have the identical name
   and signature everywhere? (`clearLayers()` in Task 3 vs `clearFullLayers()` in Task 7 is a plan
   bug.) If no → fix the mismatched task(s) before writing the plan.
7. **Placeholder scan:** search draft for "TBD", "TODO", "appropriate", or "similar to Task N".
   Any hit fails the check — resolve it before writing the plan.
8. **Output contract:** run `scripts/verify_output.py` before approval.

## Per-task Actionability Gate

Apply this checklist to EVERY task before writing it into the plan file. A task enters the plan only
when ALL five pass — a task you cannot verify as actionable does not go in the plan; resolve it first.

1. **Files confirmed.** Every file the task touches is named and confirmed to exist via glob/read —
   or, for a new file, explicitly marked "new file" with its target folder confirmed.
2. **Pattern verified.** The pattern/signature the task follows was verified by reading the actual
   file — not assumed from an explorer summary.
3. **Zero-context executable.** The description is executable by a sub-agent with zero conversation
   context, from the plan text alone — concrete names, paths, signatures. No "appropriately", "as
   needed", "handle properly", or other vague hand-waving.
4. **Mechanically checkable "Done when."** See `definition-criteria.md` — a human or agent can verify
   it without judgment calls.
5. **`Depends on` stated.** Either a specific task edge or "none" — never left blank.

Any item fails → the task is not ready. Go back and resolve it (re-explore, re-read the file, tighten
the wording) before writing the task into the plan.

## Design via Plan agents

Scale the design step to the change, same discipline as explorer scaling:

| Scope | Plan agents |
|---|---|
| Trivial (typo, rename, 1-file change) | **0** — skip; design directly, no agent dispatch |
| Standard | **1** architect agent |
| Complex / multi-area | **Up to 3**, in parallel, each with a distinct perspective (e.g. minimal-change vs clean-architecture vs risk-first) |

Claude Code dispatches the built-in `Plan` agent; Codex dispatches an explorer sub-agent given a
design brief (same read-only rigor, no built-in Plan agent available). When more than one agent runs,
the main agent reconciles the proposals into ONE approach and owns the final decision — proposals
inform the plan, they don't get merged verbatim or left as open options.

## Feasibility checks

### 1. File existence
Glob/grep for each file the plan touches. A referenced file that was renamed, moved, or deleted is the most common staleness — flag and reconcile before scaffolding.

### 2. Pattern validity
Verify the patterns the design assumes still hold (the service layer wasn't refactored to CQRS, the utility wasn't deprecated, the controller you're copying still looks that way). Read the referenced files; don't trust assumptions.

### 3. Contract concreteness
Pin each task's key signatures (name, inputs, return type) rather than leaving them vague ("add a
helper"). In **TDD depth** these become the scaffold stubs and the surfaces the failing tests bind
to; in default depth they keep the implementer's scope unambiguous.

### 4. Decompose by feature slice
Group by logical slice, not by layer:
- ✅ "Add GetUsers endpoint" → controller + service + test in one task.
- ❌ "All controllers" / "All services" / "All tests" as separate tasks.

### 5. File isolation + dependency ordering
| Pattern | Implication |
|---|---|
| Tasks touch completely separate files | Independent → parallelize |
| Task B imports a contract Task A creates | B `Depends on` A → sequence |
| Task A changes a shared interface | All consumers depend on A |
| Two tasks must touch the same file | Merge them into one task |

Record `Depends on` per task. The dispatch in Phase 2 parallelizes within an independent set and sequences across edges. **File isolation prevents file collisions; `Depends on` prevents logical ones.** Don't rely on real concurrency for correctness (Codex may serialize) — the ordering must be correct even if everything runs sequentially.

## Output of this analysis

A clear model you can write straight into `plan-template.md`:
1. **Task list** — each with files, description, "Done when", ACs (plus a Definition of Done in TDD depth).
2. **Dependency graph** — which tasks parallelize, which sequence.
3. **Agent count** — per auto-scale contract in `SKILL.md`.

This drives implementation and verification. It lives in the plan file, not just your context — and
nothing is built until the user approves it at the Approval Gate.
