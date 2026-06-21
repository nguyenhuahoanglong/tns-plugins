# Plan Feasibility & Decomposition

Phase 1.1 — turn the locked criteria (from Phase 0) into a concrete, parallel-ready task list. This analysis is what makes the plan executable rather than aspirational.

## Quick assessment (30 seconds)

1. **Can I name specific files for every change?** If no → the design/contracts aren't locked; go back to Phase 0.
2. **Does every task have a Definition of Done?** If no → not ready (see `definition-criteria.md`).
3. **Is the scope manageable?** ≤9 files → dispatch normally; 10+ → dependency-ordered batches.

## Feasibility checks

### 1. File existence
Glob/grep for each file the plan touches. A referenced file that was renamed, moved, or deleted is the most common staleness — flag and reconcile before scaffolding.

### 2. Pattern validity
Verify the patterns the design assumes still hold (the service layer wasn't refactored to CQRS, the utility wasn't deprecated, the controller you're copying still looks that way). Read the referenced files; don't trust assumptions.

### 3. Contract concreteness
Each task must expose concrete **contracts** (signatures/interfaces) — these are what Phase 2 scaffolds and what Phase 3 tests bind to. If a contract is vague ("add a helper"), pin the signature now: name, inputs, return type.

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

Record `Depends on` per task. The dispatch in Phase 4 parallelizes within an independent set and sequences across edges. **File isolation prevents file collisions; `Depends on` prevents logical ones.** Don't rely on real concurrency for correctness (Codex may serialize) — the ordering must be correct even if everything runs sequentially.

## Output of this analysis

A clear model you can write straight into `plan-template.md`:
1. **Task list** — each with files, contracts, Definition of Done, ACs, unit-testable flag.
2. **Dependency graph** — which tasks parallelize, which sequence.
3. **Agent count** — per the Phase 1.2 table.

This drives Phases 2–5. It lives in the plan file, not just your context.
