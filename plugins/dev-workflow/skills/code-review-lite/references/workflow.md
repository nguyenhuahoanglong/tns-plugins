---
name: workflow
description: Scope, deterministic gates, compact context, isolated dispatch, and cleanup for code-review-lite
---

# Workflow

## Scope and Requirements

Resolve PR, branch, staged, working, or explicit-file scope. Record source/target and write the full diff once to `.CodeReview/.{safe-branch}.diff`; sanitize branch separators, colon, and whitespace to `-`.

For explicit PR-only intent, run `ado_work_item.py pr-required --pr {id} --repo "{repo}"`. Exit `4` or `2` is a hard stop; never fall back. Review the merge preview and record `server-merge`, `local-merge`, or `source-head`.

User requirements take priority. Otherwise run `ado_work_item.py context [--pr {id}] --repo "{repo}"` once. On exit `2/3`, check `.docs/ado-context.md`, then ask at most one skippable question. A matching parent/design excerpt enriches context only; it is never a direct criterion.

## Classification and Escalation

Detect behavior risks before Tiny thresholds. Docs Tiny is documentation text with no runtime effect. Code Tiny is `<=3` files, `<=100` changed lines, and no elevated risk. Non-Tiny maps unchanged Security, Performance, Philosophy, and Standard triggers; more than one family routes directly to `code-review-pro`.

## Safe Worktree and Merge Preview

For Code Tiny and Lite, use `{repo}/.CodeReview/.worktrees/{safe-branch}`. Resolve its absolute path and prove it remains under the repo-local worktree root before replace/remove. Do not nest a review worktree.

For committed branches, fetch and add `origin/{source}`. For PRs, always fetch first, then choose:

1. Server merge: successful merge metadata/ref -> detached merge-ref worktree.
2. Local merge: source worktree plus `git merge --no-ff --no-edit origin/{target}`; abort conflicts.
3. Source HEAD: fallback when metadata/merge is unavailable.

For staged/working scope, save a binary diff, add a detached `HEAD` worktree, apply it, and copy only explicitly scoped untracked files.

## JS Dependency Preparation

Before the build gate, run:

```text
python <skill>/scripts/prepare_worktree_deps.py --worktree "{worktree}" --repo "{repo}" --diff "{diff-path}" --require-bin {build-tool} --json
```

Allow ten minutes. Repeat `--require-bin` for every exact tool invoked by the approved build. The script may junction usable source dependencies or perform its lockfile-gated frozen install. Preserve `JS-SKIPPED (deps changed | no lockfile | install failed)` when it returns `skip-build`/`install-failed`; do not call `build_gate.py` for that JS row. No semantic child installs dependencies.

## Deterministic Gate Matrix

| Flow | Gate execution | Stop/continue behavior |
|---|---|---|
| Docs Tiny | Branch only for PR/branch | FAIL -> report Critical and stop; WARN/PASS/SKIPPED -> main review |
| Code Tiny | Branch + builds concurrently | Branch FAIL -> report completed gates and stop; otherwise main review |
| Lite pass | Branch + builds concurrently | Branch allowed and all builds PASS/PASS WITH WARNINGS -> semantic lane |
| Lite build fail | Branch + builds concurrently | Branch allowed; build FAIL -> Requirement only, report, stop |
| Lite gap | Branch + builds concurrently | NOT RUN/JS-SKIPPED -> Requirement only; report gap |

Branch command:

```text
python <skill>/scripts/branch_work_item_gate.py --scope-type {scopeType} --branch "{source}" --repo "{repo}"
```

Build command:

```text
python <skill>/scripts/build_gate.py --repo "{worktree}" --command "{approved-command}" --timeout-seconds {n} --log "{absolute-log}" --json
```

The branch gate validates optional-text `US|BUG|ISSUE/{id}` against ADO types User Story, Bug, or Issue. Staged/working/files record `SKIPPED`. Gate exit/status and the build JSON are deterministic evidence, not Agent Usage.

## Compact Lite Context

After deterministic gates and before any Lite dispatch or report, write valid UTF-8 JSON to `.CodeReview/.{safe-branch}.context.json`. Docs/Code Tiny do not create it and report `Context Manifest: n/a`.

```json
{
  "schemaVersion": "code-review-lite.context.v1",
  "repo": "C:/absolute/repo",
  "worktree": "C:/absolute/worktree",
  "scope": {"type": "pr", "source": "US/123-x", "target": "main"},
  "changedFiles": ["src/a.cs"],
  "diffPath": "C:/repo/.CodeReview/.branch.diff",
  "requirements": {"mode": "work-item|regression-only", "directSource": "user|PR|ADO|unavailable", "direct": "...", "parentContext": "..."},
  "standardsPaths": ["C:/repo/AGENTS.md"],
  "buildResults": [{"repo": "...", "status": "PASS", "command": "...", "exitCode": 0, "commandExitCode": 0, "totalErrorCount": 0, "totalWarningCount": 0, "reason": "...", "logPath": "..."}],
  "preflight": {"path": "C:/worktree/.code-review-preflight", "token": "random-token"}
}
```

Paths must be absolute. `direct`/`parentContext` may be a compact string or absolute artifact path. Keep full diff out of dispatch prompts. Build records mirror `build_gate.py` status, command, both exit fields, counts, bounded diagnostics, reason, and log; JS-SKIPPED records use null `commandExitCode`, include `reason`, and invent no exit. The manifest is authoritative: report build rows must exactly match repo, status, command, command exit, counts, log, and reason.

## Child Preflight and Isolated Dispatch

Create `{worktree}/.code-review-preflight` with a random token. Each child reads it first and must return `Child Read: PASS {token}`; reject all output after FAIL/missing PASS.

Keep the reusable contract before this exact dynamic tail:

```text
Read the supplied context manifest and preflight before analysis.
For a specialist, use named-specialist output mode and only the named focus inside changedFiles/diffPath.
Run no git commands, edits, nested agents, or general review outside that boundary.
Return compact material-only records for orchestrator verification.
```

```text
Context path: {absolute-context-path}
Mode/role: {work-item|regression-only|specialist-role}
Preflight path: {absolute-preflight-path}
Preflight token: {token}
```

Use `Task(subagent_type="requirement-validator", prompt="...", description="...")` for the mandatory deep child and `Task(subagent_type="code-reviewer", prompt="...", description="...")` for the optional standard specialist. On passing builds, launch both concurrently; after build failure/gap, launch Requirement only. Semantic children run no git commands.

## Cleanup

On every exit path: verify worktree containment; run `prepare_worktree_deps.py --teardown --worktree "{worktree}"` before removal; remove worktrees with `git worktree remove --force`; remove only temporary preflight/diff/context artifacts. Keep `.CodeReview/{safe-branch}.lite.md`; never recursively remove `.CodeReview/`.
