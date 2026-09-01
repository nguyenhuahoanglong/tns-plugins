# Autonomy Preflight

The plan must execute with zero user interaction. Preflight proves that before approval by probing real
prerequisites — files, commands, authentication, endpoints, dependency state — instead of assuming them.

**Safety property: a closed set of probe kinds with typed arguments and keyed auth commands, never
free-form shell.** A `## Preflight` section is agent-authored text; a runner that executed strings from it
would be remote code execution via markdown. `preflight.py` therefore accepts only the kinds below, and
`auth` targets are keys into a hardcoded table — the plan can never supply a command line.

## Probe kinds

| Kind | Target | What it proves |
|---|---|---|
| `path` | repo-relative or absolute path | the file or directory exists. Derived automatically from every task's `Files:`; also declarable. Pure read. |
| `command` | bare command name | the executable resolves on PATH. Reports the resolved absolute path; never executes it. |
| `command-version` | bare command name | the executable runs, using one allowlisted argument (`--version`, `-v`, `version`) and nothing else. |
| `auth` | a key, never a command | a non-interactive credential check succeeds. Keys: `az-account`, `pac-list`, `pac-org`, `ado-pat`, `nuget-sources`, `git-remote`. |
| `env` | variable name | the variable is set. Never its value, never its length. |
| `url` | http or https URL | the endpoint is reachable: DNS, TCP, TLS, one unauthenticated GET, no headers or body. `401`/`403` is `ready` — the service is up and only auth is missing, which is the `auth` probe's job. Never POST. |
| `node-deps` | `package.json` path | every `dependencies` and `devDependencies` entry exists under `node_modules`. This is the `npm ci` detector. |
| `dotnet-restore` | `.csproj` path | `obj/project.assets.json` exists and is no older than the project file. |
| `manual` | free text | nothing. Never executed; always `unverifiable`, and the main agent must attest. Covers MCP-driven work no script can probe. |

Preflight never runs a build or a restore — both write `obj/`, `bin/`, or `node_modules` and would break
the read-only guarantee that host plan mode depends on. The plan names the build command; preflight proves
the executable resolves and the manifest, lock, and restore state are present.

Prefer `auth` over `env` for credentials. `AZURE_DEVOPS_EXT_PAT` being set proves nothing about expiry;
`ado-pat` actually calls the API read-only, so an expired PAT becomes a real block instead of a surprise
mid-run.

## Read-only and secret-safe

- Every probe runs with stdin closed, never through a shell, with a per-probe timeout: 20 s default, 45 s
  for `auth`, 10 s for `url`.
- Resolve executables with `shutil.which` first, then invoke the **resolved absolute path**. On Windows
  `az`, `pac`, `npm`, and `ado` are `.CMD` shims: invoking the bare name raises `WinError 2` and reads as
  "not installed" even though the tool works.
- Redact before printing: bearer tokens, JWT-shaped strings, `access_token` values, and the value of any
  environment variable whose name contains `PAT`, `TOKEN`, `SECRET`, `KEY`, or `PASSWORD`. Captured output
  is capped per probe.
- The runner never writes the plan. It prints results; the main agent transcribes them. That preserves both
  the plan-mode single-file constraint and single-writer ownership of the plan.

## States and gates

- **`ready`** — executed and matched.
- **`blocked`** — executed and failed, or timed out. A timeout on `auth` is the interactive-prompt
  signature (`az login`, device code), so it is a block, not an unknown. A blocked probe is a legitimate
  recorded result in a contract-valid plan, but it cannot be approved: fix it in the interactive window with
  the user present and re-run, or descope the tasks named in `Blocks`. Never improvise credentials, never
  switch authentication mode.
- **`unverifiable`** — the kind cannot prove it (`manual`, or an unreadable resource). Requires a
  `Fallback:` clause **on the same result line**, naming exactly what happens if it turns out blocked at
  runtime, which is always: the task stops and is marked `blocked`; never prompt, never improvise. The count is surfaced at approval so
  the user consents to the residual risk.

Aggregate to `Autonomy`: `verified-blocked` if any probe is blocked; otherwise
`unverifiable-with-fallback` if any is unverifiable; otherwise `verified-ready`.

## When to run it

Twice, with no freshness field and no timestamp arithmetic. Once during Harden, where it gates approval,
and once as the first Execute step after promotion, where it gates fan-out. Two cheap runs cover expired
tokens and a changed working tree better than any TTL the agent has to reason about.
