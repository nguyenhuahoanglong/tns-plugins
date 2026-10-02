# Planning Readiness and Recovery

Read during planning, before asking for execution approval. Goal: remove predictable human interruptions,
not manufacture a zero-interaction guarantee. Probe only prerequisites relevant to the approved outcome.

## Human dependencies to resolve now

| Concern | Evidence/decision needed before dependent execution |
|---|---|
| Acceptance and UI | Expected happy/error states; relevant screenshots/design references; responsive/accessibility expectations |
| Architecture | Consequential interface/data-flow choices settled; required design-backbone gates satisfied before detail work |
| Test ownership | Existing unit/E2E owners and test locations; meaningful cases derived from approved requirements |
| Target | Exact environment/tenant/app and expected build identity; allowed local/nonproduction scope |
| Authentication | Actual execution channel reaches a protected read-only page/API as the intended account/role |
| Browser/runner | Tool available to the eventual QA worker; base URL/start command; session transfer supported without secret leakage |
| Data and writes | Safe fixtures, allowed create/update/delete operations, cleanup, and any external-write limits |
| Review | Selected route, real escalation consent, and any session confirmation handled or disclosed |
| Recovery | Permitted restarts, noninteractive setup/retry, fallback route, and actions that still require the user |

Infer known facts from sources and live evidence. Ask only missing consequential facts, grouped while the
user is planning. Do not send a standard questionnaire for tasks that need no E2E/auth/UI decisions.

Use an existing authorized login where possible. When user login/MFA is required, arrange it before
implementation approval, then check access through the same channel execution will use. Host plan-mode
restrictions still apply: do not launch a prohibited state-changing tool. Have the user perform setup or
use an explicitly authorized preparation stage. Planning auth readiness is distinct from implementation
approval. Never place credentials, cookies, tokens, or storage-state contents in a plan or report.

## Separate human prerequisites from executable setup

Missing login, undefined expected behavior, or missing test-data authority cannot be fixed by a worker's
guess. Resolve now or explicitly stage the dependent task as blocked. A planned local dependency restore,
starting the test server, or creating an approved fixture may run after approval without another question.
Record commands, boundaries, and verification; do not imply setup already ran.

If only a deployed UI exists today, check authentication/permissions now and verify the changed build
later. Passing access preflight is not passing feature E2E. If credentials expire during execution, use
only an authorized noninteractive refresh; otherwise pause dependent checks, continue independent work,
and request the minimum human action. Never silently substitute a different account or target.

## Reuse the typed probe helper when useful

`python <skill>/scripts/preflight.py <plan-path> --repo-root <project-root>` reads the structured `## Preflight`
table. It uses a closed set of typed probes; it never executes free-form plan-supplied commands.
Keep other readiness tables under a separate heading so this parser does not treat them as probes.

| Kind | Actual proof and limit |
|---|---|
| path | Path or parent exists; not proof a supposedly existing source file is correct |
| command / command-version | Command resolves / approved version argument runs; not complete task capability |
| auth | Keyed check: az-account, pac-list, pac-org, ado-pat, nuget-sources, git-remote; account/feed listings alone do not prove resource access |
| env | Variable is set; not validity/expiry |
| url | DNS/TCP/TLS and GET reachability; 401/403 is reachable, never authenticated readiness |
| node-deps | Declared dependency directories exist; not exact lockfile/version/build correctness |
| dotnet-restore | Assets file exists and is recent enough; not a successful build |
| manual | Script cannot check it; always unverifiable, even if separate tool evidence exists |

Prefer direct protected-resource evidence over inferring access from these narrow checks. Record a
successful MCP/browser read separately; do not label an unrun scripted check ready. No automatic build,
restore, install, login, or test-data mutation occurs in this helper.

Its output remains secret-redacted, capped, noninteractive, and timeout-bounded. The caller records
results; the helper does not write the plan. Use resolved executable paths and existing approved auth.

## States, decisions, and freshness

For typed probes: `ready`, `blocked`, `unverifiable`; aggregate remains `verified-ready`,
`verified-blocked`, or `unverifiable-with-fallback`. Copy results accurately. Every unverifiable result
needs a same-line `Fallback:` describing safe recovery or a dependent-task stop.

These labels describe probe coverage, not blanket approval. A blocked probe stays blocked even when
approved setup will fix it. Stage setup first and re-probe before dependent dispatch. For a manual probe,
link direct evidence and explain its narrower coverage; do not change the helper's result.

Recheck volatile prerequisites at execution start or just before their use, and after environment
changes. Reuse stable evidence. Avoid fixed timestamp rituals and full repeated preflight on every task.
For an explicitly approved staged run, show runnable tasks and outstanding blocked ACs separately.

`verify_output.py` checks the structured record when present. FAIL means inconsistent/malformed record;
BLOCK means a recorded blocked probe. Neither is permission to alter scope, credentials, or acceptance.
