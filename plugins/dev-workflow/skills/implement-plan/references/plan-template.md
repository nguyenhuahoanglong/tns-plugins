# Plan Template

Main agent owns status edits. Apply the path matrix in `quality-assessment.md`; task headings are unique.

```markdown
# Plan: {Feature Name}

## Context
Plan path origin: {existing-input|backlog-requirement|generated-project-root}
Plan path evidence: {non-empty supplied input or project-root basis}
TDD recommendation: {recommended|not-recommended}
TDD recommendation reason: {non-empty trigger/evidence, risk, and effort}
TDD decision: {selected|skipped}
Unit tests: {selected|skipped}
Unit tests source: {user|auto-assessment}
Unit tests reason: {non-empty final decision reason}
Code review recommendation: {recommended|not-recommended}
Code review recommendation reason: {non-empty trigger/evidence, risk, and effort}
Code review decision: {selected|skipped}
Code review: {selected|skipped}
Code review source: {user|auto-assessment}
Code review reason: {non-empty final decision reason}
Depth: {TDD|simplify}

## Goal
{Outcome understandable without the original conversation.}

## Global Constraints
{Project rules, compatibility constraints, protected paths, and non-goals.}

## Acceptance Criteria
- [ ] AC-1: {observable result}

## Tasks

### Task 1: {Descriptive Name}
- Status: pending
- Depends on: none
- Files: `path/to/file`
- Risk: {routine|risky}
- Risk reason: {trigger or routine justification}
- Depth: {simplify|TDD}
- Mode: {existing-method|simple-new|complex-backbone}
- Existing-method baseline: {exact existing suite command/result, or not applicable}
- Scaffold: {named signatures/control-flow wiring, or not applicable}
- Description: {specific behavior and compatibility}
- Done when: {mechanical command or observable evidence}
- ACs: AC-1
```

Top-level Depth is TDD iff `TDD decision`/`Unit tests` is selected. Task TDD is only risky and
user-approved; mixed plans retain simplify for routine tasks. `simple-new` scaffolds only at TDD depth;
simplify implements directly. `existing-method` uses baseline/characterization GREEN, changed/new RED,
then GREEN. `complex-backbone` keeps `design-backbone` locks, verified handoff, same-task resume, and no
duplicate tests. Preserve user and legacy explicit choices; a modern auto-assessment selection requires
consent before execution.

## Agent Assignment

```markdown
| Wave | Task(s) | Agent | Verified by main agent |
|---|---|---|---|
| 1 | Task 1 | code-implementer | diff plus Done-when evidence |
```

## Verification

- Build: `{exact command}`
- Existing tests: `{exact command}`
- TDD tests (only user-approved risky tasks): `{exact command}`
- Code review (only selected): `code-review-lite` over changed files
- Manual/static checks: {specific check}

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `scaffolded` | TDD signature/stub only |
| `in-progress` | Implementer active |
| `complete` | Main agent verified Done-when |
| `blocked` | Retry exhausted |

Every task needs files, dependency, exact fields, concrete description, Done when, and AC mapping.
