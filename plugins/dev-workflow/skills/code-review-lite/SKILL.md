---
name: code-review-lite
description: "Adaptive, attested production-code review. Use for quick reviews, pre-merge checks, deterministic evidence, and Pro escalation."
version: 4.0.0
---

# Code Review Lite

Read `references/workflow.md` and `references/report-template.md`. This is v4.0.0.

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
4. Classify risk families from the production allowlist. More than one specialist escalates to
   `code-review-pro` after shared preflight/scope only. Do not run Lite gates, context, children,
   report, or sidecar; Pro may reuse verified shared artifacts.
5. For Code Tiny/Lite only, run the deterministic branch/build behavior in the workflow and
   discover direct plus affected tests. Record every repo/command outcome in `executions[]`; support
   multiple runs and repos. No direct tests for changed symbols writes the exact non-defect advisory
   `use-unit-testing`; do not create tests automatically.
6. Build/test failure or gap keeps the Requirement Validator only and skips a specialist. Passing
   Lite dispatches Requirement Validator plus at most one named specialist using isolated context.

## Profiles

| Profile | Condition | Semantic agents |
|---|---|---|
| No Production Code | docs/tests/excluded only | 0 |
| Code Tiny | <=3 production files, <=100 lines, no risk | 0 |
| Lite | production review with <=1 specialist | Requirement + optional specialist |
| Escalate | >1 specialist | code-review-pro only |

Preserve the existing branch/build rules. `FAIL` is Critical; environment, timeout, and JS skipped
are explicit gaps. Branch failure starts no semantic agents. Gates are scripts, never agents.

## Evidence and agents

Give each agent the production allowlist and context path only. Agents may cite tests/docs as
evidence but may create findings only at allowlisted production paths. Use the isolated dispatch
placeholders in the workflow; a host that cannot isolate must stop. Keep context manifest and
prompt-cache inputs ephemeral. Child output needs `Child Read: PASS {token}`.

## Report and verify

Write `.CodeReview/{safe-branch}.lite.md` and collision-safe
`.CodeReview/.{safe-branch}.lite.review-meta.json`. The sidecar uses `recordVersion: 3`, exact
runtime/session values, scope/test evidence, SHA-256 references, production allowlist, and
build/semantic-agent evidence. Use the template exactly, then run:

## Verify Output

Run the existing ADO autolink fix/check from the report template, then:

```text
python <skill>/scripts/verify_output.py ".CodeReview/{safe-branch}.lite.md"
```

Clean only temporary diff/context files and contained worktrees. Keep reports, sidecars, and all
runtime/scope/test evidence required for re-verification. Follow feedback and review-request
references when applicable.
