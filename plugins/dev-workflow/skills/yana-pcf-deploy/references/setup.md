# Shared PCF Setup

Read on first use, missing configuration or a setup failure. Both PCF skills use this
contract. A normal run reads saved preferences and verifies its live source/target;
it does not repeat tool installation, identity questions or folder grants.

## Resolve before asking

1. Read applicable `AGENTS.md` and `AGENTS.local.md`. Reuse existing personal variant,
   org/profile/Overrides paths even when written as prose. An absent managed block
   or helper mapping does not mean Chrome's folder grant is absent.
2. Resolve this skill's active installed directory and an available native Python
   3.10+ executable. Do not hardcode the author's home, `.ai` checkout or plugin cache
   version. Microsoft Store Python can redirect writes away from Chrome; do not use it.
3. Run `status` for the requested scope. Reuse a `CONFIGURED` receipt. It records setup,
   not authorization, current login, Overrides grant, active target or loaded assets.
4. If preferences are missing, infer from the explicit request/existing local guidance.
   Ask only what cannot be established. Ask for personal identity only for a Personal
   deployment, never an RC or override request. Personal variant is the user's chosen
   name, not `Long`, Windows login or a shared identity such as `RC`.
5. For missing prerequisites, guide only the relevant installation or login. The user
   completes sign-in and browser grants. Do not install tools or configure MCP silently.
6. Preview the supplied preferences, then persist with `init --apply` within the user's
   setup request. Protect unrelated local instructions. No repeated approval ritual is
   needed for a value already supplied or confirmed.

## Commands

Resolve `$python`, `$deploySkill`, `$repo` and the chosen paths from this machine.
All are absolute paths. `init` without `--apply` previews without writes or probes.

```powershell
& $python "$deploySkill/scripts/pcf_setup.py" status --repo $repo --scope deploy
& $python "$deploySkill/scripts/pcf_setup.py" init --repo $repo --scope deploy --personal-variant $variant --deploy-environment-url $orgUrl
& $python "$deploySkill/scripts/pcf_setup.py" init --repo $repo --scope deploy --personal-variant $variant --deploy-environment-url $orgUrl --apply
& $python "$deploySkill/scripts/pcf_setup.py" status --repo $repo --scope override
& $python "$deploySkill/scripts/pcf_setup.py" init --repo $repo --scope override --browser-profile $profile --overrides-directory $overrides --apply
```

Deploy initialization resolves Git, native Python, Node 18+, npm, dotnet, PAC, Azure CLI
and Windows PowerShell. Verify project-specific versions and PAC/Azure access to the
chosen non-production org during first setup. Override resolves Git, native Python,
Node 22+ and npm, then the agent checks actual browser capabilities separately. No PAC
or deployment authentication is required for browser-only debugging. A newly created
snapshot may still need dependencies installed according to the lockfile; this is
build preparation, not a reason to rerun personal setup.

`status` only reads the receipt/config and checks cached executable paths. Preference
updates via `init --apply` reuse valid cached runtime paths instead of probing again.
When a runtime fails or a package update changes requirements, repair that scope and
use `init --apply --recheck-tools` to refresh its receipt. A new env or control needs
its own observed mapping, not full setup.

## Storage and migration

Preferences live in one managed section of ignored `AGENTS.local.md`:

````markdown
<!-- yana-pcf-config:start -->
```pcf-config
{
  "personal_variant": "Alex",
  "deploy_environment_url": "https://yanaintegrationdevqa.crm5.dynamics.com",
  "default_control": "YanaGrid"
}
```
<!-- yana-pcf-config:end -->
````

Init supplies DevQA and YanaGrid defaults when absent; explicit input and existing
saved preferences win. Read and migrate known legacy prose before using defaults.
Optional `default_control` accepts YanaGrid or YanaQuickView. Other fields are absolute
`browser_profile`, absolute `overrides_directory`, and
`release_sources` mapping a work branch to its user-confirmed `X.Y.Z` release source.
Only save a lineage mapping after evidence/confirmation; a common ancestor is not proof.
`--release-source WORK_BRANCH X.Y.Z` adds a mapping while preserving other entries.
Deployment preferences use `--scope deploy`; browser paths use `--scope override`.
Cross-scope CLI preference updates are rejected before writing.
Explicit task inputs override these defaults. Free-form existing instructions remain
intact; if they conflict with the managed values, resolve the conflict before use.

The helper refuses tracked or non-ignored `AGENTS.local.md`. If needed, add that exact
name to this checkout's Git exclude after resolving its actual Git directory; do not
change shared `.gitignore`. Do not commit, copy to snapshots or distribute this file.

Receipts live under `%LOCALAPPDATA%/YanaPcfDebug/setup/<repo-key>/setup.json`;
`--state-root` overrides this for isolated tests. Override mappings, profile and
receipts remain outside plugin/source. Existing Grid profiles and schema-2 mappings
must remain usable during migration. Configuration contains no credentials; PAC,
Azure and browser retain their own authentication stores.

## Cross-tool boundary

The plugin includes both skills; standalone override installations also need the deploy
skill's setup helper. Use the actual active provider, not a guessed cache path. If the
dependency is missing, report it before changing state.

Claude Code and Codex use the same configuration/scripts, with their own available
browser adapter. Inspect actual tools. Never assume installing skills installs a
browser server or grants DevTools control. The override skill's browser reference owns
capability detection and manual setup handoffs. Missing loaded-byte evidence is NOT
VERIFIED, even if configuration and copying succeeded.
