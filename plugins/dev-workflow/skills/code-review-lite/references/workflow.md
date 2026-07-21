---
name: workflow
description: v4.1.0 runtime, scope, test, escalation, and isolated-agent workflow
---

# Workflow

## 1. Shared clearance before repository reads

Before reading repository files, gathering paths, inspecting a diff, or creating a worktree, run
the shared `runtime-preflight` with exact Codex rollout or Claude status-line evidence. Persist its
JSON. `blocked` is a hard stop. Run session classification next: `confirmation-required` pauses
until explicit confirmation, then rerun/record `overrideRecorded: true`. Do not infer runtime from
settings or rendered labels.

## 2. Scope before Lite work

Gather path metadata and write the full diff once. Run `scope-manifest` and persist it. Its
`productionFiles` is the sole finding allowlist; `evidenceFiles` (tests/docs) can be cited only;
`excludedFiles` (generated/vendor/binary) are never reviewed. `no-production-code` writes only the
No Production Code outcome plus its record-v3 sidecar. Retain runtime/scope/test artifacts, with
test status `not-applicable` and reason `no-production-code`; skip worktree, build/test execution,
semantic children, context, and findings. Branch validation is optional.

Classify specialist families from production hunks. Invocation accepts `Escalation Policy: auto|ask`;
omission defaults to `auto`. Apply the following decision table before Lite work. In `ask`, explain
every triggered family and why Pro is recommended, then request the user's choice.

| Triggered families | Policy / response | Outcome | Lite fields |
|---|---|---|---|
| 0 or 1 | `auto` or `ask` | Lite | `not-needed`; selected `{Family} Reviewer` or `None`; unreviewed `None` |
| 2+ | `auto`, or `ask` accepted | Pro | no Lite artifact |
| 2+ | `ask` declined; gates pass | Bounded Lite | `pro-declined`; select Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard Reviewer; other families unreviewed |
| 2+ | `ask` declined; branch FAIL | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |
| 2+ | `ask` declined; build/test fail, timeout, or gap | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |

For a Pro outcome, only preflight and scope artifacts may be reused; Lite must not run branch/build/test
gates, create context/sidecar/report, or spawn children. For bounded Lite, preserve the residual-family
list in the main workflow; do not inject it into the selected specialist.

## 3. Code Tiny and Lite gates

For remaining production scope, retain the v3 branch/worktree/dependency/build behavior. Use
repo-local `.CodeReview/.worktrees/{safe-branch}` and prove containment before cleanup. Run branch
and builds deterministically; children never install dependencies. Preserve `PASS`, `PASS WITH
WARNINGS`, `FAIL`, `NOT RUN (environment|timeout)`, and `JS-SKIPPED` evidence.

Then run shared `discover-tests` and `test-gate` for direct and affected tests. Record exact
commands, counts, exit, duration, bounded logs, and repo identity in `executions[]`; aggregate every
run across every repository instead of overwriting the prior result. A pass has exit 0 and zero
failed tests; a failure has nonzero exit and positive failed count; a timeout has nonzero exit and
zero counts. Empty direct tests for changed symbols require the exact advisory `use-unit-testing`,
not a defect. The advisory never suppresses a selected specialist. For every Lite route, branch
`FAIL` starts no semantic agents, selects `None`, and leaves every triggered family unreviewed;
build/test failure, timeout, or gap dispatches Requirement Validator only, selects `None`, and
leaves every triggered family unreviewed. Otherwise dispatch Requirement Validator plus exactly
one priority specialist: Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard
Reviewer. Single/zero-family Lite has decision `not-needed`.

## 4. Isolated context, report, and sidecar

For Lite, make an ephemeral absolute context manifest containing diff path, requirements, build
records, production allowlist, and preflight token. Dynamic dispatch tail stays exactly:

```text
Context path: {absolute-context-path}
Mode/role: {work-item|regression-only|specialist-role}
Preflight path: {absolute-preflight-path}
Preflight token: {token}
```

Use `Task(subagent_type="requirement-validator", prompt="...", description="...")` and
`Task(subagent_type="code-reviewer", prompt="...", description="...")`; children must not use git, edit, nest agents, or create
findings outside the allowlist. Keep prompt cache/context ephemeral.

Write `.CodeReview/.{safe-branch}.lite.review-meta.json` with `recordVersion: 3`,
`skillVersion: 4.1.0`, exact attested runtime, session override, production allowlist, build and semantic-agent
evidence, and absolute runtime/scope/test artifact references with SHA-256 hashes. Add
`escalationPolicy`, `escalationDecision`, `selectedSpecialist`, and `unreviewedRiskFamilies`, mirrored
by report fields `Escalation Policy`, `Escalation Decision`, `Selected Specialist`, and `Unreviewed
Risk Families`. `skillName`, `skillVersion`,
`reviewProfile`, the complete runtime object, and the session projection must exactly match the
report and attestation. `selectedSpecialist` must be exactly `Security Reviewer`, `Philosophy
Reviewer`, `Performance Reviewer`, `Standard Reviewer`, or `None`. The report repeats the artifact
references. No Production Code also writes
this report/sidecar pair; Pro escalation writes neither. Bounded Lite writes both.

## 5. Cleanup

After verification, remove only temporary diff/context files and a proven-contained worktree.
Retain report, sidecar, runtime attestation, scope manifest, and test evidence so verification can
be repeated.
