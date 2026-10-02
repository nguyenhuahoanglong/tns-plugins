# Plan Template

Use for medium/large work or the optional consistency helper. Trim irrelevant sections. Small work can
use one task block. Extra fields are allowed. The host's readable equivalent is equally valid.

```markdown
# Plan: <Outcome>

## Context
Plan path: <canonical path>
Unit tests: selected
Unit tests source: assessment
Unit tests reason: <behavior/risk covered, or why new tests are skipped>
Code review: selected
Code review source: assessment
Code review reason: <risk and selected route>
Approval: <pending, or actual user approval source and scope>
Execution boundary: <local implementation through verification; separately authorized external actions>

## Goal
<Observable outcome, scope and non-goals.>

## Global Constraints
<Compatibility, protected work, security, allowed local/external actions, and cost limits.>

## Acceptance Criteria
- [ ] AC-1: <observable result>

## Readiness
| Need | Evidence/decision | State | Recovery / affected tasks |
|---|---|---|---|
| E2E target and build | <exact target and build verification method> | <ready / pending / N/A with reason> | <Task N> |
| Auth and account role | <protected read through actual browser/runner, no secrets> | <state> | <permitted refresh or stop> |
| Test data and cleanup | <allowed mutations, fixture, cleanup> | <state> | <owner> |
| Test/review decisions | <cases, owner, route and actual consent> | <state> | <possible pause> |

## Tasks

### Task 1: <Outcome>
- Status: pending
- Depends on: none
- Files: `src/example.ts`, `tests/example.test.ts`
- Description: <behavior, constraints, implementation role; allowed create/modify/delete scope>
- Done when: <specific command/result or observable evidence>
- ACs: AC-1
- Model / effort: <intended selection and supported fallback>
- Decision latitude: <details worker may settle without asking>

## Agent Assignment
| Wave | Task(s) | Agent | Model / effort | Why | Fallback |
|---|---|---|---|---|---|
| 1 | Task 1 | code-implementer | <live selectable model/effort> | <task fit> | <within approved cost/scope> |

## Verification
- Build: `<exact command>` (or N/A with concrete reason)
- Existing tests: `<exact command>` (or N/A with concrete reason)
- E2E: <cases, target, runner, permitted data, evidence>
- Code review: Reviewer: code-reviewer; scope: <changed files>; <genuine consent/session prerequisites>
- Completion evidence: <results to capture per AC>

## Execution policy
<Default: one fresh substantive-blocker retry; at most two selected-review rework loops.
Continue independent work when blocked. Escalate only new material decisions/authority or human auth.
Do not commit, publish, deploy, or expand external writes without existing authorization.>
```

When TDD is useful, add `Depth: TDD` and `TDD reason: <risk>` to the task. Record baseline/RED/GREEN
evidence where it matters; `Mode`, scaffold choreography, and fixed agent counts are not mandatory.

When using the typed preflight script, add this separate section. Task `Files:` are comma-separated
exact paths for derived probes; bounded-module prose belongs in Description instead. Copy each derived
result from the real run. Do not leave placeholders or illustrative ready results in an approved plan.

```markdown
## Preflight
| ID | Kind | Target | Expect | Blocks |
|---|---|---|---|---|
| PF-1 | command | `node` | resolves on PATH | Task 1 |

### Preflight results
Run: <actual command and time>
- PF-1 <ready|blocked|unverifiable>: <actual output; Fallback: required if unverifiable>
- derived path Task 1 `src/example.ts` <state>: <actual output>
- derived path Task 1 `tests/example.test.ts` <state>: <actual output>
Autonomy: <aggregate from recorded results>
```

Task status: pending, in-progress, complete, blocked; legacy scaffolded remains readable.
Complete means main verified Done when. A worker report alone means awaiting verification, not complete.
