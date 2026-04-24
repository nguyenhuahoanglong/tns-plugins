# Plan Feasibility Analysis

Checklist for Phase 1.2 — verify the plan is implementable before dispatching code-implementers. This analysis is what makes implement-plan more than a blind dispatcher.

## Quick Assessment (30 seconds)

Read the plan and answer:

1. **Can I identify specific files to modify?** → If no, plan is too vague
2. **Can I describe what each file change does?** → If no, plan lacks detail
3. **Is the scope ≤ 8 files?** → If no, suggest `implement-feature`

If all three pass, proceed to detailed checks. If any fail, trigger interview or redirect.

## Detailed Feasibility Checks

### 1. File Existence

**Verify that target files actually exist.** Plans can reference files that were renamed, moved, or deleted since the plan was written.

- Glob for each file path mentioned in the plan
- If a file doesn't exist, check: Was it renamed? Moved? Is it a new file to create?
- Flag any mismatches — this is the most common reason plans are stale

### 2. Pattern Validity

**Verify that the codebase patterns the plan assumes still hold.**

Examples of assumptions that go stale:
- "Add to the existing service layer" — but the service layer was refactored into CQRS
- "Follow the UserController pattern" — but UserController was rewritten
- "Add a migration" — but the migration framework changed
- "Use the shared utility" — but it was deprecated or renamed

Check by reading the referenced files/patterns, not just trusting the plan text.

### 3. Change Concreteness

Each planned change should map to:
- A specific file (existing or new)
- A specific action (add function, modify class, create file, update config)
- A clear outcome (what the code should do after the change)

If a change is described abstractly ("improve error handling", "add proper validation"), ask: **Where specifically? What errors? What validation rules?**

### 4. Dependency Ordering

Check if tasks have ordering constraints:

| Pattern | Implication |
|---------|------------|
| Task B imports from files created in Task A | Task A must complete first (sequential) |
| Task A modifies a shared interface | All tasks using that interface depend on A |
| Tasks touch completely separate files | Safe to parallelize |
| Tasks touch same file | Must be merged into one task |

If dependencies exist, adjust Phase 2 dispatch: run dependent tasks sequentially (dispatch first, wait, then dispatch second), or merge them into a single task.

### 5. Scope Accuracy

Compare the plan's stated scope against reality:

- Plan says "modify 3 files" but the feature actually touches 6 → plan is incomplete
- Plan lists files that don't need changes → plan is outdated
- Plan misses test files → check if project conventions require tests

Use `Explore` agent if needed to verify scope against the actual codebase.

## Interview Decision Tree

```
Plan analyzed →
  ├─ All checks pass → Proceed to decomposition (no interview)
  ├─ 1-2 gaps found → Ask 1-2 targeted questions
  │   Examples:
  │   - "Plan references UserService.cs but it's now UserCommandHandler.cs. Should I update the plan to use the new name?"
  │   - "Plan doesn't mention tests. Should I include unit tests for the new endpoint?"
  ├─ 3+ gaps found → "This plan needs more detail. Consider fleshing it out or using /implement-feature."
  └─ Plan is fundamentally wrong → "This plan doesn't match the current codebase state. [specific reasons]. Want to re-plan?"
```

## Analysis Output

After completing the analysis, you should have a clear mental model of:

1. **Task list** — each task with files, actions, and ACs
2. **Execution order** — which tasks can parallelize, which must sequence
3. **Risk areas** — where the plan is weakest or most likely to need guidance
4. **Agent count** — how many code-implementers to dispatch

This mental model drives Phase 2 dispatch. You don't need to write it to a file — it lives in your context for this session.
