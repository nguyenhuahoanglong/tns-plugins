# Plan Feasibility & Decomposition

Phase 1.1 — turn the understanding (from Phase 0) into a concrete, parallel-ready task list. This
analysis is what makes the plan executable rather than aspirational. All of it is **read-only**; the
only write in Phase 1 is the plan file itself.

## Quick assessment (30 seconds)

1. **Can I name specific files for every change?** If no → the design isn't locked; go back to Phase 0.
2. **Does every task have a "Done when"?** If no → not ready (see `definition-criteria.md`).
3. **Is the scope manageable?** ≤9 files → dispatch normally; 10+ → dependency-ordered batches.

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
3. **Agent count** — per the Phase 1.3 auto-scale table.

This drives implementation and verification. It lives in the plan file, not just your context — and
nothing is built until the user approves it at the Approval Gate.
