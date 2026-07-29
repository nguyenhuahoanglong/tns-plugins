---
name: daily-report
description: Create a portable daily report from configured Azure DevOps tasks, a local workbook, and Dataverse. Use for daily standups, timesheets, setup, or report recovery.
---

# Daily Report

Use only the installed skill-local CLI. It owns portable runtime state; do not use profile functions, shared scripts, Git, cloud-drive paths, or another user's configuration.

## Commands

```bash
python scripts/daily_report.py setup
python scripts/daily_report.py doctor
python scripts/daily_report.py auth
python scripts/daily_report.py run [--add "Planning"]
python scripts/daily_report.py run --review-only
python scripts/daily_report.py status
python scripts/daily_report.py pending [--sync]
```

Every command supports `--json`; use per-command `--help` for its options. State defaults to `~/.ai/data/daily-report`; `--state-dir` overrides `DAILY_REPORT_HOME`, which overrides the default. Config precedence is explicit CLI path, `DAILY_REPORT_CONFIG`, then runtime config.

## Safe workflow

1. Run `setup` once. It creates only missing config, workbook, queue, and isolated environment. Fill every organization-specific placeholder yourself.
2. Run `doctor` for read-only diagnosis. It never signs in or changes state.
3. Run `auth` for public interactive device sign-in. Normal `run` uses silent authentication before changing the workbook.
4. Run `run`. It gathers tasks, updates and verifies the workbook, previews/writes and verifies the Dataverse line, then syncs older pending records. It always prints the available copy-ready report.

`--review-only` changes nothing. If setup is absent it returns `SETUP_REQUIRED` and writes nothing. Missing or ambiguous periods return `PARTIAL` after a verified workbook update and queue the current day; resolve the period then use `pending --sync`. Old pending records are never retried before the current run succeeds.

Results have `SUCCESS` (exit 0), `PARTIAL` (2), or `FAILED` (1), an exact code, step evidence, recovery instruction, and report when available. `last-run.json` is atomic and sanitized; `status` only reads it.

## User response contract

For normal human output, always return both parts when the script provides a report:

1. Copy the complete `DAILY REPORT RESULT` section through `Next action` into ordinary chat text. Never put this status section in a code fence.
2. Drop the `COPY-READY REPORT` label. End the response with exactly one fenced `text` block containing the report string only.

Never answer with the report block alone. Never put status, headings, labels, explanations, JSON, or trailing text inside or after the report fence.

Required shape:

    === DAILY REPORT RESULT ===
    Overall: SUCCESS
    ...
    Next action: None

    ```text
    Yesterday
    ...

    Today
    ...
    ```

## Guardrails

- Preserve task bullets as `- #id Title`; do not render Python records.
- Do not create repository mutations. The workbook remains local runtime data.
- Do not invent tenant, Dataverse, Azure DevOps, identity, lookup, or schedule defaults.
- If no report is available, print the operational result and recovery action without an empty fenced block. Return raw JSON only when the user explicitly requests JSON.
- Run `python scripts/verify_output.py --config PATH` after a live write when a standalone verification record is required.

## Verify Output

Run `python scripts/verify_output.py --config PATH` to independently reopen the workbook and query the written timesheet line.

Read [README.md](README.md) for setup/recovery details and `references/` for config, auth, and schema fields.
