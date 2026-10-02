---
name: chrome-devtools
description: "Use when live Chrome evidence is needed after implementation: browser E2E, console/network debugging, screenshots, or performance traces via official Chrome DevTools MCP. Keep project runners for CI."
---

# Chrome DevTools

Use the official `chrome-devtools-mcp` server. Load this skill when a task needs
evidence from a live Chrome page: post-implementation browser behavior, a
headed manual check, DOM or JavaScript inspection, console or network
diagnosis, screenshots, or performance traces.

## Route and prerequisites

- For browser-visible acceptance criteria after implementation, route the
  requirements-based check through `browser-skill` and `qa-engineer`.
- Keep Playwright, Cypress, or another project E2E runner for repeatable
  suites and CI. This skill does not replace those tests.
- Confirm the target environment, test data, expected result, and allowed
  mutations before acting. Missing browser tools, runtime, environment, or
  test-data authority means `NOT RUN` or `BLOCKED`; never claim `PASS`.
- Use only an available MCP tool. Do not invent tool names or silently fall
  back to a different browser backend.

## Browser session

The MCP server starts Chrome on its first browser call and keeps a persistent
profile unless configured otherwise. The installed 1.9.0 server uses
selected-page routing: call `select_page` and follow the parameter schema
exposed by `tools/list`. Do not assume a `pageId` parameter; if another server
exposes pageId routing, pass it only where its `tools/list` schema requires it.

- Call `list_pages` first. Use `new_page` for a new target, or
  `navigate_page` for an authorized existing page, then `select_page` before
  page-scoped actions.
- MCP runs headed by default (`--headless` defaults to `false`). Keep the
  window visible when the user asks to watch verification.
- The experimental CLI enables headless mode by default. For a visible CLI
  session use `chrome-devtools start --headless=false` explicitly.
- Use a separate or isolated profile when session separation is required. Do
  not enter passwords, tokens, or other credentials; let the user sign in.

## Interaction workflow

1. `list_pages`, then `new_page` or `navigate_page` to the exact target.
2. `wait_for` a known page condition when loading is asynchronous.
3. `take_snapshot` on the selected page; use returned element `uid` values.
4. Perform one action (`click`, `fill`, `fill_form`, `type_text`, or
   `press_key`) at a time. Re-snapshot after navigation or DOM changes because
   `uid` values are ephemeral.
5. Verify the observable result with a fresh snapshot, `evaluate_script`, or a
   targeted screenshot. Capture console and network evidence when relevant.

Prefer snapshots for structure and text. Use `take_screenshot` when visual
state matters or the user needs to see the page. Use `evaluate_script` only
for a specific DOM/runtime question and follow its `tools/list` parameters.

## E2E evidence

Record target URL/environment, page or form identity, build or bundle
identity when available, action, expected result, observed result, and
evidence path. Report each case as `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`.
Read back persisted data after saves. Restore edited test data and remove only
rows created by the current run when the approved test scope permits it.
Redact credentials, cookies, authorization headers, and personal data from
reports and screenshots. Close only pages created by the current task.

## Diagnostics

- Console: `list_console_messages`, then `get_console_message` for a specific
  entry.
- Network: `list_network_requests`, then `get_network_request` for a request
  or response body. Use filtering and pagination for large pages.
- Performance: `performance_start_trace`, `performance_stop_trace`, and
  `performance_analyze_insight`; use `lighthouse_audit` for non-performance
  audits.
- Runtime state: use a focused `evaluate_script` call. If the server exposes
  the optional styling category, `get_css_styles` can inspect resolved CSS
  using a snapshot `uid`.

If MCP cannot launch or connect, read the official troubleshooting guide and
report the exact blocker. Do not treat a static skill check as browser
verification.

## Reference

See the local [README](README.md) for ownership, Windows setup, and the pinned
upstream source. Official references:

- <https://github.com/ChromeDevTools/chrome-devtools-mcp>
- <https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/tool-reference.md>
- <https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/troubleshooting.md>
