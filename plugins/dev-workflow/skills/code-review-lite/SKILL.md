---
name: code-review-lite
description: "Adaptive low-cost code review. Use for quick review, lite review, or pre-merge checks; runs deterministic gates, isolated risk review, and escalates broad risk."
version: 3.0.0
---

# Code Review Lite

Run an adaptive review. Read `references/workflow.md` and `references/report-template.md` before execution.

## 1. Gather

Resolve scope, repos, source/target, changed files, full diff, and exact approved build command per repo. Count files, additions plus deletions excluding headers, and risk families. User requirement text wins; otherwise fetch once with `ado_work_item.py context`, ask at most one skippable question after failure, and keep parent/design context non-binding.

For an explicit PR-only request, require `ado_work_item.py pr-required` success and review its merge preview. Do not fall back to another scope. Follow `references/workflow.md` for merge-preview strategy, worktree safety, dependency preparation, and child-read preflight.

## 2. Classify

`Tiny` requires `<=3` files, `<=100` changed lines, and no changed behavior involving shared/public API, schema/serialization/migration, auth/secrets/trust, dependencies/manifests/lockfiles, async/concurrency/lifecycle/background work, persistent/shared state, or runtime config/deployment/flags/environment.

| Profile | Condition | Deterministic gates | Semantic children |
|---|---|---|---|
| Docs Tiny | Documentation-only, any size | Branch when applicable; no build | 0 |
| Code Tiny | Tiny with code | Branch when applicable + build per repo | 0 |
| Lite | Not Tiny; at most one specialist | Branch when applicable + build per repo | Requirement Validator + 0/1 specialist |
| Escalate | More than one specialist | Route to `code-review-pro` | Lite pipeline does not run |

Documentation-only excludes executable code/tests, config, schema, manifests, lockfiles, scripts, and generated runtime assets.

## 3. Select Specialist

Use the Pro triggers unchanged:

| Reviewer | Trigger examples |
|---|---|
| Security | auth, secrets, crypto, untrusted input, trust boundary |
| Performance | async/concurrency, lifecycle, hot paths, I/O, resources |
| Philosophy | shared/public API/schema, state/config ownership, coupling |
| Standard | explicit project rule, new pattern/folder, build convention |

One family selects one `code-reviewer` named role. Two or more announce escalation and invoke `code-review-pro` without running Lite.

## 4. Prepare and Gate

Create repo-local worktrees and run `prepare_worktree_deps.py` exactly as `references/workflow.md` specifies. Preserve lockfile-gated frozen installs and `JS-SKIPPED`; children never install dependencies.

Branch and build gates are deterministic processes, never agents. For PR/branch scope run `branch_work_item_gate.py`; otherwise record `SKIPPED`. For each non-doc repo not marked `JS-SKIPPED`, run only:

```text
python <skill>/scripts/build_gate.py --repo "{worktree}" --command "{approved-command}" --timeout-seconds {n} --log "{absolute-log}" --json
```

Run applicable branch and build gates concurrently. A branch `WARN` continues. A branch `FAIL` is Critical: wait for started gates, report their completed evidence, skip all semantic children, and stop. A code build `FAIL` is Critical; `NOT RUN (environment|timeout)` and `JS-SKIPPED ({reason})` are explicit gaps, not fabricated code failures.

## 5. Create Lite Context

For Lite, write the compact `.CodeReview/.{safe-branch}.context.json` contract from `references/workflow.md`. Store the diff and requirements in files/manifest, not dispatch text. Put stable child instructions first and only context path, role/mode, and preflight values in the dynamic tail.

Use semantic runtimes only:

| Child | Runtime | Dispatch |
|---|---|---|
| Requirement Validator | `opus / default` | `Task(subagent_type="requirement-validator", prompt="...", description="...")` |
| Named specialist | `sonnet / default` | `Task(subagent_type="code-reviewer", prompt="...", description="...")` |

Before each semantic dispatch announce `Agent trigger: {child} | Model/Effort: {runtime} | Reason: {risk/scope}`. If a host rejects isolated custom-agent syntax, stop instead of inheriting the main context/runtime.

## 6. Execute

- **Docs Tiny:** after branch pass/warn/skip, main agent checks accuracy, consistency, links, commands, and requirement alignment. Spawn zero semantic children.
- **Code Tiny:** after gates pass/warn/skip, main agent reviews correctness, regressions, security, performance, design, and standards. Spawn zero semantic children.
- **Lite, all builds pass/pass-with-warnings:** dispatch the mandatory Requirement Validator and the one selected specialist, if any, concurrently. Main agent verifies and synthesizes both.
- **Lite, build fails:** dispatch only the mandatory Requirement Validator after branch pass/warn/skip; skip the specialist, then report the build failure and requirement result.
- **Lite, build not run/JS-skipped:** dispatch the mandatory Requirement Validator; record the validation gap and specialist skip reason.

Use `references/agents/requirement-validator.md` as the Lite dispatch/output adapter. Do not inline the central agent methodology.

## Requirement and Collateral Evidence

- Map direct requirements to `Addressed`, `Partial`, `Missing`, or `Not verifiable`; changed implementation at `file:line` is required for `Addressed`.
- Classify each material behavior delta as `Direct requirement`, `Necessary collateral`, `Unrelated`, or `Unclear`; collateral never becomes a new criterion.
- Record base-to-new behavior, affected caller/consumer/event/state/config paths, and tests or equivalent preservation evidence.
- Mark missing proof `Unproven`; missing tests alone are not a defect. Regression findings require concrete exposed-path evidence.

## 7. Report

Write `.CodeReview/{safe-branch}.lite.md` with skill `code-review-lite v3.0.0`. Separate Deterministic Gates from Semantic Agents. Agent Usage records context mode and input, cache-read, cache-write, and output tokens as a number or exact `not exposed`; never estimate.

## Related Protocols

Before responding to published-review feedback, read `references/feedback-reception.md`. For milestone review requests, see `references/requesting-review.md`.

## Verify Output

Run the ADO autolink fix/check commands in `references/report-template.md`, then:

```text
python <skill>/scripts/verify_output.py ".CodeReview/{safe-branch}.lite.md"
```

Clean verified worktrees unconditionally using `references/workflow.md`; keep the report.
