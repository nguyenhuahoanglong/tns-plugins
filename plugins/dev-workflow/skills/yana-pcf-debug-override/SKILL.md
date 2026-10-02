---
name: yana-pcf-debug-override
description: Use for local YanaGrid or YanaQuickView logic/UI debugging through Chrome Local Overrides. Build selected control from current checkout, map complete client assets, and verify loaded bytes.
---

# Yana PCF Debug Override

Use for local YanaGrid bundle overrides; YanaGrid is the default. Use `--control YanaQuickView` for QuickView. Read [resource-contract.md](references/resource-contract.md) for mapping and evidence rules, and [browser-adapter.md](references/browser-adapter.md) before browser work.

## Outcome and boundary

Override the complete generated client resource set from one build, then test the requested behavior on the existing form. A copied file or passing UI interaction alone is not a runtime-resource PASS. This workflow changes only local build output, helper state and the configured DevTools Overrides files. It does not import a solution or mutate server web resources, metadata, form bindings, credentials, or security.

Default `client-assets` scope supports logic and UI tests while keeping host-manifest and RESX differences visible. Mark behavior that depends on those differences unverified. Use `client-parity` only when the requested result requires matching host metadata and localized values. Neither scope simulates solution import, registration, plugins, security or deployment lifecycle.

## Workflow

1. Establish the selected repo, current branch, control, environment origin, behavior and verification scope. For a request to test the user's variant, use the current checkout and its local changes. Read repo instructions, the selected control's workspace instructions and `AGENTS.local.md` before deriving a branch or control identity.
2. Resolve the active `dev-workflow` provider and read its bundled `yana-pcf-deploy/references/setup.md` only on first use, missing setup or setup failure. Check the shared override setup once then. If configured, load its saved values without repeating setup questions or grants. Reuse legacy prose preferences; migrate known values without asking again. For first setup, prefer an already working backend/profile and Overrides folder. If none exists, use the dedicated persistent non-default Chrome user-data directory described in [browser-adapter.md](references/browser-adapter.md); validate the actual executable and reported Chrome profile path. Explain the profile/folder choice; the user signs in and grants the folder. Save the exact paths once. Ask only what cannot be inferred. Do not install a browser adapter or create duplicate personal config.
3. If the working tree contains tracked changes, untracked files or local commits ahead of its upstream, build that checkout as-is and report that local work is included. Do not fetch, merge, stash, reset or otherwise change Git state. If the checkout is clean and has no local commits, fetch its configured upstream and fast-forward only; stop if no upstream, remote rewind, divergence or concurrent checkout change prevents proving latest. Never commit or push. Dry-run never fetches or merges.
4. Select the control from an explicit request, then saved `default_control`, then YanaGrid. After source selection, check the repository lockfile and PCF build dependency. If `pcf-scripts` is missing and the repo uses `package-lock.json`, run `npm ci` from the repo root as the routine prerequisite for this authorized build; it restores locked packages without changing the lockfile and needs no repeated setup approval. Follow the repository's package-manager instructions if a different lockfile applies. Never run `npm install`, update a lockfile or install global tools to bypass a failed restore. Build only the selected control's workspace and `out/controls/<control>` output with direct `pcf-scripts`; use production mode unless source maps are needed. Guard its identity files and record branch, SHA, local-diff state, control and build mode. For `--artifact-dir`, freshness is unverified unless separately evidenced.
5. Inspect that build's generated `ControlManifest.xml` and inventory all required JS, CSS, images, fonts, localization and other runtime assets. Never mix outputs across controls, branches or builds. Host metadata and RESX remain separate from the locally loaded client assets.
6. Inspect the selected control's actual browser requests and existing Overrides grant. Map each exact observed URL to its existing DevTools-saved file; JS and CSS may have independent cache tokens. Never derive URL paths or assume that an absent helper map means the browser grant is missing. Use a separate task-owned tab when the existing form has unsaved changes.
7. Review the whole plan before applying it. Resolve maps by checkout, configured browser profile, origin, selected control and observed deployed identity. Validate every existing destination inside the configured Overrides folder before fetch or build. An old origin-only schema-2 Grid map requires explicit `--migrate-legacy-grid-map`; migration copies it into the selected scope and keeps the old entry. Never reuse that map for QuickView or another scope.
8. Apply the complete eligible client set in one recoverable transaction. Do not partially apply missing, ambiguous, stale, changed or out-of-folder mappings. Keep DevTools Overrides enabled for the test tab; don't reload while the helper is replacing files.
9. Detect the active Claude Code or Codex browser capability using its own live tools. Start `capture_runtime.mjs`, reload only a task-owned test tab, wait for the control and lazy resources, and exercise the relevant UI. Prove executed JS with `Debugger.getScriptSource` and CSS/other assets with actual loaded `Network.getResponseBody` evidence. A disk hash, CSSOM serialization, later fetch, folder grant or successful apply is not loaded-byte proof. If the current adapter cannot produce the required evidence, report `NOT VERIFIED` and offer the manual DevTools/collector path.
10. Run `verify` against the apply receipt and fresh browser evidence. Then verify the requested behavior at the same form, locale and viewport. Report the branch/source mode, control, environment, build identity, applied files, runtime verdict, behavior result and any host-dependent limits. At debug completion, disable task-owned overrides or close only task-owned tabs; preserve shared mappings and user tabs.

## Commands

Resolve `<skill-dir>` and the native Python 3.10+ / Node 22+ runtimes from the active installed provider. Do not hardcode the author's checkout, home directory or plugin-cache version. The shared setup helper is bundled beside this skill; the helper resolves it from the same active provider. Microsoft Store Python can redirect LocalAppData writes away from Chrome; use an available native runtime and do not install one silently. Keep reports outside skill/repository source, normally in `%LOCALAPPDATA%\YanaPcfDebug\YanaGrid`.

```powershell
python <skill-dir>/scripts/yana_grid_debug_override.py --mode inventory --repo-root <repo> --control YanaGrid --report <inventory.json>
python <skill-dir>/scripts/yana_grid_debug_override.py --mode inventory --repo-root <repo> --control YanaQuickView --report <inventory.json>
python <skill-dir>/scripts/yana_grid_debug_override.py --mode plan --repo-root <repo> --control YanaGrid --artifact-dir <out/controls/YanaGrid> --page-url <url> --resource-map <map.json> --report <plan.json>
python <skill-dir>/scripts/yana_grid_debug_override.py --mode setup --repo-root <repo> --control YanaGrid --artifact-dir <out/controls/YanaGrid> --page-url <url> --resource-map <map.json> --report <receipt.json>
node <skill-dir>/scripts/capture_runtime.mjs --receipt <receipt.json> --target <cdp-target-id> --output <evidence.json> --port 9222 --duration-ms 30000
python <skill-dir>/scripts/yana_grid_debug_override.py --mode verify --receipt <receipt.json> --runtime-evidence <evidence.json> --report <verification.json>
```

- `--control` accepts `YanaGrid` or `YanaQuickView`; it defaults to shared `default_control`, then YanaGrid. Build commands use that control's workspace and output.
- `run --repo-root <repo> --page-url <url>` builds the selected control and reuses the uniquely matching repo/profile/origin/control/deployed-identity map. If multiple deployed identities match, pass `--deployed-identity` copied from observed browser requests.
- `--resource-map` supplies a schema-2 map of exact observed URLs and existing DevTools files. Mapping scope includes checkout, browser profile, origin, control and deployed identity.
- `--artifact-dir` reuses an existing complete output and skips Git refresh/build; provenance and freshness remain unverified unless supplied.
- `--dry-run` is read-only: it requires `--artifact-dir`, and does no fetch, merge, build, browser action, output write or report write.
- `--verification-scope client-assets` is the default: all required client mappings and runtime bytes remain mandatory; host findings are warnings unless they affect the tested behavior. `client-parity` also requires host contract/localization parity. Verification honors the receipt's saved scope.
- `--allow-host-unverified` allows only partial asset debugging when host evidence is unknown; it never bypasses known mismatches or missing client assets.
- `status` reads helper state. Existing Chrome grants and helper mappings are separate. Schema-1 bundle-only maps remain untouched.
- If the selected control's PCF build dependency is missing, follow the repo lockfile once as part of authorized build setup (root `package-lock.json` → `npm ci` from repo root). Do not update lockfiles, install global runtimes or silently install a browser MCP.

## Verify Output

```powershell
python <skill-dir>/scripts/verify_output.py <skill-dir>
python -m unittest discover -s <skill-dir>/scripts/tests -v
node --check <skill-dir>/scripts/capture_runtime.mjs
```

No Dataverse import, web-resource update, credential entry or repository identity stamping occurs in this workflow. Missing browser capability or loaded-byte evidence is a reported limit, never a PASS.
