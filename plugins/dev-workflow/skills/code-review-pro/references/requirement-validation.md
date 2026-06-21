---
name: requirement-validation
description: Requirement context resolution and binding direct-task versus parent-context contract
---

# Requirement Validation Context

## Resolve Context

Run:

```text
python <skill-dir>/scripts/ado_work_item.py context [--pr {pr-id}] --repo {repo-root}
```

Detection order remains PR links, branch identifiers, then commit identifiers. If unresolved, inspect `.docs/ado-context.md` for a candidate. User-provided requirement text overrides inferred context.

## Contract Hierarchy

1. **Direct task/story/bug and its acceptance criteria are binding scope.**
2. **Parent Feature/Epic is explanatory context only.** Use it to understand business intent and terminology; do not turn parent outcomes into extra acceptance criteria.
3. **Repository instructions and existing behavior constrain preservation.** A direct requirement does not authorize unrelated regressions.
4. **No direct requirement means regression-only mode.** Do not invent criteria from a parent, branch name, PR title, or implementation.

## Modes

### Work-item mode

Pass direct item title, description, acceptance criteria, state, parent summary, and any user clarification. Map each direct criterion to observable evidence. Parent-only goals may be notes, never Missing/Partial findings.

### Regression-only mode

Pass changed files, diff, base reference, tests, and any intent text. Validate:

- base behavior versus new behavior
- changed symbols and signatures
- callers and consumers
- emitted/handled events
- state reads, writes, ordering, and persistence
- tests proving intended and preserved behavior
- unrelated behavior preservation

Report no fabricated AC table. Use a Behavior Preservation table instead.

## Evidence Rules

- Cite `file:line`, symbol, and execution path. A changed line alone is not fulfillment evidence.
- For Addressed, connect input/precondition through implementation to observable output/state/event.
- For Missing, prove no implementation/evidence exists in reviewed scope after search.
- For regression, show base/new difference and at least one exposed caller, consumer, event, state, or test.
- Distinguish absence of tests from a demonstrated defect.

## Severity

- **CRITICAL**: proven existing behavior break, crash/data loss, auth bypass, or contract break with exposed consumer evidence.
- **HIGH**: direct AC missing/partial; demonstrated user-visible regression; public/API/schema/event contract mismatch.
- **MEDIUM**: plausible preservation risk with incomplete exposure evidence; missing tests for changed behavior; benign unrelated scope.
- **LOW**: clarification/documentation gap without runtime impact.

Downgrade unsupported CRITICAL/HIGH claims. Put uncertainty in Notes, not fabricated evidence.
