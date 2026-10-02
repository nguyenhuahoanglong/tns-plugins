# Yana PCF Debug Override

## Purpose

Build YanaGrid locally by default, or YanaQuickView when explicitly selected, and override the complete client resource set through Chrome Local Overrides to test logic and UI on an existing Dataverse form. This is local debugging only; it does not import a solution or change server web resources.

The active `dev-workflow` plugin bundles this skill beside `yana-pcf-deploy`, whose setup helper owns shared first-run preferences. Claude Code and Codex use the same source helper and configuration, but each runtime must detect its own currently available browser tools. First-run may create a dedicated non-default Chrome user-data directory; the skill does not install an MCP, modify the normal profile, copy cookies, sign in or grant DevTools access.

## Pain Points

Copying only `bundle.js` can combine new JavaScript with old CSS, strings, images or fonts. The browser can also continue executing an older script after the override file changes, and independent resources may use different cache tokens. Schema-2 maps keyed only by origin can accidentally cross repos, profiles, controls or deployed variants.

The helper inventories the selected control's generated `ControlManifest.xml` and output files, maps exact observed requests, applies all required client files in one recoverable transaction, and checks browser runtime evidence. JavaScript-injected styles travel with the bundle; manifest CSS remains a separate resource. Mapping keys now include checkout, browser profile, origin, control and observed deployed identity. An old origin-only Grid map needs explicit one-time migration and is never reused for QuickView.

The host owns component metadata, properties, dataset bindings, platform libraries and often RESX values. Default `client-assets` scope verifies complete loaded client assets and reports those host limits; only dependent behavior remains unverified. Optional `client-parity` scope blocks on host differences or missing evidence. Neither mode deploys anything.

## Entry points

- [SKILL.md](SKILL.md): first-run setup, source freshness, build, apply and verification workflow.
- [Resource contract](references/resource-contract.md): selected-control inventory, map scope, host data, transaction and verdict semantics.
- [Browser adapter](references/browser-adapter.md): Claude/Codex capability detection, manual fallback and required loaded-byte evidence.
- `scripts/yana_grid_debug_override.py`: inventory, plan, setup/run, verify, status.
- `scripts/resource_set.py`: deterministic inventory, contract checks, transaction and verification.
- `scripts/capture_runtime.mjs`: read-only capture from an existing loopback Chrome CDP target.
- `evals/evals.json`: behavioral coverage, including QuickView, source freshness and cross-runtime limits.

Shared preferences live in the one managed `AGENTS.local.md` block created by `yana-pcf-deploy/scripts/pcf_setup.py`; operational maps and receipts remain under `%LOCALAPPDATA%\YanaPcfDebug\YanaGrid`. The helper neither logs in nor automatically reloads a tab. Chrome's folder grant and helper mapping remain separate state.

Prerequisites: Python 3.10+, Node 22+ for capture, the repo's locked PCF dependencies, and Chrome DevTools Local Overrides enabled on the test tab. If root `package-lock.json` exists and `pcf-scripts` is missing, run `npm ci` from repo root once as part of the authorized build; preserve the lockfile and do not use `npm install`. For a new machine, use the dedicated persistent non-default Chrome user-data directory and loopback debugging endpoint described in [Browser adapter](references/browser-adapter.md); never copy the normal Chrome profile or cookies. The selected control build defaults to production mode, cleans only its checked output directory, and guards selected source identity files. Clean checkouts with no local commits may fetch and fast-forward their configured upstream; local changes and ahead commits are built as-is without Git mutation. The skill never commits or pushes.

## Changelog

### 2026-10-02 — Shared setup, QuickView and source-scoped mappings

Active intent revision: 3. Reused the sibling PCF setup helper for one-time configuration; kept Grid as the default and added explicit QuickView workspace/build support. Mappings now separate checkout, profile, origin, control and deployed identity. Added confirmed Grid-only migration for old origin-keyed maps, clean-source fast-forward behavior, local-worktree preservation, and strict dry-run boundaries. Added runtime-specific Claude/Codex capability detection, a Chrome 136+ non-default persistent user-data setup, Chrome 144+ AutoConnect gating, and lockfile-based `npm ci` for missing PCF dependencies. Missing runtime byte proof remains `NOT VERIFIED`. No live browser session or cross-runtime parity run was performed for this revision.

Validation: 55 focused Python tests ran: 54 passed and one case-collision test skipped because this filesystem aliases case-only paths. Node syntax, `verify_output.py`, and the skill-creator intent/guardrail checks passed. The original intent remains reconstructed/unconfirmed; PyYAML and runtime grading were unavailable. Claude/Codex behavioral comparison and live browser evidence were `NOT RUN`.

### 2026-09-29 — Complete resource and runtime verification

Active intent revision at that time: 2, user clarified logic/UI testing as the primary goal. Complete asset verification stays mandatory; strict host parity is optional. Original no-deployment purpose and permission boundaries are preserved; canonical source was extended rather than creating a competing override skill. Structure, intent, transaction/runtime regressions and observed browser failure cases are checked separately.

- Replaced bundle-only copying with generated-output inventory and exact per-resource mappings.
- Added CSS/assets, framework RESX checks, manifest compatibility, staging and rollback.
- Added executed-JS and loaded-response verification; stale tabs, CSSOM and later fetches cannot pass as fresh loaded assets.
- Added read-only CDP capture, explicit partial-debug status, dry-run and schema-1 migration guards.
- Preserved existing profile grants and user drafts; removed automatic browser launch/reload assumptions.
- Live rerun found Microsoft Store Python redirecting LocalAppData writes away from Chrome. Added a native-runtime guard before CLI work and direct apply; use an existing non-Store Python executable. This preserves revision 1's browser-visible resource requirement.
- Live rerun also found Chrome `longurls` CSS mappings, different tokens on stale/new tabs, inactive manually opened DevTools frontends, and lazy grid loading beyond a short capture window. Documented native DevTools and allowed bounded captures up to 180 seconds.
- Validation at the time: Python transaction/CLI tests, fake-CDP collector tests, Node syntax, intent/structure checks, a real production build, live PTQA asset/behavior checks, and bounded old/no-skill/candidate workflow comparisons. DateTime duration-to-end-time updates survived blur; DateOnly display was checked but editing remained blocked by the supplied form's read-only field. Full client/host parity remains unverified when the host contract or strings differ; no deployment was performed.

### 2026-07-10 — Initial debug override workflow

- Added bundle-only Chrome Local Overrides setup for YanaGrid.
- Used direct PCF build and source hash guards to avoid prebuild identity rewrites.
