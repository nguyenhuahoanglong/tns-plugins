"""Portable, offline-testable daily-report orchestration."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Mapping
from types import SimpleNamespace

from lib_common import load_config, resolve_state_paths


def _as_bullet(item):
    """Render one report line.

    Gathered work arrives as task records, while ``--add`` supplies plain text. A record
    formatted with ``str()`` leaks a dict repr into the workbook and the timesheet
    description, so records are formatted explicitly here.
    """
    if isinstance(item, Mapping):
        identifier, title = item.get("id"), str(item.get("title") or "").strip()
        if identifier is not None:
            return f"- #{identifier} {title}".rstrip()
        if title:
            return f"- {title}"
    text = str(item).strip()
    return text if text.startswith("-") else f"- {text}"


def _today_block(items):
    """Join report lines for the workbook's Today block and the copy-ready report."""
    return "\n".join(_as_bullet(item) for item in items)


def _default_dependencies():
    """Wire production helpers behind the same small seam used by tests."""
    from bootstrap import setup
    from doctor import main as doctor_cli
    from gather_tasks import gather
    from update_dailytask import update_workbook
    from write_timesheet import write_timesheet
    from pending_timesheets import enqueue_current, queue_path_for, sync, prune
    from commit_workbook import backup_workbook
    from lib_common import get_access_token

    def merge(tasks, additions):
        return list(tasks) + list(additions)

    def gather_tasks(config):
        gathered = gather(config)
        return gathered[0] if isinstance(gathered, tuple) else gathered

    def render_report(items):
        return "Yesterday\n\nToday\n" + _today_block(items)

    def bootstrap(state_or_config, **options):
        state_dir = resolve_state_paths()["state_dir"] if isinstance(state_or_config, dict) else state_or_config
        return setup(state_dir, **options)

    def workbook(config, items, when):
        return update_workbook(config, _today_block(items), date=when)

    def enqueue(config, payload, error=None):
        report_date = payload.get("date", dt.date.today().isoformat())
        today = payload.get("today", payload.get("report", ""))
        record, action = enqueue_current(queue_path_for(config), report_date, today, str(error or "pending"))
        return {"queued": True, "action": action, "record": record}

    def verifier(result):
        from verify_output import verify_run_result
        return verify_run_result(result)

    return SimpleNamespace(
        bootstrap=bootstrap,
        doctor=lambda config=None: doctor_cli(["--config", str(config)] if config else []),
        gather_tasks=gather_tasks,
        merge_additions=merge,
        render_report=render_report,
        update_workbook=workbook,
        auth_preflight=lambda config: get_access_token(config, interactive=False),
        write_timesheet=write_timesheet,
        enqueue_current=enqueue,
        verify=verifier,
        backup_workbook=lambda config, workbook_path: backup_workbook(config),
        sync_old_pending=lambda config: sync(queue_path_for(config)),
        prune_old_pending=lambda config: prune(queue_path_for(config), 30),
    )


def _defaults():
    """Compatibility name for callers created before the explicit factory."""
    return _default_dependencies()


def _code(error, fallback="WORKFLOW_FAILED"):
    text = str(error)
    for marker in ("AUTH_REQUIRED", "WORKBOOK_LOCKED", "NO_ACTIVE_PERIOD", "AMBIGUOUS_PERIOD"):
        if marker in text:
            return marker
    return fallback


def run(config, *, date=None, additions=(), review_only=False, backup=False, dependencies=None):
    """Run current report before stale queue retries; every mutation is injectable."""
    deps = dependencies or _defaults()
    when = date or dt.date.today()
    operations = []
    deps.bootstrap(config); operations.append("bootstrap")
    tasks = deps.gather_tasks(config); operations.append("gather")
    items = deps.merge_additions(tasks, additions); operations.append("merge")
    if review_only:
        result = {"ok": True, "review_only": True, "operations": operations, "tasks": items}
        if hasattr(deps, "render_report"):
            result["report"] = deps.render_report([str(item) for item in items])
        return result
    if not items:
        return {"ok": False, "code": "NO_TASKS", "operations": operations,
                "message": "No active tasks. Review additions or try again later."}
    try:
        workbook = deps.update_workbook(config, items, when); operations.append("workbook")
        if isinstance(workbook, dict) and workbook.get("status") == "FAIL":
            return {"ok": False, "code": workbook.get("code", "WORKBOOK_FAILED"), "operations": operations, "workbook": workbook}
    except Exception as error:
        operations.append("workbook")
        return {"ok": False, "code": _code(error), "operations": operations, "message": str(error)}
    report = workbook.get("report", "") if isinstance(workbook, dict) else ""
    # The timesheet records only the day's own work. The Yesterday/Today report is the
    # Teams standup format and must not reach the portal, where every other day holds
    # just that day's lines.
    today_block = (workbook.get("today", "") if isinstance(workbook, dict) else "") or report
    try:
        deps.auth_preflight(config); operations.append("auth")
    except Exception as error:
        operations.append("auth")
        queued = deps.enqueue_current(config, {"date": when.isoformat(), "report": report, "today": today_block}, error); operations.append("enqueue")
        return {"ok": False, "code": _code(error), "operations": operations, "workbook": workbook,
                "report": report, "timesheet": queued, "queue": queued}
    try:
        dry = deps.write_timesheet(config, when, today_block, commit=False, dry_run=True); operations.append("timesheet-dry-run")
        if isinstance(dry, dict) and (dry.get("status") == "FAIL" or dry.get("action") in {"PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"}):
            code = dry.get("action") or dry.get("code") or "TIMESHEET_DRY_RUN_FAILED"
            queued = deps.enqueue_current(config, {"date": when.isoformat(), "report": report, "today": today_block}, code); operations.append("enqueue")
            return {"ok": False, "code": code, "operations": operations, "workbook": workbook,
                    "report": report, "timesheet": dry, "queue": queued}
        committed = deps.write_timesheet(config, when, today_block, commit=True, dry_run=False); operations.append("timesheet-write")
    except Exception as error:
        code = _code(error)
        queued = deps.enqueue_current(config, {"date": when.isoformat(), "report": report, "today": today_block}, error); operations.append("enqueue")
        return {"ok": False, "code": code, "operations": operations, "workbook": workbook,
                "report": report, "timesheet": queued, "queue": queued}
    result = {"ok": True, "workbook": workbook, "report": report, "timesheet": committed,
              "queue": {"queued": False}, "operations": operations + ["verify"]}
    verdict = deps.verify(result); operations.append("verify")
    if not isinstance(verdict, dict) or not verdict.get("ok"):
        result.update(ok=False, code="VERIFY_FAILED", verification=verdict, operations=operations)
        return result
    result["verification"] = verdict
    if backup:
        result["backup"] = deps.backup_workbook(config, workbook.get("path", workbook.get("workbook")) if isinstance(workbook, dict) else workbook); operations.append("backup")
    result["operations"] = operations
    result["current"] = {"ok": True, "timesheet": committed}
    try:
        result["old_pending"] = {"ok": True, "sync": deps.sync_old_pending(config)}; operations.append("sync-old-pending")
        result["old_pending"]["prune"] = deps.prune_old_pending(config); operations.append("prune-old-pending")
    except Exception as error:
        operations.append("sync-old-pending")
        result["old_pending"] = {"ok": False, "code": _code(error, "OLD_PENDING_FAILED"), "message": str(error)}
    result["operations"] = operations
    return result


def _emit(stdout, result, *, fenced=False):
    print("=== daily-report status ===", file=stdout)
    print(json.dumps({key: value for key, value in result.items() if key != "report"}, default=str), file=stdout)
    if result.get("ok") and result.get("report"):
        print("=== copy-ready report ===", file=stdout)
        if fenced:
            print("```text", file=stdout)
        print(result["report"], file=stdout)
        if fenced:
            print("```", file=stdout)


def main(argv=None, *, config_loader=load_config, dependencies=None, stdout=None, state_resolver=resolve_state_paths):
    parser = argparse.ArgumentParser(description="Portable daily-report workflow.")
    parser.add_argument("command", choices=("setup", "doctor", "run", "pending"))
    parser.add_argument("--config")
    parser.add_argument("--date")
    parser.add_argument("--add", action="append", default=[])
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--import-config")
    parser.add_argument("--import-workbook")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    deps = dependencies or _default_dependencies()
    output = stdout or sys.stdout
    if args.command == "setup":
        state = state_resolver()["state_dir"]
        options = {"import_config": args.import_config, "import_workbook": args.import_workbook,
                   "replace": args.replace}
        result = deps.bootstrap(state, **options) if any(options.values()) else deps.bootstrap(state)
        return 0 if not isinstance(result, dict) or result.get("status") != "FAIL" else 1
    if args.command == "doctor":
        # Diagnostics must work on a first-run machine, so never *load* config first.
        # The path is still passed so an existing config is validated; doctor reports a
        # missing file as "not initialized" rather than failing to start.
        deps.doctor(args.config or state_resolver()["config_path"]); return 0
    config = config_loader(args.config)
    if args.command == "pending":
        deps.sync_old_pending(config); return 0
    when = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    result = run(config, date=when, additions=args.add, review_only=args.review_only, backup=args.backup, dependencies=deps)
    _emit(output, result, fenced=args.date is None)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
