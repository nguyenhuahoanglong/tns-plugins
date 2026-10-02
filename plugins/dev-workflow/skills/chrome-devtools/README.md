# Chrome DevTools skill

Canonical skill is an owned adaptation of the official Chrome DevTools MCP
agent guidance. It uses MCP tools for live Chrome inspection and interaction;
the former local Puppeteer script bundle was retired from this skill.

## Purpose

Provide reliable live Chrome evidence for browser-visible acceptance criteria,
debugging, and performance analysis after implementation.

## Pain Points

- Browser backends expose different tools and session behavior.
- Headed verification and authenticated internal apps need explicit session and
  evidence rules.
- Static source checks cannot prove browser behavior.

## Source and ownership

- Upstream: <https://github.com/ChromeDevTools/chrome-devtools-mcp>
- Local reference: `prompts/.cache/chrome-devtools-mcp` relative to the AI-assets repository root.
- Reviewed reference commit: `882f93e9a8809fe88eced35d793951fb456b7117`
- Pinned runtime family: `chrome-devtools-mcp@1.9.0`
- Canonical status: `owned`; do not overwrite through ClaudeKit mirror sync.

The local cache is read-only reference material. Port behavior into this
folder when upstream guidance changes, then validate the owned intent and
skill structure before deployment.

## Windows operation

Use PowerShell with absolute paths for local files. The MCP server is headed by
default (`--headless` defaults to `false`). The experimental CLI is headless
by default, so a visible CLI session must start with:

```powershell
chrome-devtools start --headless=false
```

For MCP clients, keep the server configuration free of `--headless` when the
user needs to watch the browser. Use `--isolated` or a task-specific
`--userDataDir` when session separation is required. Never store credentials
or copied cookies in skill files or evidence.

## Routing

Use after implementation when acceptance criteria require live browser
evidence, especially headed CRM or internal-app checks, console/network
diagnosis, runtime DOM inspection, local bundle verification, screenshots, or
performance traces. Keep the project’s Playwright/Cypress suite for stable,
repeatable CI coverage. If the MCP server or authorized test environment is
unavailable, report `NOT RUN` or `BLOCKED`.

## Changelog

### 2026-09-21 — Owned MCP migration

- Replaced the legacy Puppeteer script skill with official Chrome DevTools MCP
  workflow guidance.
- Added headed Windows behavior, post-implementation E2E routing, evidence
  rules, and ownership metadata.
