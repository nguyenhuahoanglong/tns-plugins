---
name: code-review-publish
description: Publish a code-review report to an ADO work item or a pull request thread, @mentioning the author. Use for "publish review", "comment review on the PR", "follow up the review", /publish-review.
version: 1.1.0
---

# Code Review Publish

## When to use

- Right after `/code-review-pro` finishes — orchestrator should propose this skill.
- User says: "publish the review", "post review to ADO", "comment the review on the PR", "send the code review to {dev}", "follow up on review for US-{n}", `/publish-review`.
- Skip when: the target WI/PR is closed/abandoned. For WI mode, if the report has no Must Fix items, suggest a one-line `ado comment` instead.

## Two targets — route first

| Target | Trigger | Body | Followup | Detail |
|---|---|---|---|---|
| **Work item** | `<wi-id>` (numeric, no `--pr`) | Attach report file + **concise** @mention summary with Must Fix shortlist | Edit comment in place ("Resolved N/M" banner) | rest of this file |
| **Pull request** | `--pr <id>` / `pr` subcommand / request names a PR | **Full report inline** + greeting that @mentions PR author; no attachment | **New** thread + **resolve** prior thread | `references/pr-publish.md` |

PR mode is deliberately the opposite of the WI anti-pattern "don't repeat the full review" — PR threads have no attachment, so the full report goes inline. Read `references/pr-publish.md` before running PR mode; the rest of this file is the WI flow.

## Inputs

```
# Work-item target
/publish-review <wi-id> [--report <path>] [--pr <ids>] [--mention <email>] [--re-attach]
/publish-review followup <wi-id> [--report <path>]

# Pull-request target
/publish-review pr <pr-id> [--report <path>] [--mention <guid|email>]
/publish-review pr followup <pr-id> [--report <path>]
```

| Arg / flag | Default | Notes |
|---|---|---|
| `<wi-id>` | required (WI mode) | ADO work item id (e.g., 1987) |
| `pr <pr-id>` | required (PR mode) | ADO pull request id (e.g., 75324) |
| `--report` | `.CodeReview/{current-branch}.md` | Report path (sanitize branch slashes → dashes) |
| `--pr` | none | WI mode: comma-separated PR ids for author lookup via `az repos pr show` |
| `--mention` | resolved | Override mention target. WI: email→GUID. PR: pass GUID or email |
| `--re-attach` | false | WI followup: re-upload the report even if state has prior `attachmentUrl` |

## ADO autolink guard

Before any PR inline post or WI attachment, sanitize the report:

```bash
python scripts/ado_autolink_guard.py fix "<report>"
python scripts/ado_autolink_guard.py check "<report>"
```

ADO renders raw `#123` as a work-item link. Raw `#number` is allowed only for explicit intentional work-item contexts (`Work Item #123`, `Parent #123`, `WI #123`, `ADO #123`). The guard escapes all other refs (`PR \#1489`, `AC \#4`, `Philosophy \#23`). Do not publish if `check` fails after `fix`.

## PR mode pipeline

| Phase | Action | Tool |
|---|---|---|
| 1 Detect | Read `.CodeReview/.{branch}.pr-publish.json` → `followup` if `threadId` present (forces resolve-prior). | filesystem |
| 2 Resolve mention | `--mention` GUID/email > `PR.createdBy` (from `pr-info`). No identity cache needed. | `pr_publish.py pr-info` |
| 3 Compose + post | Run ADO autolink guard `fix` + `check`, then greeting + `---` + **full report inline**; POST new active thread. Followup: also resolve prior thread. | `pr_publish.py publish [--prior-thread <id>]` |
| 4 Persist | Write state w/ `prId, threadId, commentId, priorThreadIds[], mentionGuid, iteration, postedAt`. | `publish_state.py write` |

Always `--dry-run` first to preview the body + mention GUID before posting. Full step detail, API shapes, and verification: `references/pr-publish.md`.

## Verify Output

PR mode (deterministic local checks): write the dry-run `bodyPreview` to a file and run `scripts/verify_output.py body <file>` to confirm the greeting + `@<GUID>` + `---` + report shape + no accidental ADO `#number` autolinks; after persisting state, run `scripts/verify_output.py state <.pr-publish.json>`. The live mention chip, dev notification, and prior-thread resolution are confirmed in the PR UI (see `references/pr-publish.md`).

## WI mode pipeline

| Phase | Action | Tool |
|---|---|---|
| 1 Detect | Read state file `.CodeReview/.{branch}.publish.json` → mode = `update` if exists, else `initial`. Subcommand `followup` forces `update`. | filesystem |
| 2 Resolve mention | `--mention` > PR.createdBy > WI.assignedTo > AskUserQuestion. Email → GUID via cache or Graph. See `references/identity-resolution.md`. | `az repos pr show`, `ado get`, `az rest` |
| 3 Sanitize + parse report | Run ADO autolink guard `fix` + `check`, then extract Build Status row, Must Fix bullets w/ slugs + severities, total counts. | `scripts/ado_autolink_guard.py`, `scripts/parse_must_fix.py` |
| 4 Attach | `initial` → `ado attach <wi> --file <report> --link-comment "Code review"`. `update` → reuse prior `attachmentUrl` unless `--re-attach`. | `ado attach` |
| 5 Compose | Render `references/comment-template.md` w/ `{guid, name, filename, attachment_url, build_status, n_high, bullets, iteration_label, resolved_banner}`. | text |
| 6 Post / Edit | `initial` → `ado comment <wi> --file <tmp>`. `update` → `ado comment-edit <wi> <commentId> --file <tmp>`. | `ado comment`, `ado comment-edit` |
| 7 Persist | Write state file w/ `commentId, attachmentId, attachmentUrl, mentionGuid, mustFixSlugs[], iteration, postedAt`. | `scripts/publish_state.py write` |

For followup: phase 3 also runs `publish_state.py diff <prior-state> <new-report>` → `{resolved[], remaining[], new[]}`. Phase 5 prepends iteration banner. Phase 6 always edits in place.

## Anti-patterns

- **Don't** repeat the full review in the comment — link + summary only.
- **Don't** @mention multiple people unless the user explicitly asks.
- **Don't** auto-transition the WI state; suggest only.
- **Don't** post if attach failed — atomic. State file written only when phases 4-6 all succeed.
- **Don't** publish reports with accidental raw `#number` refs — run `ado_autolink_guard.py fix` then `check` first.
- **Don't** re-attach on every iteration; reuse the prior attachment URL unless `--re-attach`.
- **Don't** silently re-publish — if `.publish.json` exists and the user didn't pass `followup`, ask: "publish state exists for this branch — followup, re-attach, or skip?"
- **Don't** fabricate slugs — slugs come from the report's `[mf:slug]` tags. If a Must Fix bullet lacks a slug, fail and ask the reviewer to add one.

## State file shape

`.CodeReview/.{branch-sanitized}.publish.json`:

```json
{
  "wiId": 1987,
  "branch": "US/1987",
  "commentId": 14081617,
  "attachmentId": "0cd09271-...",
  "attachmentUrl": "https://dev.azure.com/.../attachments/...",
  "mentionGuid": "a046b071-...",
  "mentionEmail": "review.author@example.com",
  "mentionName": "Review Author",
  "mustFixSlugs": ["auth-broaden", "nre-risk", "raw-statuscode", "finalize-reload"],
  "iteration": 1,
  "postedAt": "2026-05-07T05:44:48Z"
}
```

## Identity cache

`~/.claude/.ado-identity-cache.json` — flat `{email: guid}` map. Populate on Graph hit. Read first, write on miss. See `references/identity-resolution.md`.

## Verification

After running:
1. `az rest GET _apis/wit/workitems/{wi}?$expand=relations` shows the AttachedFile.
2. WI Discussion in browser shows: comment with @mention chip rendered as live link, attachment link clickable, Must Fix bullets numbered.
3. State file exists and `iteration` matches the run count.
4. Followup re-run: prior comment carries "edited" badge; banner reads "Resolved {x}/{y}: {slugs}".

## References

- `references/pr-publish.md` — **PR-thread target**: inline body, mention, API shapes, resolve-prior followup, PR anti-patterns
- `references/workflow-detail.md` — WI flow full step-by-step including error paths
- `references/identity-resolution.md` — author lookup chain, Graph query, cache shape (WI mode)
- `references/must-fix-slug-strategy.md` — slug rules, regex, conflict resolution across iterations
- `references/followup-diff.md` — diff algorithm, banner rules, edit-in-place rationale
- `references/comment-template.md` — the WI comment body template

## Scripts

- `scripts/ado_autolink_guard.py check|fix <report.md>` — sanitize accidental ADO `#number` autolinks; raw `#number` remains only for intentional work-item refs.
- `scripts/pr_publish.py pr-info|publish` — PR mode: resolve PR author + post inline report thread + resolve prior thread. Supports `--dry-run`.
- `scripts/parse_must_fix.py <report.md>` — JSON `{buildStatus, mustFixSlugs[], mustFixBullets[], counts}`. Pass `--out <file>` to write JSON to file. (WI mode.)
- `scripts/publish_state.py read|write|diff|init` — state file CRUD + slug diff. Used by both targets.

## Dependencies

- `az` CLI logged in to ADO tenant (PR mode uses `az repos pr show` + `az rest` PR-thread endpoints)
- `ado` CLI w/ `attach` and `comment-edit` subcommands (WI mode; added 2026-05-07)
- Python 3 for the helper scripts
- `code-review-pro` skill report convention v2 (Must Fix bullets carry `[mf:{slug}]` tags — required by WI mode; PR mode posts the report verbatim)
