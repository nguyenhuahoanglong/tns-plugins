---
name: daily-report
description: Create a portable daily report from configured Azure DevOps tasks, workbook, and Dataverse timesheet. Use for daily report, standup, or timesheet updates.
---

# Daily Report

Use this skill for a daily standup/report or timesheet update. It is self-contained: invoke Python from this installed skill directory; do not call profile functions, external helper scripts, or a machine-specific path.

## Normal flow

Run one command for an autonomous report:

```bash
python scripts/daily_report.py run [--add "- extra work"] [--backup]
```

`run` initializes missing local state idempotently, gathers configured active Azure DevOps tasks, refreshes today's workbook row, resolves the timesheet identity and period, then verifies results. It writes the current timesheet only after a successful dry-run. A re-run refreshes today's workbook/timesheet record instead of creating a duplicate.

`--backup` is opt-in. Default: no backup. Workbook Git commit behavior remains restricted to the configured workbook; unrelated worktree changes stay untouched.

End a successful user-facing response with only the copy-ready report in a fenced `text` block:

```text
Yesterday
- ...
Today
- ...
```

## First run and diagnostics

Local state is OS-native and private to current user. Setup creates missing config, workbook, queue, isolated environment, and dependencies without overwriting existing artifacts.

```bash
python scripts/daily_report.py setup
python scripts/daily_report.py doctor
```

Before a report can access services, user fills required organization and Azure DevOps values in local config. `doctor` is read-only: report its precise failed check and recovery action. Do not invent credentials or copy another user's configuration.

To migrate existing local data, source paths must be explicit:

```bash
python scripts/daily_report.py setup --import-config "PATH" --import-workbook "PATH"
python scripts/daily_report.py setup --import-config "PATH" --replace
```

Use `--replace` only when user explicitly asks to replace destination state.

## Review-only and timesheet outcomes

When user asks to inspect first, dry-run, or not commit, use:

```bash
python scripts/daily_report.py run --review-only
```

This returns gathered items/report preview without workbook or timesheet mutation. Do not silently convert review-only into a write.

Normal `run` performs timesheet preflight, dry-run, then explicit writer commit. If no period exists or more than one period matches, enqueue today's record locally and report that outcome; do not block report output solely for this condition. Retry pending records separately:

```bash
python scripts/daily_report.py pending
```

If secure token storage or authentication fails, stop before live write, surface stable error code/recovery guidance, and never fall back to plaintext tokens. Do not claim success for an unverified external write.

## Verify Output

`run` invokes `scripts/verify_output.py` internally before reporting success. Do not bypass a failed verification or manually claim an external write succeeded.

## Guardrails

- Read Azure DevOps only; never create or edit work items.
- Do not invent tasks, identity, business lookups, period, or credentials.
- No fixed user, organization, project, workbook path, cloud-drive path, or operating-system assumption.
- Do not call internal scripts as user workflow entrypoints; `daily_report.py` is public CLI.
- Do not expose tokens, auth-cache contents, or confidential config values.

## Resources

- `README.md` — portable behavior and changelog.
- `references/config.md` — local configuration and state overrides.
- `references/auth.md` — secure authentication recovery.
- `references/timesheet-schema.md` — identity/lookup resolution.
