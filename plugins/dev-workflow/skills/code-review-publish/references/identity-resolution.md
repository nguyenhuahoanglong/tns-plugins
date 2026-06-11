# Identity Resolution

ADO @mentions need a user GUID, not an email. This file defines the lookup chain and cache.

## Lookup chain

```
Email → GUID
├── 1. Cache hit? Return GUID. ← fast path
├── 2. az rest GET _apis/identities?searchFilter=General&filterValue={email}
│   ├── Resource: 499b84ac-1321-427f-aa17-267ca6975798 (AAD ADO resource ID)
│   ├── Returns: array of identity objects {id, providerDisplayName, properties}
│   └── Pick first match where properties.Mail == email (case-insensitive)
├── 3. Fallback: az devops user list --org <org> | jq for email
└── 4. Manual: AskUserQuestion with the email + "paste the GUID from the WI assigned-to JSON"
```

Cache the result on hit (steps 2 or 3): write to `~/.claude/.ado-identity-cache.json`.

## Cache file shape

```json
{
  "review.author@example.com": {
    "guid": "a046b071-4c1f-60bc-8970-9a33752df8ec",
    "displayName": "Review Author",
    "cachedAt": "2026-05-07T05:44:48Z"
  },
  "review.delegate@example.com": {
    "guid": "a942f61c-b8af-6bb2-a01f-054ab26cb20e",
    "displayName": "Review Delegate",
    "cachedAt": "2026-05-07T05:44:48Z"
  }
}
```

Cache is forever — ADO GUIDs don't change unless a user is deleted and re-created. If a Graph lookup ever returns a different GUID for a cached email (rare), overwrite + log a warning.

## Author selection rules

When deciding whom to mention:

1. **`--mention <email>` flag** → use directly. User override beats inference.
2. **PR.createdBy** → who actually wrote the code. Best default for code review.
3. **WI.assignedTo** → fallback when no PR.
4. **Conflict** (PR.createdBy ≠ WI.assignedTo) → ask. PR author may be a delegate of the assignee.

Edge cases:
- PR has multiple commits from different authors → use PR.createdBy (the PR opener), not commit authors.
- Multiple PRs (e.g., paired BE+FE) → use the first PR's createdBy. If different across PRs, ask.
- PR.createdBy is a service account / bot → fall back to WI.assignedTo, then ask.

## az rest invocation

```bash
az rest \
  --method GET \
  --uri "https://vssps.dev.azure.com/{org}/_apis/identities?searchFilter=General&filterValue={url-encoded-email}&api-version=7.1" \
  --resource "499b84ac-1321-427f-aa17-267ca6975798" \
  --query "value[0].id" -o tsv
```

Note the host is `vssps.dev.azure.com`, not `dev.azure.com` — identities API lives in the SPS service.

## Display name

For `{{name}}` in the comment template, prefer `displayName` from the identity API response (e.g., "Review Author") over the email local-part. Cache stores both.

## Mention HTML format

Final mention markup posted in the comment:

```html
<a href="#" data-vss-mention="version:2.0,{guid}">@{displayName}</a>
```

ADO renders this as a clickable mention chip. `version:2.0` is the current convention (older `data-vss-mention` v1 also works but is legacy). Confirmed working on 2026-05-07 with US-1987 comment.
