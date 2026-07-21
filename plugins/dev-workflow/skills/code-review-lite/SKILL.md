---
name: code-review-lite
description: "Adaptive, attested production-code review. Use for quick reviews, pre-merge checks, deterministic evidence, and Pro escalation."
version: 4.1.0
---

# Code Review Lite

Read `references/workflow.md` and `references/report-template.md`. This is v4.1.0.

## Invocation

Accept optional `Escalation Policy: auto|ask`; omitted means `auto` and preserves the prior
immediate-Pro behavior for multiple specialist families.

## Mandatory order

1. Before any repository read, diff, worktree, build, test, or classification, run shared
   `runtime-preflight` and session gate using exact host metadata. Missing, stale, conflicting,
   unknown, or below-minimum runtime is a hard stop. An existing session pauses for explicit
   confirmation; record its override. Never use display names, self-report, or defaults.
2. Gather paths and diff, persist the production scope manifest, then classify only production
   hunks. Tests and documents are evidence-only; generated, vendor, and binary paths are excluded.
3. If scope is `no-production-code`, write the `No Production Code` report and record-v3 Lite
   sidecar, retaining runtime/scope/test artifacts. Test status is `not-applicable` with reason
   `no-production-code`. Do not create a worktree/context, execute build/tests/semantic review,
   or produce findings. Branch validation is optional evidence.
4. Classify risk families from the production allowlist. For multiple families, apply the
   escalation decision table before Lite gates: `auto` invokes `code-review-pro` immediately;
   `ask` explains every family and why Pro is recommended, then asks. An accepted ask invokes Pro.
   Both Pro paths stop after preflight/scope: no Lite gates, context, children, report, or sidecar.
   A declined ask continues bounded Lite.
5. For Code Tiny/Lite only, run the deterministic branch/build behavior in the workflow and
   discover direct plus affected tests. Record every repo/command outcome in `executions[]`; support
   multiple runs and repos. No direct tests for changed symbols writes the exact non-defect advisory
   `use-unit-testing`; do not create tests automatically.
6. For every Lite route, a branch `FAIL` starts no semantic agents, sets `Selected Specialist` to
   `None`, and marks every triggered family unreviewed. A build/test failure, timeout, or gap runs
   Requirement Validator only, sets `Selected Specialist` to `None`, and marks every triggered
   family unreviewed. Otherwise, bounded Lite after a declined ask dispatches Requirement Validator
   plus exactly one highest-priority specialist: Security Reviewer > Philosophy Reviewer >
   Performance Reviewer > Standard Reviewer; every other triggered family is unreviewed.
   Single/zero-family Lite uses `not-needed`.

## Profiles

| Profile | Condition | Semantic agents |
|---|---|---|
| No Production Code | docs/tests/excluded only | 0 |
| Code Tiny | <=3 production files, <=100 lines, no risk | 0 |
| Lite | production review with <=1 specialist | Requirement + optional specialist |
| Pro escalation | >1 family with `auto` or accepted `ask` | code-review-pro only |
| Bounded Lite | >1 family with declined `ask` | Requirement + one priority specialist when gates pass |

Preserve the existing branch/build rules. `FAIL` is Critical; environment, timeout, and JS skipped
are explicit gaps. For every Lite route, branch failure starts no semantic agents; build/test
failure, timeout, or gap runs Requirement Validator only. Gates are scripts, never agents.

## Escalation decision table

| Triggered families | Policy / response | Outcome | Lite fields |
|---|---|---|---|
| 0 or 1 | `auto` or `ask` | Lite | `not-needed`; selected `{Family} Reviewer` or `None`; unreviewed `None` |
| 2+ | `auto`, or `ask` accepted | Pro | no Lite artifact |
| 2+ | `ask` declined; gates pass | Bounded Lite | `pro-declined`; select Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard Reviewer; other families unreviewed |
| 2+ | `ask` declined; branch FAIL | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |
| 2+ | `ask` declined; build/test fail, timeout, or gap | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |

## Evidence and agents

Give each agent the production allowlist and context path only. Agents may cite tests/docs as
evidence but may create findings only at allowlisted production paths. Use the isolated dispatch
placeholders in the workflow; a host that cannot isolate must stop. Keep context manifest and
prompt-cache inputs ephemeral. Child output needs `Child Read: PASS {token}`.

## Report and verify

Write `.CodeReview/{safe-branch}.lite.md` and collision-safe
`.CodeReview/.{safe-branch}.lite.review-meta.json`. The report fields are `Escalation Policy`,
`Escalation Decision`, `Selected Specialist`, and `Unreviewed Risk Families`; the matching sidecar
keys are `escalationPolicy`, `escalationDecision`, `selectedSpecialist`, and
`unreviewedRiskFamilies`. The sidecar uses `recordVersion: 3`, `skillVersion: 4.1.0`, exact
runtime/session values, scope/test evidence, SHA-256 references, production allowlist, and
build/semantic-agent evidence. Its `selectedSpecialist` value must be exactly `Security Reviewer`,
`Philosophy Reviewer`, `Performance Reviewer`, `Standard Reviewer`, or `None`. Use the template
exactly, then run:

## Verify Output

Run the existing ADO autolink fix/check from the report template, then:

```text
python <skill>/scripts/verify_output.py ".CodeReview/{safe-branch}.lite.md"
```

Clean only temporary diff/context files and contained worktrees. Keep reports, sidecars, and all
runtime/scope/test evidence required for re-verification. Follow feedback and review-request
references when applicable.
