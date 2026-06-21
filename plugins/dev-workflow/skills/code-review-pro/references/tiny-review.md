---
name: tiny-review
description: Main-agent all-lens review contract for Tiny profile code diffs
---

# Tiny Main-Agent Review

Review every changed line and enough surrounding code to prove impact. Tiny means low blast radius, not reduced rigor.

## Lenses

1. **Requirement/correctness**: compare intended or inferred behavior with implementation; if no work item exists, preserve unrelated behavior.
2. **Base/new behavior**: identify what happened before and after each behavioral change.
3. **Blast radius**: inspect changed symbols plus callers, consumers, events, and state transitions.
4. **Tests**: map behavior changes to tests; distinguish absent evidence from proven failure.
5. **Security**: input trust, authorization, secrets, injection, unsafe output/error exposure.
6. **Performance**: loops/queries, allocations, blocking async, lifecycle/resource leaks, concurrency.
7. **Design**: SOLID, DRY, KISS, ownership/layering, error handling.
8. **Standards/patterns**: explicit instructions, linter rules, and nearby exemplars.

## Evidence

- Cite `file:line`, symbol, and concrete execution path.
- Changed code is not proof of requirement fulfillment; show how behavior reaches an observable result.
- A regression claim needs a base/new behavior difference plus an affected caller, consumer, event, or state path.
- Missing tests alone is MEDIUM unless requirements explicitly demand tests; elevate only with a demonstrated uncovered failure.
- Do not invent acceptance criteria. Parent context explains intent but cannot broaden direct scope.

Use severity rules from `analysis-framework.md`. Record the main review as triggered and Requirement/specialists as skipped because profile is Tiny.
