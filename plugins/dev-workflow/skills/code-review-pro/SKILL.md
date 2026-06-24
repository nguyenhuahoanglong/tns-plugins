---
name: code-review-pro
description: Adaptive code review for PRs, branches, staged changes, and follow-ups. Use when Docs-only, Tiny, or Pro risk-based validation and reporting are needed.
version: 2.0.0
---

# Code Review Pro

Classify first, announce the decision, then spend agents only where risk warrants them. Use this skill for full reviews and follow-ups; route explicit "quick/lite review" requests to `code-review-lite`.

## Runtime Contract

| Role | Agent type | Runtime |
|---|---|---|
| Main review/synthesis | current agent | report actual exposed model/effort |
| Branch Work Item Gate | lightweight gate runner | `haiku / default` |
| Build Validator | `build-validator` | `haiku / default` |
| Requirement Validator | `requirement-validator` | `opus / default` |
| Risk specialist | `code-reviewer` | `sonnet / default` |

Resolve the main runtime before classification, in this order:

1. explicit launch/review metadata supplied by the caller
2. current host/session metadata
3. a configured default only when confirmed as the active session runtime
4. `not exposed` for only the individual field that remains unavailable

Never replace a known model or effort with `not exposed`. A parent/orchestrator launching a Codex review must pass both values explicitly when the child cannot inspect its launch settings.

Dispatch with exact generated calls:

- Build: `Task(subagent_type="build-validator", prompt="...", description="...")`
- Branch Work Item Gate: run `python <skill-dir>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{sourceBranch}" --repo "{repo}"`
- Requirement: `Task(subagent_type="requirement-validator", prompt="...", description="...")`
- Specialist: `Task(subagent_type="code-reviewer", prompt="...", description="...")`

At review start emit:

> Review profile: `{profile}` | Main: `{resolved model}` / `{resolved effort}` | Planned agents: `{actors and runtimes}`

Before every spawn emit:

> Agent trigger: `{role}` | Model/Effort: `{runtime}` | Reason: `{trigger}`

## Workflow

### 1. Gather

Read `references/review-workflow.md`. Determine scope, source branch, write one diff file, count changed files and added+removed lines, detect repos/projects, discover standards/neighbors, and resolve optional work-item context through `scripts/ado_work_item.py`.

Resolve one exact approved build command per repo from project instructions. Do not authorize dependency install/restore implicitly; omit it unless already available or explicitly approved.

For an existing v2 sidecar, use `references/followup-review.md`. An absent, invalid, or v1 sidecar requires a fresh full-scope classification.

### 2. Classify and Announce

Read `references/adaptive-classifier.md`. Choose exactly one profile:

- **Docs-only**: documentation-only diff; zero agents.
- **Tiny**: code diff with at most 3 files and 100 changed lines, and no classifier risk.
- **Pro**: every other diff; uncertainty selects Pro.

Every classifier and specialist trigger must appear in both this announcement and final `Triggered`/`Skipped` fields.

### 3. Execute Profile

#### Docs-only

Run Branch Work Item Gate for PR/branch scope; skip it for staged, working, and file scope. Spawn no other agents and create no worktree. If the gate fails, report the CRITICAL branch/work-item violation and stop. Otherwise review changed documentation inline for internal consistency, broken paths/commands, requirement mismatch, and accidental behavior claims.

#### Tiny

Create repo-local worktrees. Run Branch Work Item Gate in parallel with exactly one `build-validator` per repo using `references/agents/build-validator.md`; both use `haiku / default`. Every child must echo the supplied preflight token before analysis.

If Branch Work Item Gate fails, write the report with completed build results, mark the gate failure CRITICAL, skip later review, and stop.

After all child reads pass, the main agent reviews every changed line through all lenses in `references/tiny-review.md`. Do not spawn Requirement or specialist agents.

#### Pro

Create repo-local worktrees. Run Branch Work Item Gate in parallel with exactly one `build-validator` per repo first; both use `haiku / default`. Repair/retry any `Child Read: FAIL`; do not dispatch readers against inaccessible paths. Every later child repeats the token preflight.

If Branch Work Item Gate fails, write the report with completed build results, mark the gate failure CRITICAL, skip Requirement Validator and specialists, and stop.

After child reads pass, always spawn one `requirement-validator` using `references/agents/requirement-validator.md`. With a direct work item, use `work-item` mode; without one, use `regression-only` mode.

If any build fails, still run Requirement Validator because requirement/regression is highest priority, but skip specialists to avoid spending tokens on broken code. Otherwise dispatch only specialists whose triggers fired:

- Security Reviewer: `references/agents/security-reviewer.md`
- Performance Reviewer: `references/agents/performance-reviewer.md`
- Philosophy Reviewer: `references/agents/philosophy-reviewer.md`
- Standard Reviewer: `references/agents/standard-reviewer.md`

Build failure is a CRITICAL finding. Continue Requirement validation when files remain readable.

### 4. Synthesize

Read `references/report-template.md` and `references/analysis-framework.md`. Re-verify agent claims against code and evidence. Organize findings by file, preserve stable `[mf:slug]` tags, and write `.CodeReview/{safe-branch}.md`.

Write `.CodeReview/.{safe-branch}.review-meta.json` using record version 2 from `references/followup-review.md`. Include `skillName`, `skillVersion`, `reviewProfile`, classifier data, `branchWorkItemGate`, runtime, triggered/skipped records, repos reviewed, requirement mode, scope type/base/fingerprint, reviewed files/commit, and iteration.

Run the ADO autolink guard after every report:

```text
python <code-review-publish-skill>/scripts/ado_autolink_guard.py fix ".CodeReview/{safe-branch}.md"
python <code-review-publish-skill>/scripts/ado_autolink_guard.py check ".CodeReview/{safe-branch}.md"
```

Raw `#number` is allowed only for intentional work-item links.

## Verify Output

Run before declaring completion:

```text
python <skill-dir>/scripts/verify_output.py ".CodeReview/{safe-branch}.md" --sidecar ".CodeReview/.{safe-branch}.review-meta.json"
```

Fix every FAIL. Then remove worktrees and the temporary diff; keep report and sidecar.

## Follow-up, Feedback, Requests

- Follow-up/re-review: `references/followup-review.md`; reclassify the delta with the same classifier.
- Received feedback: `references/feedback-reception.md`.
- Requesting review from others: `references/requesting-review.md`.

## Enforcement

- Docs-only uses only Branch Work Item Gate when scope is PR/branch. Tiny uses only Branch Work Item Gate and Build Validators; main agent owns all review lenses.
- Pro always runs Build Validator(s) and one Requirement Validator; specialists require recorded triggers.
- Branch Work Item Gate uses the Build Validator runtime, validates `US/`, `BUG/`, or `ISSUE/` branch IDs against ADO work item type, and blocks later review on FAIL.
- Use repo-local `.CodeReview/.worktrees/{safe-branch}` paths only.
- Pass paths, not pasted diffs or reference contents, to agents.
- Cleanup runs even on failures. Do not sync/install this skill as part of review execution.
