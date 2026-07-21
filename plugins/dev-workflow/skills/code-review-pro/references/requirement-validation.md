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

## Harvest Design-Doc Context

Acceptance criteria are often terse; the authoritative requirement lives in a design document. After resolving the work item, build a richer requirement bundle:

1. Read the repo's `AGENTS.md` to find the declared **design-doc root** (a `Design docs: <path>` line, or an equivalent documented location). Resolve it dynamically from `AGENTS.md` — never assume a fixed folder name.
2. Use `.docs/ado-context.md` (maintained by the `azdevops-context` skill) to map the resolved item's parent Feature/Epic to its design-doc file(s).
3. Extract only the section matching the direct work item (by title, feature keyword/alias, or heading) and pass it alongside the AC as the **requirement bundle**.

The design-doc excerpt is **elaboration of the direct AC**, not a new source of binding criteria — the contract hierarchy below still governs. When `AGENTS.md` declares no design-doc root, or no matching section is found, fall back to AC-only context; this is non-blocking and never invents criteria.

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
- **MEDIUM**: plausible preservation risk with incomplete exposure evidence; benign unrelated scope.
- **LOW**: clarification/documentation gap without runtime impact.

Missing direct tests use the exact `use-unit-testing` advisory outside findings. Downgrade unsupported CRITICAL/HIGH claims. Put uncertainty in Notes, not fabricated evidence.
