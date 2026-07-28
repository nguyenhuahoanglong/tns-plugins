# Daily Report

## Purpose

Portable, self-contained daily reporting skill. It gathers configured active Azure DevOps tasks, updates a local workbook, creates or updates today's Dataverse timesheet line, and returns a copy-ready `Yesterday` / `Today` report.

## Pain Points

- Avoids dependence on a developer's shell profile, global script, or cloud-drive folder.
- Keeps daily workbook/timesheet work idempotent and recoverable when period resolution is unavailable.
- Gives a review-only escape hatch before any local or live mutation.

## Public command

Run from installed skill root:

```bash
python scripts/daily_report.py run
```

Useful options:

```bash
python scripts/daily_report.py run --add "- planning"
python scripts/daily_report.py run --review-only
python scripts/daily_report.py run --backup
python scripts/daily_report.py doctor
python scripts/daily_report.py pending
```

`run` bootstraps missing state without overwriting existing artifacts. It gathers configured tasks, makes an idempotent workbook update, preflights authentication, dry-runs the timesheet, then commits the timesheet only when resolution succeeds. `--review-only` performs no workbook or timesheet mutation. `--backup` is optional and disabled by default.

On a missing or ambiguous timesheet period, the current day is queued locally and report generation continues. Run `pending` to retry queued records. Authentication or secure-store failure stops the live write; no plaintext-token fallback exists.

For explicit migration only:

```bash
python scripts/daily_report.py setup --import-config "PATH" --import-workbook "PATH"
python scripts/daily_report.py setup --import-workbook "PATH" --replace
```

Do not use external global scripts, shell-profile functions, hardcoded cloud folders, or another developer's config. See `SKILL.md` for workflow guardrails and `references/` for configuration/auth/schema details.

## Changelog

### 2026-07-28 — Working gather path on Windows

- Resolved console shims through `shutil.which`, so `az` (installed as `az.CMD`) no
  longer reports as missing and every CLI call runs; this blocked all gathering and
  made `doctor` report Azure CLI unavailable.
- Replaced `az boards query` with `az devops invoke` (`wiql` for ids, `workitemsbatch`
  for fields): the former exits 0 with no output on some Azure CLI builds.
- Stopped sending `--team` on the query, which rejects it, while keeping it on the team
  iteration lookup, which requires it.
- Added `--timeframe current` when resolving the sprint; an unfiltered list returns
  every iteration ever defined and selected a years-old sprint.
- Added optional per-team `organization`, so projects in different Azure DevOps
  organizations are gathered in one run.
- `doctor` now runs before configuration exists, which is the first-run case.

### 2026-07-27 — Portable dev-workflow release

- Moved runtime contract to skill-local Python CLI.
- Added idempotent setup, explicit migration, diagnostics, portable state, and optional backup.
- Added secure cross-platform token persistence with no plaintext fallback.
- Added identity/period resolution, pending queue handling, and copy-ready report contract.

### 2026-07-01 — Pending timesheet queue

- Added retryable local queue for unavailable timesheet periods.

### 2026-06-18 — Workbook verification

- Added isolated workbook commit and copy-ready report output.
