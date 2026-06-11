# Must-Fix Slug Strategy

Slugs are the contract between `code-review-pro` (producer) and `code-review-publish` (consumer). They enable iteration diff: if `slug-X` appears in iteration N's report but not N+1's, it's resolved.

## Slug rules

- **Format**: kebab-case, `[a-z0-9-]+`, ≤24 chars
- **Source**: derived from the issue noun phrase (`auth-broaden`, `nre-risk`, `raw-statuscode`, `finalize-reload`)
- **Stability**: do NOT change a slug across iterations unless the underlying issue is genuinely different. If the reviewer rewords a Must Fix bullet, keep the slug.
- **Uniqueness**: unique within a single report. Reviewer enforces by inspection; the parser flags duplicates as an error.
- **Tag location**: inline in the bullet, after agent tags: `[CRITICAL] [Security] [mf:auth-broaden]`

## Regex

```
\[mf:([a-z0-9][a-z0-9-]{0,23})\]
```

Used by `scripts/parse_must_fix.py` to extract slugs.

## Producer responsibility

`code-review-pro` skill's report-template.md (updated 2026-05-07) requires the slug column. The orchestrator (Phase 4 synthesis) assigns slugs when consolidating Must Fix items. Slug pool examples:

| Issue type | Slug pattern |
|---|---|
| Access control broadened | `acl-broaden`, `auth-broaden` |
| Null reference / NPE | `nre-{site}` (e.g., `nre-scope`) |
| Wrong enum / status code | `wrong-{enum}` |
| Redundant DB call | `dup-fetch` |
| Missing validation | `no-validate-{field}` |
| Resource leak | `leak-{resource}` |

When unsure, use `mf:{first-3-words-kebab}` (e.g., `mf:access-control-broaden`) — readable beats clever.

## Conflict resolution

If iteration N+1's report introduces a NEW Must Fix item with a slug that's identical to a resolved item from N: the parser treats them as the same item (resurrection). Reviewer should pick a fresh slug if it's a different issue at the same site.

## Why slugs over hashing `file:line`

- Line numbers shift across iterations
- File renames break hash continuity
- Slugs are reviewer-authored, semantic, stable through refactor
- Slugs let the comment body diff stay human-readable ("Resolved: auth-broaden, nre-risk")

## Failure mode

Parser exits 1 if any Must Fix bullet lacks `[mf:{slug}]`. The skill propagates the error and prompts the reviewer to add slugs to the report before re-running publish. Do NOT auto-generate slugs at publish time — they'd drift across iterations because the LLM might pick different words for the same issue.
