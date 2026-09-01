# Plan Template

Main agent owns every status edit. Apply the path resolution in `plan-contract.md`; task headings are
unique. Field sets are exact — see `plan-contract.md` for which conditional fields apply.

```markdown
# Plan: {Feature Name}

## Context
Plan path: {canonical path}
Plan path origin: {host-plan-mode|existing-input|backlog-requirement|generated-project-root}
Plan path evidence: {supplied input, promoted host draft path, or project-root basis}
Unit tests: {selected|skipped}
Unit tests source: {user|flag}
Unit tests reason: {non-empty decision reason}
Code review: {selected|skipped}
Code review source: {user|flag}
Code review reason: {non-empty decision reason}

## Goal
{Outcome understandable without the original conversation.}

## Global Constraints
{Project rules, compatibility constraints, protected paths, and non-goals.}

## Acceptance Criteria
- [ ] AC-1: {observable result}

## Preflight

| ID | Kind | Target | Expect | Blocks |
|---|---|---|---|---|
| PF-1 | command | `pac` | resolves on PATH | Task 2 |
| PF-2 | auth | `pac-org` | non-interactive success | Task 2 |
| PF-3 | node-deps | `src/pcf/package.json` | devDependencies installed | Task 2 |

### Preflight results
Run: {ISO timestamp} scripts/preflight.py
- PF-1 ready: {resolved absolute path}
- PF-2 ready: {non-interactive check succeeded}
- PF-3 ready: {all declared dependencies present}
- derived path Task 1 `path/to/file`: ready
Autonomy: verified-ready

## Tasks

### Task 1: {Descriptive Name}
- Status: pending
- Depends on: none
- Files: `path/to/file`
- Mode: {existing-method|simple-new|complex-backbone}
- Description: {specific behavior and compatibility}
- Done when: {mechanical command or observable evidence}
- ACs: AC-1

### Task 2: {TDD Task Name}
- Status: pending
- Depends on: Task 1
- Files: `path/to/other`
- Mode: existing-method
- Depth: TDD
- TDD reason: {why this behavior needs a failing test first}
- Existing-method baseline: {exact existing suite command and result}
- Description: {specific behavior and compatibility}
- Done when: {mechanical command or observable evidence}
- ACs: AC-1

## Agent Assignment

| Wave | Task(s) | Agent | Verified by main agent |
|---|---|---|---|
| 1 | Task 1 | code-implementer | diff plus Done-when evidence |
| 2 | Task 2 | qa-engineer then code-implementer | RED then GREEN plus diff |

## Verification

- Build: `{exact command}`
- Existing tests: `{exact command}`
- TDD tests (only when Unit tests is selected): `{exact command}`
- Code review (only when selected): `code-review-lite` over changed files, `Escalation Policy: ask`
- Manual/static checks: {specific check}

| Status | Meaning |
|---|---|
| `pending` | Not started |
| `scaffolded` | TDD signature or stub only |
| `in-progress` | Implementer active |
| `complete` | Main agent verified Done-when |
| `blocked` | Retry exhausted or preflight prerequisite unmet |
```

`Depth` appears only when `Unit tests: selected`; an absent `Depth` means `simplify`. `TDD reason`,
`Existing-method baseline`, and `Scaffold` appear only at `Depth: TDD`, the latter two per `Mode`. `Mode`
appears on every task. Every task needs files, a dependency, a concrete description, a mechanical Done when,
and an AC mapping; at least one task must deliver code. Supporting non-code files stay inside their owning
code task and need an AC, project rule, or verified code-impact reason.
