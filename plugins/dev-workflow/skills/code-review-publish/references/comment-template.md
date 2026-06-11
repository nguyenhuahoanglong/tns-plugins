# Comment Template

Render this template into the comment body. Substitution fields use `{{double-brace}}`. After substitution, the result is markdown — `ado comment` / `ado comment-edit` convert to HTML automatically (HTML conversion is the default in those CLI subcommands; the inline `<a data-vss-mention>` tag survives the conversion intact).

## Template

```markdown
<a href="#" data-vss-mention="version:2.0,{{guid}}">@{{name}}</a> code review {{iteration_label}}: [{{filename}}]({{attachment_url}}). Build {{build_status}}. {{n_high}} HIGH must-fix.

{{resolved_banner}}

**Must Fix:**
{{bullets}}

Push back on any item w/ reasoning if disagree.
```

## Field substitutions

| Field | Source | Example |
|---|---|---|
| `{{guid}}` | identity resolution | `a046b071-4c1f-60bc-8970-9a33752df8ec` |
| `{{name}}` | display name from PR.createdBy / WI.assignedTo | `Thuong Cao` |
| `{{iteration_label}}` | computed | initial: `attached`. Followup: `update {{n}}` |
| `{{filename}}` | basename of report | `US-1987.md` |
| `{{attachment_url}}` | `ado attach` response or state file | `https://dev.azure.com/.../attachments/0cd...` |
| `{{build_status}}` | `parse_must_fix.py` output | `PASS` / `FAIL` |
| `{{n_high}}` | counts.high from parse | `4` |
| `{{resolved_banner}}` | followup only — empty for initial | see below |
| `{{bullets}}` | Must Fix bullets, numbered | see below |

## Resolved banner (followup only)

When `iteration > 1`, prepend (between mention line and `**Must Fix:**`):

```markdown
**Iteration {{iteration}}** — Resolved {{resolved_count}}/{{total_count}}: {{resolved_slugs_joined}}.
```

If all items resolved (`remaining_count == 0`), use:

```markdown
**Iteration {{iteration}}** — All Must Fix resolved ({{total_count}}/{{total_count}}). Ready for re-review.
```

…and replace the entire `**Must Fix:**` block with: `_(none remaining — see attachment for full report)_`.

For initial iteration (`iteration == 1`), `{{resolved_banner}}` = empty string (template renders a blank line; harmless).

## Bullets format

Each remaining Must Fix item is rendered as one line:

```markdown
{n}. {original-bullet-text-without-the-mf-tag}
```

Example (from US-1987 report):

```markdown
1. Access-control broadening in `GetDistributionFailures` + `GetDistributionErrorSummary` — restore allowlist or confirm intent.
2. NRE risk in same handlers when scope lists partial-null — null-coalesce locals.
3. `GetDistributionHistoryByIdCommandHandler.cs:778` — inner detail uses raw `s.StatusCode`; apply `ComputeMdmProcessStatus`.
4. `FinalizeRunHistoryAsync` reloads detail rows on explicit-status path — gate fetch behind `if (processStatus == null)`.
```

Strip the `[mf:{slug}]` tag from the rendered bullet (slug is internal — clutters the comment). Keep `[CRITICAL]` / `[HIGH]` / `[Agent]` tags only if the bullet is short; drop them if the bullet exceeds ~140 chars.

## Truncation

Cap total comment length at 30 KB (ADO comment soft limit ~32 KB). If over:

1. Drop `[Agent]` tags from bullets first.
2. Truncate bullet text to ~120 chars w/ `…`.
3. If still over, replace `**Must Fix:**` block with: `**Must Fix:** {n} HIGH items — see attachment.`
