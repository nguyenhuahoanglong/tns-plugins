# Plan Contract

What a plan must contain to be executable without user interaction. This file prescribes the **contract**,
never the planning method: no interview script, no question bank, no explorer or architect counts, no
exploration scaling. The host tool's plan mode owns all of that.

## Path resolution

| Input | Origin | Canonical destination |
|---|---|---|
| Host-injected plan path present | `host-plan-mode` | draft at host path, `.plans/<feature>.md` on promotion |
| Existing plan path supplied | `existing-input` | its exact supplied path |
| Explicit requirement file/folder under `.backlog/<feature>/` | `backlog-requirement` | `.backlog/<feature>/plan.md` |
| Inline, no-argument, or non-backlog input | `generated-project-root` | nearest project-root `.plans/<feature>.md` |

Detect, never assume. While a host plan path is in force it is the only writable file: draft there and
never attempt a repo write before approval. Codex plan mode injects no path, so resolve by matrix; when the
host forbids planning writes, hold the draft in-message and make the canonical write the first
post-approval action. Promotion copies the approved draft to the canonical path with a real feature slug
(host slugs are hash-suffixed paraphrases); never delete or rewrite the host file. From promotion onward
only the canonical file receives Status updates. Discovered backlog context never redirects a plan.

## Consent

`--tdd`, `--review`, `--no-tdd`, and `--no-review` are explicit consent; record the flag verbatim in the
matching reason field. Without flags, ask one consolidated question after the plan is drafted — both,
tests only, review only, or neither — once. Silence skips both. A one-line advisory naming the trigger and
the risk is allowed; a recommendation phase is not. Legacy `requested`/`not requested` and old
`auto-assessment` selections are accepted as input and normalized to `source: user` with the reason
preserved. Surface a project-mandated gate conflict for user resolution rather than overriding a decline.

## Context contract

Write exactly these fields on every new or rewritten plan:

```text
Plan path: <canonical path>
Plan path origin: host-plan-mode|existing-input|backlog-requirement|generated-project-root
Plan path evidence: <supplied input, promoted host draft path, or project-root basis>
Unit tests: selected|skipped
Unit tests source: user|flag
Unit tests reason: <non-empty>
Code review: selected|skipped
Code review source: user|flag
Code review reason: <non-empty>
```

`Autonomy` and preflight results live in `## Preflight`, never in `## Context`.

## Eligibility

At least one task must deliver source code, executable scripts, test code, or runtime/build code tied to a
feature, fix, or refactor. Supporting non-code files may ride along in an eligible code plan when an AC,
project rule, or verified code impact requires them, inside their owning code task; they never make a plan
eligible and never form a standalone task.

## Acceptance criteria

Each AC states observable behavior and maps to one or more tasks. Good: `AC-1: Exporting an empty report
yields a CSV with only the header row.` Weak: `AC-1: Export works.`

## Per-task contract

Every task carries exactly these seven fields:

```text
- Status: pending|scaffolded|in-progress|complete|blocked
- Depends on: none|Task N
- Files: `path`
- Mode: existing-method|simple-new|complex-backbone
- Description: <zero-context executable behavior and compatibility>
- Done when: <mechanical command or observable evidence>
- ACs: AC-N
```

Conditional fields, and no others:

- When `Unit tests: selected`, add `Depth: simplify|TDD`. An absent `Depth` means `simplify`.
- When `Depth: TDD`, add `TDD reason: <non-empty>`; `Depth: TDD` is itself the risk assertion.
- When `Mode: existing-method` and `Depth: TDD`, add `Existing-method baseline: <exact existing suite
  command and result>`.
- When `Mode: simple-new` and `Depth: TDD`, add `Scaffold: <named signatures and control-flow wiring>`.

`Mode` is mandatory at every depth because `complex-backbone` routes execution to `design-backbone`
regardless of Depth. Valid Done-when evidence is a named build/test command, a deterministic assertion, or
exact endpoint I/O.

## Actionability gate

A task is admitted only when its pattern or signature was personally read, its description is zero-context
executable, its Done when is mechanical, and `Depends on` is `none` or an exact task. Every external
prerequisite — authentication, network endpoint, CLI availability, dependency state — has a `## Preflight`
row. File existence is never hand-authored: `preflight.py` derives a `path` probe from every task's
`Files:` field, checking parent-folder existence for a file the description marks as new.

No two tasks share a file; merge overlapping work. Imports and contracts create explicit dependency edges,
and a changed shared interface precedes all of its consumers. Assign one implementer per independent,
dependency-ready slice, keep coupled files together, and cap concurrency at three. The plan records waves
plus each agent's file scope, task contract, and Done-when evidence.

## Placeholder ban

`TBD`, `TODO`, `undecided`, `appropriate`, `similar to Task N`, and unresolved template braces block
writing. Resolve the fact or narrow the scope instead.
