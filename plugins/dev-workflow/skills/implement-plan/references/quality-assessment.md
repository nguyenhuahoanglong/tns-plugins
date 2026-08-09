# Project Quality Assessment

Assess the nearest target module after exploration: read applicable `AGENTS.md`, build/test setup,
deployment surface, and ownership rules. Recommendations are evidence; only explicit user `Yes` selects
a risky workflow.

## Eligibility

Assess quality only after the entry gate passes. At least one planned task must deliver source code,
executable scripts, test code, or runtime/build code tied to a feature, fix, or refactor. Supporting
non-code files may remain in an eligible code plan when required by an AC, project rule, or verified code
impact, but never make a plan eligible by themselves.

## Context contract

Write these exact Context fields on every new or rewritten plan:

```text
Plan path origin: existing-input|backlog-requirement|generated-project-root
Plan path evidence: <non-empty>
TDD recommendation: recommended|not-recommended
TDD recommendation reason: <non-empty>
TDD decision: selected|skipped
Unit tests: selected|skipped
Unit tests source: user|auto-assessment
Unit tests reason: <non-empty>
Code review recommendation: recommended|not-recommended
Code review recommendation reason: <non-empty>
Code review decision: selected|skipped
Code review: selected|skipped
Code review source: user|auto-assessment
Code review reason: <non-empty>
Depth: TDD|simplify
```

`TDD decision` equals `Unit tests`; `Code review decision` equals `Code review`. Top-level `Depth` is
`TDD` when TDD is selected, otherwise `simplify`. `Plan path evidence` names the supplied input or
resolved project-root basis.

## Path matrix

| Input | Origin | Exact destination |
|---|---|---|
| Existing plan | `existing-input` | its exact supplied path |
| Explicit requirement file/folder under `.backlog/<feature>/` | `backlog-requirement` | `.backlog/<feature>/plan.md` |
| Inline, no-argument, or non-backlog input | `generated-project-root` | nearest project-root `.plans/<feature>.md` |

Discovered backlog context never redirects a plan.

## Recommendation and consent

For each code workflow, record concrete trigger/evidence, affected workflow or regression risk, and
effort. A `not-recommended` workflow is skipped without a question unless the user already selected it.
Ask only unresolved workflows marked `recommended`; present `Yes (Recommended)` and `No` so the option
label matches the assessment.

Only explicit user `Yes` selects TDD or review. A recommendation, missing answer, or modern
`selected` with source `auto-assessment` is evidence only: ask before execution. A modern decision
with source `user` preserves its explicit choice. Legacy `requested` maps to selected and `not requested`
to skipped, both with `source: user`; preserve meaning and normalize all fields on rewrite. Surface a
project-mandated gate conflict for user resolution rather than silently overriding a decline.

## Per-task depth

Every task uses the exact fields in `definition-criteria.md`. Only risky, user-approved tasks use
`Depth: TDD`; routine and unapproved risky tasks use `simplify`. Mixed plans may therefore have routine
tasks at `simplify` while the top-level Depth is `TDD`.
