# PR Publish (PR-thread target)

Publishing a code review to a **pull request** is a distinct target from the
work-item flow. PR discussion threads have no attachment mechanism, so the
**full report is posted inline** — the opposite of the WI flow's "link +
summary". This is intentional and matches the established house style (see the
reference example below).

## When PR mode is selected

- User passes `--pr <id>` / runs `/publish-review pr <id>`, or the request
  names a PR ("post the review to PR 75324", "comment on the PR").
- The report exists (default `.CodeReview/{branch}.md`).

## Comment body shape

```
Hi @<{GUID-UPPERCASE}>, please help me check this code review result:

---
{full report markdown, verbatim}
```

- **Greeting line** — `Hi @<GUID>, please help me check this code review result:`
  The `@<GUID>` token is the **Markdown-editor mention syntax** (the org uses the
  Markdown comment editor). Posting it raw via REST registers a *true* mention
  and emails the user. (Per Microsoft docs, copy-pasting a rendered mention from
  the UI does **not** notify — but the raw token does, which is what we post.)
- **`---` separator** then the **entire report**, unmodified. No summarizing, no
  Must Fix shortlist extraction — the reader sees the whole report in-thread.
- GUID is uppercased to match the canonical example; ADO accepts either case.

`scripts/pr_publish.py publish` runs `ado_autolink_guard.py fix` + `check` on
the report before composing the body. This prevents accidental ADO work-item
links from raw `#number` refs such as `PR \#1489` or `AC \#4`. Raw `#number`
survives only for explicit work-item contexts like `Work Item #1795`. In
`--dry-run`, the script previews the sanitized body without writing the report;
real publish fixes the report file in place before posting.

`scripts/pr_publish.py publish` composes this body for you — don't hand-build it.

## Mention target (no identity cache needed)

`az repos pr show --id <pr>` returns `createdBy.id` (the GUID) and
`createdBy.displayName` directly, so PR mode resolves the mention **without** a
Graph query or the `~/.claude/.ado-identity-cache.json` lookup that WI mode uses.

Override order: `--mention-guid` (explicit) > `PR.createdBy`. Use an override
only when the reviewer wants to mention someone other than the PR author.

## API calls (wrapped by `pr_publish.py`)

| Action | Method + URI | Body |
|---|---|---|
| Post new thread | `POST {org}/{project}/_apis/git/repositories/{repo}/pullRequests/{pr}/threads?api-version=7.1` | `{comments:[{parentCommentId:0, content, commentType:1}], status:1}` |
| Resolve prior thread (followup) | `PATCH .../threads/{threadId}?api-version=7.1` | `{status:"closed"}` |

`--resource 499b84ac-1321-427f-aa17-267ca6975798` (the ADO AAD resource) is
required on every `az rest` call. Repo can be the **name** in the URI path — no
repo GUID needed.

Thread `status`: `1` = active (new thread). Resolve states: `closed`, `fixed`,
`wontFix`, `byDesign`. Default resolve = `closed`.

## Followup behaviour — new comment + resolve old

On a followup run (state file already records a `threadId`):

1. Post a **fresh thread** with the new report (the prior report stays visible in
   its own resolved thread — full per-iteration history, which the reviewer
   chose over edit-in-place for PRs).
2. **Resolve the prior thread** (`PATCH status=closed`) so the active thread is
   always the latest review.
3. Persist the new `threadId` / `commentId` and bump `iteration`.

`pr_publish.py publish --prior-thread <id>` does steps 1–2 atomically; pass the
prior `threadId` from the state file.

## State file (PR variant)

`.CodeReview/.{branch-sanitized}.pr-publish.json`:

```json
{
  "prId": 75324,
  "branch": "US/410849",
  "threadId": 246619,
  "commentId": 1788234,
  "priorThreadIds": [246511],
  "mentionGuid": "a046b071-4c1f-60bc-8970-9a33752df8ec",
  "mentionName": "Thuong Cao Thi",
  "iteration": 2,
  "postedAt": "2026-06-10T08:30:00Z"
}
```

Separate filename suffix (`.pr-publish.json`) so a branch can carry both a WI
publish and a PR publish without collision. Reuse `publish_state.py read|write`
for CRUD — the shape is just extra fields.

## Anti-patterns (PR-specific)

- **Don't** summarize or drop sections — PR mode posts the full report inline.
- **Don't** attach a file — PR threads render inline; there is no attachment step.
- **Don't** edit the prior comment in place — followup posts a *new* thread and
  resolves the old one (PR threads have resolve semantics WIs lack).
- **Don't** mention multiple reviewers unless asked — default is `PR.createdBy`.
- **Don't** change the PR's vote/status or auto-complete — only thread status.
- **Don't** bypass the ADO autolink guard — it is required before posting the full
  report inline.

## Verification

After a real (non-dry-run) post:
1. Open the PR → the new thread shows the greeting with a live mention **chip**
   (blue link), and the full report rendered below the `---`.
2. The mentioned developer receives an email notification.
3. Followup: prior thread shows **Resolved**, newest thread is **Active**.
4. State file `iteration` matches run count; `priorThreadIds` lists resolved ones.

Use `--dry-run` first to preview `bodyPreview` + `mentionGuid` without posting.
