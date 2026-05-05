# tns-plugins

Team Claude Code plugin marketplace.

> **DO NOT HAND-EDIT.** This repo is generated from the maintainer's Script source by `Publish-Plugin.ps1`. Any manual changes here are overwritten on the next publish. File bugs or request changes upstream with the maintainer.

## Install (team members)

In Claude Code:

```
/plugin marketplace add nguyenhuahoanglong/tns-plugins
/plugin install dev-workflow@rd-team
```

The `dev-workflow` plugin registers **15 skills** and **3 sub-agents**:

### Workflow skills

| Skill | Purpose |
|-------|---------|
| `code-review-lite` | Parallel code review: build gates + critical/quality reviewers |
| `implement-plan-lite` | Single-agent plan executor from a plan file on disk |
| `implement-feature` | Full feature loop: interview → plan → parallel implementation |

### Dataverse authoring skills

| Skill | Purpose |
|-------|---------|
| `dataverse-plugins` | C# IPlugin authoring — pipeline, anatomy, patterns, deployment |
| `dataverse-web-api` | Web API / REST — tables, columns, relationships, queries, security |
| `dataverse-web-resources` | JS form scripts, ribbon, BPF, side-panes, HTML dashboards |
| `pcf-controls` | PCF TypeScript/React — lifecycle, manifest, component patterns |

### Dataverse ops skills (via Dataverse MCP)

| Skill | Purpose |
|-------|---------|
| `dv-overview` | Router — picks the right specialist for any Dataverse request |
| `dv-connect` | One-step env setup: install tools, auth, register MCP, write `.env` |
| `dv-query` | Data querying — Web API advanced, QueryBuilder, Jupyter |
| `dv-data` | Data import/manipulation — multi-table FK import, sample data |
| `dv-metadata` | Schema management — tables, forms, views, alternate keys |
| `dv-solution` | Solution ALM — export, import, patch, version |
| `dv-security` | Security model — roles, teams, field security |
| `dv-admin` | Org admin — settings overrides, recycle bin, OrgDB |

### Sub-agents

| Agent | Purpose |
|-------|---------|
| `code-reviewer` | Thorough code/PR review |
| `code-implementer` | Multi-file implementation from a plan |
| `qa-engineer` | Test cases, unit tests, coverage, E2E |

## Authentication (first time, per machine)

The repo is private. Claude Code reads it via your existing GitHub credentials:

- **If you use `gh` CLI**: run `gh auth login` once — done.
- **Otherwise**: set `GITHUB_TOKEN` env var to a classic or fine-grained PAT with `repo` scope. Required for silent background auto-updates.

If neither is configured, `/plugin install` prompts for creds interactively.

## Updates

By default, Claude Code notifies you on startup when a plugin update is available and asks for confirmation.

For silent auto-updates, add to `~/.claude/settings.json`:

```json
{
  "marketplaceAutoUpdate": true
}
```

## Versioning convention (maintainer reference)

- **patch** — typo, wording tweak in a reference
- **minor** — new skill, new sub-agent, new reference file, additive change
- **major** — removed/renamed skill or agent, changed sub-agent contract, anything breaking existing behavior

## Publishing (maintainer only)

```powershell
& "C:\Users\LN\.claude\Script\AutomateScript\Plugins\Publish-Plugin.ps1" -PluginName dev-workflow -VersionBump patch
```

Sources live in `C:\Users\LN\.claude\Script\Prompts\source\`. Plugin definitions live in `C:\Users\LN\.claude\Script\AutomateScript\Plugins\plugins-config.json`.
