# Portable configuration

`daily-report` owns local state; it never relies on a caller working directory.

## State location

Every platform defaults to `~/.ai/data/daily-report`. This keeps config,
workbook, queue, encrypted authentication cache, managed environment, and run
status under one predictable user-local root.

`DAILY_REPORT_HOME` replaces the state root. State holds:

- `daily-report.config.json`
- `DailyTask.xlsx`
- `pending-timesheets.json`
- `auth-cache.bin`
- `last-run.json`
- `.venv/`
- `.requirements.sha256`

Config resolution is: `--config PATH`, then `DAILY_REPORT_CONFIG`, then the
state-root config file. Keep the live config and cache out of source control.

## First run and diagnosis

Python 3.11 or newer is required. Run `daily_report.py setup` to create missing
state without replacing existing files. Migration is explicit:

```text
daily_report.py setup --import-config OLD.json --import-workbook OLD.xlsx --replace
```

Run `daily_report.py doctor` for read-only prerequisite checks. It reports
Python, Azure CLI, Azure DevOps extension/login, secure cache, config, workbook,
and guarded service status. Git is not required. Fix a reported prerequisite
before retrying; doctor does not write a workbook or authenticate interactively.

## Config shape

Start from `assets/config-template.json`. Fill only values valid for your own
environment.

```jsonc
{
  "excel": { "path": "", "sheet": "Daily Report" },
  "ado": {
    "organization": "", "projects": [], "teams": [], "member_identity": "",
    "active_states": ["Active", "In Progress"]
  },
  "timesheet": {
    "org_url": "", "tenant_id": "", "client_id": "",
    "header_entity_set": "", "detail_entity_set": "",
    "defaults": {
      "task_days": 1.0, "description_style": "semicolon",
      "location_option": 0, "location_label": "",
      "travel_by_option": 0, "from_hour_local": "09:00",
      "to_hour_local": "18:00", "timezone_offset_hours": 0,
      "bindings": {
        "navigation_property": {
          "set": "entity_set", "code": "BUSINESS-CODE",
          "code_field": "logical_code_field", "id_field": "logical_id_field"
        }
      }
    }
  }
}
```

ADO requires explicit organization, project list, team list, and member identity;
do not depend on a machine-level default project. Each lookup binding needs a
set, business code, code field, and id field. IDs are resolved at runtime, not
stored in config.

### Projects in more than one organization

`ado.organization` is the default for every project. A team entry may carry its own
`organization` to override it, so projects hosted in different Azure DevOps
organizations are gathered in one run. Entries without an `organization` inherit the
root value, so single-organization configuration needs no change.

```jsonc
{
  "ado": {
    "organization": "https://dev.azure.com/example-org",
    "projects": ["Project One", "Project Two"],
    "teams": [
      { "project": "Project One", "team": "Team One" },
      { "project": "Project Two", "team": "Team Two",
        "organization": "https://dev.azure.com/other-org" }
    ]
  }
}
```

Use the full organization URL, not a bare organization name.

Gathering resolves the current sprint with `--timeframe current`, then queries work
items through `az devops invoke` (Work Item Tracking `wiql`, then `workitemsbatch` to
fetch fields). `az boards query` is not used: on some Azure CLI builds it exits 0 with
no output, and it rejects `--team`, which the team iteration lookup does require.

## Queue and runtime status

Pending submissions use `pending-timesheets.json`. Current work is enqueued
before old records are retried; synced records may be pruned later. The runtime
never stages, backs up, or commits a workbook. `last-run.json` is an atomic,
sanitized status document read without mutation by `daily_report.py status`.
