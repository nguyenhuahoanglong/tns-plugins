# Resource mapping and verification contract

Read when collecting mappings, interpreting a blocker, or producing runtime evidence.

## Sources of truth

Use one fresh `out/controls/<selected-control>` build: `out/controls/YanaGrid` by default, or `out/controls/YanaQuickView` when selected. Each control has its own workspace, manifest identity and emitted files. Generated `ControlManifest.xml` describes packaged resources; remaining emitted runtime files and local CSS dependencies also matter. Separate JavaScript, CSS, images/fonts, localization and optional debug maps. Inline CSS bundled by webpack travels with JavaScript. Manifest-declared CSS does not. Never combine Grid and QuickView output.

`ControlManifest.xml` is inspected for host compatibility, not blindly copied as a request override. PCF host metadata controls properties, datasets, features, libraries and resource loading. A changed host contract or asset membership/order may need a deployment even if every local file exists.

The same source may produce different development/production output. Build the selected control with the intended mode, record source branch/SHA and whether dirty changes or local commits were included, and never describe development output as a verified Release artifact. Dirty/untracked/ahead work is built as-is without Git mutation. A clean branch with no local commits may fetch its configured upstream and fast-forward only; divergence, remote rewind or missing upstream blocks a latest-source claim. `--artifact-dir` is explicit reuse, not freshness certification. Source hash guards detect identity stamping; they do not automatically revert a changed source file.

## Map exact browser requests

Use DevTools Network/Overrides for the selected org/control variant. Reuse existing grants and saved files. For missing files, save the actual request with **Override content**. Keep DevTools open. Do not create URL-to-path encodings yourself: percent escapes, query strings and Chrome `longurls` storage make inferred paths unreliable.

Use the inspected tab's native DevTools window. A manually navigated `devtools://...inspector.html` page may show a checked Overrides setting while its persistence manager is inactive. Where the connected Chrome protocol exposes `Target.openDevTools`, use that supported operation for the owned page, then verify activity and loaded bytes. A checkbox alone is not proof that interception works.

Example shape only; replace every URL/path/XML/string with observed evidence:

```json
{
  "schema_version": 2,
  "origin": "https://org.crm5.dynamics.com",
  "resources": [
    {
      "artifact": "bundle.js",
      "url": "https://org.crm5.dynamics.com/%7bJS_TOKEN%7d/webresources/cc_Technosoft.DMS.XRM.CustomControl.Grid.YanaGrid/bundle.js",
      "override_file": "C:/.../overrides/<actual DevTools file>"
    },
    {
      "artifact": "Styles/DatasetStyles.css",
      "url": "https://org.crm5.dynamics.com/%7bCSS_TOKEN%7d/webresources/cc_Technosoft.DMS.XRM.CustomControl.Grid.YanaGrid/Styles/DatasetStyles.css",
      "override_file": "C:/.../overrides/<actual DevTools CSS file>"
    }
  ],
  "host_manifest": {
    "xml": "<manifest>...actual captured deployed manifest...</manifest>",
    "source_url": "https://org.crm5.dynamics.com/<actual observed source>"
  },
  "host_resources": {
    "localized/YanaGrid.1033.resx": {
      "locale": 1033,
      "values": {"EveryLocalKey": "Actual framework-returned text"},
      "source": "context.resources.getString",
      "observed_at": "2026-09-29T04:00:00Z"
    }
  }
}
```

URLs must be HTTPS, same origin and the selected control directory, with the exact artifact suffix. A selected deployed identity may be the build namespace or the same namespace with one observed variant suffix. All entries in one map must identify that same control directory. Destination files must already exist inside the configured Overrides root, without symlink/traversal/collision. Each artifact, URL and destination is unique. Different cache tokens are valid when independently observed. Missing assets and source/destination changes between plan and apply block all writes. Unrelated override files remain untouched.

The helper keeps mappings separate by canonical checkout, configured browser profile, environment origin, control and deployed identity. A `YanaGrid` map never selects a `YanaQuickView` bundle; another checkout, profile or variant also requires its own observed map. Old schema-2 maps keyed only by origin lack these boundaries. Rebind one only after reviewing the origin, deployed identity and existing override paths, and explicitly pass `--migrate-legacy-grid-map`. Migration copies the map into the selected Grid scope and preserves the original entry. It is never a QuickView migration, and once claimed it cannot bind to another scope.

The helper validates mapping shape and containment, but cannot prove that a human-supplied URL/file pair came from Chrome. Runtime verification catches inactive or incorrectly mapped destinations. Do not label plan/apply success as browser success.

## Host resources and localization

Some hosts expose actual `.resx` requests. Only map a raw RESX file when that exact request is observed and the file is consumed by the active control. Otherwise PCF supplies strings through `context.resources.getString`; capture returned values for all local keys and the active LCID. Do not treat a RESX filename or the browser language alone as proof of the framework's active locale.

Use the control's already available context through a bounded read-only browser probe. If no context/manifest source is accessible, report unverified. Do not guess private endpoints or overwrite a translation service to force matching values. Returning the key itself may indicate fallback: compare with actual local expected text.

Locale siblings are separate resources. Verify each supported locale required by the test scope; if any required locale cannot be observed, report that gap. Do not silently delete untranslated assets from the inventory to get a PASS. Equal duplicate RESX values may be deduplicated; conflicting duplicate values are ambiguous and blocked.

Default `client-assets` scope retains host differences as warnings. Assess their relevance to each E2E case: unchanged DateTime logic can be tested despite unrelated label differences; a new translated label cannot pass while the host returns old text. Host resource membership changes can prevent the new asset from loading, which still fails mandatory runtime verification. Do not deploy all resources solely to remove unrelated host warnings.

Strict `client-parity` scope blocks known host/RESX differences. Its legacy `--allow-host-unverified` flag permits only unknown host evidence for partial debugging, never known mismatches. Neither scope permits missing JS/CSS/assets. Changed host behavior necessary for a test requires a separately authorized sandbox deployment or an explicit unverified case.

## Apply transaction

`plan` freezes build/destination hashes. `setup` and `run` create a fresh plan, validate all mandatory artifacts, stage all new bytes, replace exact mapped files, verify hashes and roll back the prior bytes if a replacement fails. An apply receipt records plan, hashes and `applied_at`.

This is a recoverable filesystem transaction, not an atomic browser snapshot. Do not reload while it is applying. Start runtime capture after apply completes. If rollback itself fails, keep recovery files and report their paths; do not continue to verification or hide the failure.

## Runtime evidence

Collector attaches to an existing loopback CDP target; it does not launch Chrome, sign in, reload tabs or modify Dataverse. Node 22+ is required. Start it before a reload of a task-owned tab, wait for `CAPTURING`, then drive the authorized browser. Use a separate test tab for an existing unsaved form.

Choose a capture window that includes form startup and lazy grid mounting (up to 180 seconds; 120 seconds is useful for slow CRM forms). Run long captures asynchronously. If a resource is missing, compare the page's resource timings with the capture window before blaming cache or override content.

- JavaScript: `Debugger.getScriptSource` for the active exact URL. Hash executed source, not a new fetch or disk file.
- CSS: `Network.getResponseBody` of the actual `Stylesheet` request, with request ID, capture time and exact URL. CSSOM (`CSS.getStyleSheetText`) may normalize or mutate text; it cannot prove raw response identity.
- Images/fonts/other client files: actual loaded response bodies. A later fetch/XHR is not proof that the view used the resource. Exercise lazy-loaded paths; missing observations stay missing.
- Host strings: for strict parity or localization tests, recapture the same locale/keys from framework context after apply. Default asset verification does not certify strings. Do not reuse pre-apply values as fresh runtime evidence.

The collector rejects cross-origin/non-loopback targets. It collects resource URLs/hashes and request provenance, not headers, tokens or storage. It returns a nonzero exit when expected URLs are missing or capture fails. Even exit 0 is only evidence capture; Python `verify` decides parity.

Minimal evidence shape:

```json
{
  "schema_version": 2,
  "origin": "https://org.crm5.dynamics.com",
  "plan_id": "from receipt",
  "resources": [
    {
      "url": "exact planned URL",
      "sha256": "observed SHA-256",
      "method": "Network.getResponseBody",
      "request_id": "actual CDP request ID",
      "resource_type": "Stylesheet",
      "loaded_request": true,
      "captured_at": "2026-09-29T04:05:00Z",
      "captured_after_apply": true
    }
  ],
  "host_resources": [
    {
      "artifact": "localized/YanaGrid.1033.resx",
      "locale": 1033,
      "values": {"EveryLocalKey": "Actual framework-returned text"},
      "source": "context.resources.getString",
      "observed_at": "2026-09-29T04:05:00Z",
      "captured_after_apply": true
    }
  ]
}
```

Pass fresh host data to the collector using `--host-evidence <file.json>`, containing the same `origin` and the `host_resources` array. The collector merges it without inventing values/timestamps; verifier checks source, locale, time and values.

## Interpret results

| Result | Meaning / next step |
| --- | --- |
| `READY` | Plan is eligible to apply, not yet applied. |
| `BLOCKED` | Plan records resource/host findings. Apply blocks missing/invalid client assets in every scope; host findings block strict parity but become warnings in client-assets scope. No partial write. |
| `ASSETS_APPLIED` | Local override bytes copied; runtime and E2E still pending. |
| `ASSETS_APPLIED_NOT_DEPLOY_PARITY` | Client-assets scope applied, or strict scope with explicit unknown-host allowance. Runtime/E2E pending. |
| `FAIL` | Runtime resource missing, stale, mismatched or unsupported evidence. |
| `ASSETS_VERIFIED_NOT_DEPLOY_PARITY` | Browser assets verified; host equivalence is not certified. `verify` exits 0 for a saved client-assets receipt, nonzero for strict/legacy receipts. |
| `CLIENT_RESOURCES_VERIFIED` | Resource/host checks pass for captured scope. Still run behavioral E2E. |

Do not claim deployment correctness, other locales/forms, solution layering, import/publish, server behavior or security from this verdict. Changed host configuration needs an explicitly targeted sandbox deployment through the deployment workflow.
