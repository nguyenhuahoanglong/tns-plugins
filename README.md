# claude-plugins

Team Claude Code plugin marketplace.

> **DO NOT HAND-EDIT.** This repo is generated from the maintainer's Script source by `Publish-Plugin.ps1`. Any manual changes here are overwritten on the next publish. File bugs or request changes upstream with the maintainer.

## Install (team members)

In Claude Code:

```
/plugin marketplace add nguyenhuahoanglong/claude-plugins
/plugin install dev-workflow@team-marketplace
```

That's it. The `dev-workflow` plugin registers three skills (`code-review`, `implement-plan`, `implement-feature`) and three sub-agents (`code-reviewer`, `code-implementer`, `qa-engineer`).

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
