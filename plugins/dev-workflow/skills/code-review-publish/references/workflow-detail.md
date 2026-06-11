# Workflow Detail

Full step-by-step including error paths and decision points. Read this when SKILL.md's pipeline table is too terse for an edge case.

## Phase 1 — Detect mode

```
branch = git branch --show-current
sanitized = branch.replace("/", "-")  # US/1987 → US-1987
state_path = ".CodeReview/.{sanitized}.publish.json"

if subcommand == "followup":
    if not state_path.exists(): FAIL "no prior publish state — run /publish-review <wi> first"
    mode = "update"
elif state_path.exists():
    ASK user: "publish state exists for {branch} (iteration {n}). Choose: followup | re-attach | skip"
    mode = mapped from answer
else:
    mode = "initial"
```

If `--report` flag absent, default to `.CodeReview/{sanitized}.md`. If that file doesn't exist, FAIL "no report at {path} — run /code-review-pro first or pass --report".

## Phase 2 — Resolve mention

Order:
1. `--mention <email>` — use directly. Skip to GUID lookup.
2. `--pr <ids>` — call `az repos pr show --id <first-id> --query createdBy.uniqueName -o tsv`. Use returned email.
3. `ado get <wi> --format summary` (or read AssignedTo from work item JSON via `az rest`). Use AssignedTo email.
4. `AskUserQuestion` — list candidates from steps 2-3 + free-form "Other".

After email resolved → GUID lookup per `identity-resolution.md`.

If `--mention` absent AND PR.createdBy ≠ WI.assignedTo, prefer PR.createdBy (the actual code author) and `AskUserQuestion` to confirm. Don't silently pick.

## Phase 3 — Sanitize + parse report

Run the ADO autolink guard before parsing or attaching:

```bash
python scripts/ado_autolink_guard.py fix "<report>"
python scripts/ado_autolink_guard.py check "<report>"
```

Stop if `check` fails after `fix`. Raw `#number` is allowed only for explicit work-item refs.

Run `python scripts/parse_must_fix.py <report-path> --out <tmp.json>`.

Output JSON shape:
```json
{
  "buildStatus": "PASS",
  "counts": {"critical": 0, "high": 4, "medium": 8, "low": 4},
  "mustFix": [
    {"slug": "auth-broaden", "severity": "HIGH", "agents": ["Security", "Requirement (Approach)"], "text": "Access-control broadening...", "fileLine": "GetDistributionFailuresQueryCommandHandler.cs:640-680"},
    ...
  ]
}
```

If any Must Fix bullet lacks `[mf:{slug}]`, the script exits non-zero w/ stderr listing offending lines. The skill MUST fail and ask the reviewer to add slugs (don't auto-generate — slugs need to be stable across iterations).

If the report has zero Must Fix bullets, suggest user runs `ado comment <wi> --text "Reviewed — no Must Fix items. See attached report."` instead.

## Phase 4 — Attach (or reuse)

Initial:
```
ado attach <wi> --file <report> --link-comment "Code review iter 1"
→ capture {attachmentId, attachmentUrl}
```

Update (followup w/o `--re-attach`):
- Reuse `state.attachmentUrl` and `state.attachmentId`.
- If reviewer regenerated the report, the URL still points to the original snapshot. That's intentional — the comment links the most recent published artifact, not the live working copy. If the reviewer wants the new content visible, pass `--re-attach`.

Update with `--re-attach`:
- Run `ado attach` again. Update `state.attachmentId`, `state.attachmentUrl`. Old attachment remains on the WI (ADO doesn't delete; user prunes manually if desired).

## Phase 5 — Compose comment

For initial: `iteration_label = "attached"`, `resolved_banner = ""`.

For update: 
- `iteration_label = "update {iteration+1}"` (state's iteration counter is incremented in phase 7)
- Run `python scripts/publish_state.py diff <state-path> <new-report>` → JSON `{resolved: ["slug1"], remaining: ["slug2", ...], new: []}`
- Compute `resolved_count = len(resolved)`, `total_count = len(state.mustFixSlugs)`, `remaining_count = len(remaining)`
- Render banner per `comment-template.md` rules

For each remaining Must Fix in the new report, render a numbered bullet (template rules in `comment-template.md`).

If `len(new) > 0`, new Must Fix items appeared — append them to the bullets list w/ a `(NEW)` prefix.

Write composed body to `tmp/publish-comment-{wi}-{iter}.md`.

## Phase 6 — Post / Edit

Initial:
```
ado comment <wi> --file tmp/publish-comment-{wi}-1.md
→ capture {commentId, createdDate}
```

Update:
```
ado comment-edit <wi> {state.commentId} --file tmp/publish-comment-{wi}-{iter}.md
```

If POST/PATCH fails → log error, DO NOT write state file. The skill is atomic at the publish boundary — partial state corrupts followup logic.

## Phase 7 — Persist state

```
state = {
  wiId: <wi>,
  branch: <branch>,
  commentId: <from phase 6 if initial; preserve from prior if update>,
  attachmentId: <from phase 4>,
  attachmentUrl: <from phase 4>,
  mentionGuid: <from phase 2>,
  mentionEmail: <from phase 2>,
  mentionName: <from phase 2>,
  mustFixSlugs: <from phase 3, full list>,
  iteration: <prior + 1, or 1 for initial>,
  postedAt: <ISO 8601 UTC>
}
publish_state.py write <state-path> <state-json>
```

Print to user: comment URL, attachment URL, resolved count (followup), remaining slugs.

## Failure recovery

- Phase 4 fail: report user-facing error w/ ADO error message. No state written.
- Phase 6 fail (initial): attachment exists on WI but no comment. Re-run skill — the orphan attachment remains; pass `--re-attach false` (default) won't double-attach because no state exists yet... but a duplicate attachment will appear. Acceptable; user prunes.
- Phase 6 fail (update): prior comment unchanged. Re-run skill (same `followup` invocation) — idempotent because edit-in-place.
- Phase 7 fail (write): publish succeeded but state lost. Manual recovery: re-run with `--mention <email>`; the skill will re-publish (creating a duplicate comment in initial mode). Mitigation: write state first to a `.tmp` file, atomic rename on success.
