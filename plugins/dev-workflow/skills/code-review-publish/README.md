# Code Review Publish

## Purpose

Take a `code-review-pro` report (e.g., `.CodeReview/{branch}.md`), attach it to an Azure DevOps work item, and post a single concise discussion comment that @mentions the developer with the Must Fix shortlist. On follow-up runs after the developer pushes fixes, edit the same comment in place with a "Resolved N/M" banner instead of cluttering the thread with new comments.

## Pain Points Addressed

- Manual ADO REST calls for attachments + raw `<a data-vss-mention>` HTML are non-repeatable
- Hand-composing Must Fix summaries from review reports is tedious and drifts from the source
- Re-running review on iterated code spawns duplicate comments, hurting discussion clarity
- No persistent record of which Must Fix items were resolved across iterations
- Author identity resolution (PR.createdBy → WI.assignedTo → ask) is implicit knowledge, lost between sessions

## Design Notes

- Direction "D" from brainstorm 2026-05-07: thin orchestration skill on top of `ado` CLI primitives (`ado attach`, `ado comment-edit`) added the same day. The skill owns parsing, identity, state, follow-up diff. The CLI owns auth, REST, HTML conversion.
- Edit-in-place comment strategy chosen over append-new — discussion clarity > history. Followup banner ("Resolved N/M") preserves audit trail in the comment body itself.
- Stable `[mf:slug]` tags on Must Fix bullets enable iteration diff. Slugs are the contract between `code-review-pro` skill (producer) and `code-review-publish` (consumer).
- State file `.CodeReview/.{branch}.publish.json` is per-branch. Multi-WI per branch not supported in v1.
- Identity cache `~/.claude/.ado-identity-cache.json` avoids Graph queries on repeat publishes to same author.

## Changelog

### 2026-06-10 - PR-thread target (v1.1.0)
- Added a second publish target: **pull request thread** (alongside the existing work-item flow).
- Motivation: published the PR-75324 review manually via raw `az rest` to the PR threads API + a hand-typed `@<GUID>` mention — the same non-repeatable pain the WI flow was built to kill, now for PRs.
- PR mode posts the **full report inline** (PR threads have no attachment), prefixed with `Hi @<GUID>, please help me check this code review result:` + `---`. Mention target resolved directly from `PR.createdBy` via `az repos pr show` — no identity cache needed.
- Followup behaviour (user choice): **new thread + resolve the prior thread** (`PATCH status=closed`), preserving per-iteration history — distinct from WI mode's edit-in-place.
- Mention syntax `@<GUID>` is the documented Markdown-editor form; posting it raw via REST registers a true mention + notifies (verified against MS docs + the live PR-75324 comment).
- Files added: `scripts/pr_publish.py` (`pr-info` + `publish`, with `--dry-run`), `references/pr-publish.md`. SKILL.md now routes WI vs PR up front. No change to the WI flow.

### 2026-05-07 - Initial (v1.0.0)
- Created skill `code-review-publish`
- Motivation: published US-1987 review manually (raw `Invoke-RestMethod` + hand-built HTML mention) — painful, slow, non-repeatable
- Companion changes:
  - Added `ado attach <id> --file` + `ado comment-edit <id> <commentId>` subcommands (`Script/scripts/ado/`)
  - Added `Add-AzureDevOpsWorkItemAttachment` + `Update-AzureDevOpsWorkItemComment` to `AzureDevOpsClient.psm1`
  - Updated `code-review-pro/references/report-template.md` to require `[mf:{slug}]` tags on Must Fix bullets
- Files: SKILL.md, README.md, references/{comment-template,workflow-detail,identity-resolution,must-fix-slug-strategy,followup-diff}.md, scripts/{parse_must_fix.py,publish_state.py}
