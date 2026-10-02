# Browser adapter and runtime evidence

Read this before opening or changing a browser. Claude Code and Codex can expose different browser tools and MCP connections. Inspect the live capabilities in the active runtime and use only a browser adapter that is available in that runtime. Do not infer that a Claude MCP exists in Codex, or that Codex browser access exists in Claude. Installing this skill does not install an MCP/browser server, sign in, launch Chrome, or grant Local Overrides access.

## Capability check

Confirm that the active tool can reach the intended Chrome session, identify its actual profile, select the intended tab, inspect actual Network/DevTools state, preserve user tabs, and either capture the required raw resource evidence or expose a loopback CDP target to `capture_runtime.mjs`. Record which capabilities are absent. Browser interaction by itself is not evidence that Chrome executed a newly overridden resource.

On later uses, select the configured browser backend/profile and reuse its folder grant. Do not launch another Chrome process just to make an adapter appear available. The Chrome DevTools MCP `--autoConnect` path is eligible only when the installed Chrome is version 144 or later and the active adapter actually exposes that option; validate the selected profile through `chrome://version` before use. AutoConnect may choose the default profile when several are active, so stop if its reported path is outside the configured scope. On first setup, reuse an already working configured backend/profile. If this is a new machine with no working browser backend, create the dedicated persistent debugging user-data directory below. Do not ask for credentials or handle sign-in; the user signs in themselves.

## First-run profile setup

First read `AGENTS.local.md`, the shared setup receipt and known browser configuration. Reuse a valid working profile and Overrides directory when found, including values written in older prose. Do not change or copy the user's normal Chrome profile. For a new machine without a working configured backend/profile, use a dedicated persistent user-data directory under `%LOCALAPPDATA%\YanaPcfDebug\ChromeProfile`. A separate user-data directory gives this debug session its own browser state and remote-debugging endpoint; it does not copy cookies or sign-in state from regular Chrome.

On Chrome 136 and later, `--remote-debugging-port` and `--remote-debugging-pipe` are ignored for the default Chrome data directory; Chrome requires a non-default `--user-data-dir`. See [Chrome's remote-debugging switch change](https://developer.chrome.com/blog/remote-debugging-port?hl=en). Resolve the actual installed `chrome.exe` from the active backend or machine; do not hardcode an author's installation path. Set `$chromeExe` to that full path and verify it exists. For manual setup, show and run this command with the resolved executable and these exact task-local paths:

```powershell
$chromeExe = '<verified absolute path to this machine’s installed chrome.exe>'
$profileRoot = Join-Path $env:LOCALAPPDATA 'YanaPcfDebug\ChromeProfile'
$overrides = Join-Path $env:LOCALAPPDATA 'YanaPcfDebug\Overrides'
New-Item -ItemType Directory -Force -Path $profileRoot, $overrides | Out-Null
if (-not (Test-Path -LiteralPath $chromeExe -PathType Leaf)) { throw 'Resolve the installed chrome.exe path before starting the debug profile.' }
Start-Process -FilePath $chromeExe -ArgumentList "--user-data-dir=`"$profileRoot`" --remote-debugging-port=9222" -WindowStyle Normal
```

This creates a fresh persistent Chrome user-data directory; the user completes sign-in themselves. Do not add `--remote-allow-origins=*`, expose the port to the network, or copy cookies/profile files. The endpoint is local browser-control access, so use this isolated session for the debug environment. Close only this dedicated process when the task ends and no ongoing debug session needs it; leave normal Chrome sessions open. If port 9222 is already occupied, choose another loopback port and pass that same port to the collector. If Chrome routes this launch into the normal profile or `http://127.0.0.1:9222/json/version` is unavailable, stop and diagnose the actual executable/adapter instead of closing or modifying the user's normal browser.

Open `chrome://version` in the dedicated browser and verify that **Profile Path** is inside the configured user-data root. This skill stores the exact path passed as `--user-data-dir`, while Chrome reports a profile leaf beneath it (usually `Default`). For an existing legacy config that stores a profile leaf instead, require an exact path match and preserve that value; do not rewrite it as a root. In a task-owned form tab, open DevTools **Sources → Overrides**, choose `$overrides`, and let the user grant that folder when Chrome prompts. The user owns sign-in and the browser's folder grant. Validate that the configured user-data directory/profile path and Overrides directory exist and that the selected browser reports a profile inside the configured root or at the exact configured legacy leaf. Show both exact configured paths, then persist the user-data root as `browser_profile=$profileRoot` and the local destination as `overrides_directory=$overrides` with the shared `pcf_setup.py init --scope override --apply` flow. If the user authorized first-run setup, explain and perform this routine setup without asking for a second permission. Do not repeat it on later runs unless a path disappears or the user changes backend/profile.

## Manual handoff

When no usable adapter or CDP target exists, explain that automated browser verification is unavailable and guide the user through only the missing browser steps. This fallback can initialize the dedicated user-data directory as described above; it does not itself prove loaded bytes:

1. For an already configured backend, open its configured profile and intended form. For first setup on a new machine, use the dedicated launch above, complete sign-in yourself, and open the intended form there. Preserve normal Chrome and any tab with unsaved work; create or select a separate test tab before reload.
2. In Chrome DevTools, inspect the Network requests for the selected `YanaGrid` or `YanaQuickView` control. Save each exact request with **Override content** into the configured Overrides folder. Keep the actual request URL and DevTools-created file path; never construct the path from an artifact name.
3. Use DevTools' Local Overrides folder picker only if Chrome reports that the configured folder is not granted. The user chooses and grants the configured folder. A helper mapping is separate from this browser grant.
4. If the active adapter can expose this same existing page as a loopback CDP target, run the supplied collector before reloading the task-owned test tab. Otherwise stop after plan/apply or browser inspection and report runtime bytes `NOT VERIFIED`.

Do not ask the user to install or configure an MCP as a routine workaround. If they explicitly choose to set up a browser adapter, let them perform the installation and then re-detect live capabilities in that runtime.

For a configured Chrome DevTools MCP, use [its advanced usage guide](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/advanced-usage.md) only when that adapter is actually installed and available. It documents Chrome 144+ AutoConnect and manual `--browser-url=http://127.0.0.1:9222` connection. Validate the connected profile path; never count an AutoConnect session as the intended debug profile without that check.

## Required loaded-byte proof

The collector attaches read-only to an existing loopback CDP target. For each required client asset, capture its exact URL and bytes after the override is applied and the task-owned tab is reloaded:

- JavaScript must come from `Debugger.getScriptSource` for the executed script, not a second fetch or a file on disk.
- Stylesheets, images, fonts and other runtime responses must come from actual `Network.getResponseBody` requests with request ID, resource type, load observation and capture time.
- Lazy assets must be loaded by exercising the relevant view. Missing observations remain missing; do not invent evidence or omit required assets.
- Run the helper's `verify` against this evidence and the saved receipt. A missing adapter, inaccessible target, incomplete response body or missing asset is `NOT VERIFIED`/`FAIL`, never a PASS.

Disk hashes, DevTools folder grants, purple override indicators, CSSOM serialization, a later `fetch`, host metadata alone, or successful UI behavior cannot substitute for these loaded bytes. `ASSETS_VERIFIED_NOT_DEPLOY_PARITY` proves only the captured client asset set for the saved scope; it is not proof of Dataverse deployment or uncaptured forms/locales.
