---
name: code-review-lite
description: "Adaptive low-cost code review. Use for quick review, lite review, or pre-merge checks; classifies Tiny changes, dispatches risk-based agents, and escalates broad risk."
version: 2.0.0
---

# Code Review Lite

Run an adaptive review. Read `references/workflow.md` and `references/report-template.md` before execution.

## 1. Gather

Resolve scope, repos, target branch, changed files, and full diff. Count:

- files changed
- changed lines = additions + deletions, excluding diff headers
- risk families below

Fetch requirement context non-blockingly with:

```text
python <skill>/scripts/ado_work_item.py context [--pr {id}]
```

User requirement text wins. Ask at most one skippable requirement-context question after fetch failure.

Resolve one exact approved build command per repo from project instructions. Do not authorize dependency install/restore implicitly.

## 2. Classify

`Tiny` requires both `<=3` files and `<=100` changed lines. It is ineligible when any changed behavior touches:

- shared behavior or public API
- schema, serialization, or data migration
- authentication, authorization, secrets, or trust boundaries
- dependencies, package manifests, or lockfiles
- async, concurrency, resource lifecycle, or background work
- persistent/shared state
- runtime configuration, deployment, feature flags, or environment behavior

Profiles:

| Profile | Condition | Review actors |
|---|---|---|
| Docs Tiny | Documentation-only at any size | Main agent only; zero child agents |
| Code Tiny | Tiny with code | Main agent + one Build Validator per repo |
| Lite | Not Tiny and at most one specialist | Build Validator per repo + Requirement Validator + zero/one specialist |
| Escalate | More than one specialist | Route to `code-review-pro`; do not run Lite pipeline |

Documentation-only excludes executable code, tests, config, schema, manifests, lockfiles, scripts, and generated runtime assets.

## 3. Select Specialist

Use same specialist triggers as Pro:

| Reviewer | Trigger examples |
|---|---|
| Security | auth, authorization, secrets, crypto, untrusted input, trust boundary |
| Performance | async/concurrency, lifecycle, query/loop hot paths, I/O, resource ownership |
| Philosophy | shared behavior, public API/schema, state/config ownership, abstraction/coupling |
| Standard | explicit project rule, new pattern/folder, build/config convention, exemplar divergence |

One reviewer triggers one generic `code-reviewer` with that named role injected. Two or more reviewers trigger `code-review-pro`. Announce every trigger or escalation before dispatch.

## 4. Runtime and Visibility

Use these exact child profiles:

| Actor | Agent type | Model | Effort |
|---|---|---|---|
| Build Validator | `build-validator` | `haiku / default` | configured |
| Requirement Validator | `requirement-validator` | `opus / default` | configured |
| Named specialist | `code-reviewer` | `sonnet / default` | configured |

Resolve the main runtime before classification: explicit launch/review metadata, then current host/session metadata, then a configured default only when confirmed active. Use `not exposed` only for an individual field that remains unavailable. Never replace a known model or effort with `not exposed`; Codex parent/orchestrator prompts must pass both values when the child cannot inspect launch settings.

Before each dispatch announce:

```text
Agent trigger: {actor} | Model/Effort: {runtime} | Reason: {risk/scope}
```

Dispatch Build with `Task(subagent_type="build-validator", prompt="...", description="...")`, Requirement with `Task(subagent_type="requirement-validator", prompt="...", description="...")`, and named specialist with `Task(subagent_type="code-reviewer", prompt="...", description="...")`.

Create agent worktrees per repo at `.CodeReview/.worktrees/{safe-branch}`. Complete the child-read preflight in `references/workflow.md` before analysis. Child agents run no git commands.

## 5. Execute

### Docs Tiny

Main agent reviews accuracy, consistency, links, commands, and requirement alignment. Spawn no agents.

### Code Tiny

Run Build Validators in parallel. Main agent reviews changed code for correctness, regressions, security, performance, design, and standards. Do not spawn Requirement Validator or specialist.

### Lite

1. Run one Build Validator per repo in parallel.
2. Run one Requirement Validator even if build fails.
3. On build failure, skip specialist to save tokens.
4. Otherwise run the single triggered named specialist, if any.
5. Main agent verifies and synthesizes findings.

## Requirement Evidence

- Map each explicit requirement to `Addressed`, `Partial`, `Missing`, or `Not verifiable`.
- `Addressed` needs changed-code evidence: `file:line` plus behavior explanation.
- Tests support evidence but do not replace implementation evidence.
- `Partial`/`Missing` must state searched scope and absent behavior.
- Regression claims need caller, consumer, or execution-path evidence.
- Never invent criteria; use user text, PR text, or fetched work item only.

## 6. Report

Write `.CodeReview/{safe-branch}.lite.md`. Include exact:

- skill: `code-review-lite`
- version: `2.0.0`
- profile: `Docs Tiny`, `Code Tiny`, or `Lite`
- main runtime: `{resolved model} / {resolved effort}`
- triggered actors with runtime profiles and reasons
- skipped actors with reasons

Preserve the ADO autolink guard:

```text
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{safe-branch}.lite.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{safe-branch}.lite.md"
```

## Verify Output

Run before declaring completion:

```text
python <skill>/scripts/verify_output.py ".CodeReview/{safe-branch}.lite.md"
```

Then clean worktrees unconditionally. Keep the `.lite.md` report.

## Related Protocols

- Received feedback: `references/feedback-reception.md`
- Requesting review: `references/requesting-review.md`
