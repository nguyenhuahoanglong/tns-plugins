---
name: followup-review
description: Incremental follow-up review workflow (iteration 2+) — reuses the prior report and meta sidecar, reviews only the delta with a single Delta Reviewer, regenerates the full publish-compatible report
---

# Follow-up Review (Iteration 2+)

A follow-up review runs when the branch already has a completed full review. The expensive artifacts from iteration 1 — discovery results, AC mapping, per-file findings, Must Fix slugs — are reused, so the pipeline shrinks to: delta diff → build gate → ONE Delta Reviewer → synthesis.

## Detection

Follow-up mode applies when BOTH exist for the current branch:

- Report: `.CodeReview/{BranchName}.md`
- Meta sidecar: `.CodeReview/.{BranchName}.review-meta.json`

Also triggered explicitly by "follow up review" / "re-review" / "check my fixes". If the user explicitly asks for a **full** re-review, run the full pipeline instead (and overwrite report + sidecar).

If `HEAD == reviewedCommit` from the sidecar → tell the user "no changes since last review" and STOP (no agents, no worktree).

If the sidecar is missing or unparseable but a report exists → fall back to the full pipeline (do not guess the reviewed commit).

## Meta Sidecar Schema

Written by Phase 4 of every review (full and follow-up):

```json
{
  "reviewedCommit": "{HEAD sha at review time}",
  "targetBranch": "develop",
  "workItemId": 1795,
  "standardsPaths": ["AGENTS.md", ".editorconfig"],
  "exemplarMap": { "src/Services/FooService.cs": ["src/Services/BarService.cs"] },
  "reviewedFiles": ["src/Services/FooService.cs", "src/Api/FooController.cs"],
  "iteration": 1,
  "reviewedAt": "{ISO timestamp}"
}
```

`reviewedFiles` = the changed-file list of the last review (used by the escalation rule). Paths relative to the repo root.

## Pipeline

### 1. Pre-work (orchestrator)

Reuse from the sidecar — SKIP scope determination, standards discovery, work item resolution, and the Approach Gate (it passed in iteration 1; the orchestrator sanity-checks the delta during synthesis instead).

- **Delta diff**: `git diff --no-prefix -U50 {reviewedCommit}..HEAD > .CodeReview/.{BranchName}.diff` and `git diff --name-only {reviewedCommit}..HEAD` for the delta file list
- **Worktree setup**: same as full review (`review-workflow.md` §4)
- **Neighbor discovery**: only for delta files NOT already in `exemplarMap` (extend the map; don't redo it)

### 2. Escalation check (orchestrator, before dispatch)

The single-agent path assumes the delta is "fixes plus a little new code". Escalate to the **full 5-agent fan-out on the delta diff** (still reusing the sidecar and skipping discovery) when EITHER:

- Delta exceeds **400 changed lines** (added + removed, from `git diff --shortstat`), OR
- Delta touches files **outside `reviewedFiles`** that aren't trivially related (new source files in new areas — test/doc-only additions don't count)

When escalating, each deep-dive agent additionally receives the prior report path with the instruction to check whether prior findings in its domain are resolved.

### 3. Gate + Delta Reviewer (parallel)

Dispatch both in a single message using the standard path-based prompt:

| Agent | File | Context |
|---|---|---|
| Build Validator | `agents/build-validator.md` | Worktree path, project paths (haiku) |
| Delta Reviewer | `agents/delta-reviewer.md` | Worktree path, delta diff file path, **prior report path**, work item summary (1–3 lines), delta file list (sonnet) |

Build `Gate Result: FAIL` → Build Fail short report (`short-reports.md`) → cleanup → STOP. The Delta Reviewer's output is discarded in that case.

### 4. Synthesis (orchestrator, opus)

1. **Re-verify resolution claims on Must Fix items at P1 rigor** — re-read the fixed code in the worktree for every prior Must Fix the Delta Reviewer marked Resolved. Should Fix/Consider resolutions can be trusted unless they look off.
2. **Regenerate the FULL report** at `.CodeReview/{BranchName}.md` (template: `report-template.md`):
   - Findings on files untouched by the delta → carry forward verbatim from the prior report
   - Resolved findings → remove (their `[mf:slug]` disappears from Must Fix — that is how `code-review-publish` detects resolution)
   - Unresolved/Partial findings → keep with **unchanged slugs**
   - New findings → add; new Must Fix items get new slugs
   - Header: bump `**Iteration**`, update `**Reviewed Commit**`
3. **Run the ADO autolink guard** (fix + check) as in the full pipeline
4. **Update the sidecar**: new `reviewedCommit`, merged `reviewedFiles` (union with delta files), extended `exemplarMap`, bumped `iteration`, new `reviewedAt`

### 5. Cleanup

Same as the full pipeline: remove worktrees, delete the diff file, keep report + sidecar.

## Token Rationale

Iteration 1 already paid for discovery and the 5-lens scan. A follow-up only needs to answer "are the prior findings fixed?" and "did the fixes break anything?" — both answerable from the prior report plus a small delta. Typical follow-up cost is one fast build agent plus one standard agent on a small diff, instead of six agents on the full diff.
