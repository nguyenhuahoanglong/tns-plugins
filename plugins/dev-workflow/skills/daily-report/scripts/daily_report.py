"""Portable daily-report command line workflow.

The CLI owns orchestration. Helpers remain independently testable and never infer
an organisation, identity, workbook location, or repository.
"""
from __future__ import annotations

import sys

# Public commands must never dirty source or installed skill folders.
sys.dont_write_bytecode = True

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path

from lib_common import (RuntimeContext, get_access_token, load_config, resolve_config_path,
                        resolve_runtime_context, save_json_atomic)

SUCCESS, PARTIAL, FAILED = "SUCCESS", "PARTIAL", "FAILED"
_SECRET_MARKERS = ("token", "secret", "password", "authorization", "bearer", "client_secret")


def _sanitize(value, key=""):
    """Remove credentials recursively before durable status is written."""
    if any(marker in key.lower() for marker in _SECRET_MARKERS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(name): _sanitize(item, str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, key) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(token|secret|password|authorization|bearer)(\s*[:=]\s*|\s+)[^\s,;]+", r"\1\2[REDACTED]", value)
    return value


def _bullet(item):
    if isinstance(item, Mapping):
        title, identifier = str(item.get("title") or "").strip(), item.get("id")
        return f"- #{identifier} {title}".rstrip() if identifier is not None else f"- {title}"
    text = str(item or "").strip()
    return text if text.startswith("-") else f"- {text}"


def _report(items):
    return "Yesterday\n\nToday\n" + "\n".join(_bullet(item) for item in items if str(item or "").strip())


def _review_report(config, items):
    """Read yesterday from the workbook without creating or modifying anything."""
    yesterday = ""
    try:
        import openpyxl
        workbook = openpyxl.load_workbook(config["excel"]["path"], read_only=True, data_only=False)
        sheet = workbook[config["excel"]["sheet"]]
        yesterday = str(sheet["C2"].value or "")
    except (OSError, KeyError, ImportError):
        pass
    return "Yesterday\n" + yesterday + "\nToday\n" + "\n".join(_bullet(item) for item in items if str(item or "").strip())


def _result(status, code, *, report="", steps=None, recovery=None, command=None, context=None, date=None, **details):
    """Return the stable result envelope; legacy ``status`` mirrors ``overall``."""
    normalized_steps = []
    for step in steps or []:
        step = dict(step)
        normalized_steps.append({"name": step.pop("name", "workflow"), "status": step.pop("status", "UNKNOWN"),
                                 "action": step.pop("action", None), "details": step, "verified": step.pop("verified", None)})
    return {"schema_version": 1, "command": command, "overall": status, "status": status, "code": code,
            "date": date, "state_dir": str(context.state_dir) if context else None, "steps": normalized_steps,
            "pending": details.pop("pending", {}), "report": report, "warnings": details.pop("warnings", []),
            "next_action": recovery, "recovery": recovery, "verified_at": details.pop("verified_at", None), **details}


def _exit_code(result):
    return 0 if result["status"] == SUCCESS else 2 if result["status"] == PARTIAL else 1


def _runtime(args):
    # Explicit CLI location has highest precedence, then DAILY_REPORT_HOME, then Path.home.
    return resolve_runtime_context(state_dir=getattr(args, "state_dir", None), config_path=getattr(args, "config", None))


def _public_command(context, command, *options):
    """Build one directly runnable command for the exact resolved context."""
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--state-dir",
        str(context.state_dir),
        command,
    ]
    if command in {"doctor", "auth", "run", "pending"}:
        argv.extend(["--config", str(context.config_path)])
    argv.extend(map(str, options))
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def _apply_exact_recovery(result, context):
    code = result.get("code")
    if not result.get("recovery"):
        return result
    if code == "AUTH_REQUIRED":
        recovery = _public_command(context, "auth")
    elif code in {"PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS", "PENDING_REMAINING"}:
        recovery = _public_command(context, "pending", "--sync")
    elif code == "NO_LAST_RUN":
        ready = (
            context.config_path.is_file()
            and (context.state_dir / ".venv").is_dir()
            and (context.state_dir / ".requirements.sha256").is_file()
        )
        recovery = _public_command(context, "run" if ready else "setup")
    elif code == "NO_TASKS":
        recovery = _public_command(context, "run", "--add", "DESCRIPTION")
    elif code in {"SETUP_REQUIRED", "SETUP_FAILED", "DEPENDENCY_INSTALL_FAILED"}:
        recovery = _public_command(context, "setup")
    else:
        recovery = _public_command(context, "run")
    result["next_action"] = result["recovery"] = recovery
    return result


def _dependencies():
    from bootstrap import setup
    from gather_tasks import gather
    from pending_timesheets import enqueue_current, list_records, load_queue, prune, queue_path_for, sync
    from update_dailytask import update_workbook
    from verify_output import verify_run_result
    from write_timesheet import write_timesheet
    return {"setup": setup, "gather": gather,
            "gather_review": lambda config: gather(config, no_temp_files=True),
            "update": update_workbook, "verify": verify_run_result,
            "write": write_timesheet, "enqueue": enqueue_current, "sync": sync, "prune": prune,
            "queue_path_for": queue_path_for, "load_queue": load_queue, "list_records": list_records}


def run(config, context: RuntimeContext | None = None, *, date=None, additions=(), review_only=False, dependencies=None):
    """Create today first; stale pending work is strictly post-success cleanup."""
    if context is None:
        state = Path(config.get("excel", {}).get("path", ".")).parent
        context = RuntimeContext(state, state / "daily-report.config.json", state / "DailyTask.xlsx", state / "pending-timesheets.json", state / "auth-cache.bin", state / "last-run.json")
    deps, day, steps = dependencies or _dependencies(), date or dt.date.today(), []
    if not isinstance(deps, Mapping):
        deps = {"gather": getattr(deps, "gather", getattr(deps, "gather_tasks", None)),
                "update": getattr(deps, "update", getattr(deps, "update_workbook", None)),
                "verify": getattr(deps, "verify", None), "write": getattr(deps, "write", getattr(deps, "write_timesheet", None)),
                "enqueue": getattr(deps, "enqueue", getattr(deps, "enqueue_current", None)),
                "sync": getattr(deps, "sync", getattr(deps, "sync_old_pending", None)),
                "prune": getattr(deps, "prune", getattr(deps, "prune_old_pending", None)),
                "auth": getattr(deps, "auth", getattr(deps, "auth_preflight", None))}
    try:
        gather = deps.get("gather_review") if review_only else None
        tasks = (gather or deps["gather"])(config)
        tasks = tasks[0] if isinstance(tasks, tuple) else tasks
        items = list(tasks) + list(additions); report = _report(items)
        task_ids = [str(item.get("id")) for item in tasks if isinstance(item, Mapping) and item.get("id") is not None]
        steps.append({"name": "gather", "status": "PASS", "count": len(tasks), "task_ids": task_ids})
    except Exception as error:
        return _result(FAILED, "GATHER_FAILED", steps=steps, recovery="Check Azure DevOps configuration and sign-in.", message=str(error))
    if review_only:
        return _result(SUCCESS, "REVIEWED", report=_review_report(config, items), steps=steps + [{"name": "review", "status": "PASS", "action": "PREVIEW"}], mutated=False,
                       verified_at=dt.datetime.now(dt.timezone.utc).isoformat())
    if not items:
        return _result(PARTIAL, "NO_TASKS", report=report, steps=steps, recovery="Add work with --add or review Azure DevOps tasks.")
    try:
        # Silent preflight must precede every workbook mutation.
        auth = deps.get("auth") or get_access_token
        auth(config, interactive=False, cache_path=context.auth_cache_path)
        steps.append({"name": "auth", "status": "PASS"})
    except Exception as error:
        return _result(FAILED, "AUTH_REQUIRED", report=report, steps=steps + [{"name": "auth", "status": "FAIL"}],
                       recovery="Run `daily_report.py auth` interactively, then retry.", message=str(error))
    preview_today = "\n".join(_bullet(item) for item in items)
    # Resolve period/action before any workbook mutation, but still write and
    # verify the workbook when a period is unavailable so the report is usable.
    dry = deps["write"](config, day, preview_today, commit=False, dry_run=True,
                         auth_cache_path=context.auth_cache_path)
    preview_status = "WARN" if dry.get("action") in {"PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"} else (
        "FAIL" if dry.get("status") == "FAIL" else "PASS"
    )
    steps.append({"name": "timesheet_preview", "status": preview_status,
                  "action": dry.get("action", "NOT_RUN"), "result_status": dry.get("status")})
    if dry.get("status") == "FAIL" and dry.get("action") not in {"PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"}:
        return _result(FAILED, dry.get("code", "TIMESHEET_PREVIEW_FAILED"), report=report, steps=steps)
    try:
        workbook = deps["update"](config, preview_today, date=day)
        steps.append({"name": "workbook", "status": "FAIL" if workbook.get("status") == "FAIL" else "PASS",
                      "action": workbook.get("status", "UPDATED"), "mode": workbook.get("mode"),
                      "path": workbook.get("path"), "verified": workbook.get("status") != "FAIL"})
        if workbook.get("status") == "FAIL":
            return _result(FAILED, workbook.get("code", "WORKBOOK_FAILED"), report=report, steps=steps,
                           recovery="Close the workbook and retry.", workbook=workbook)
    except Exception as error:
        return _result(FAILED, "WORKBOOK_FAILED", report=report, steps=steps, recovery="Close the workbook and retry.", message=str(error))
    report = workbook.get("report", report)
    today = workbook.get("today", preview_today)
    if dry.get("action") in {"PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"}:
        record, action = deps["enqueue"](context.queue_path, day.isoformat(), today, dry["action"])
        evidence = {"workbook": workbook, "report": report, "timesheet": {},
                    "queue": {"queued": True, "action": action, "record": record},
                    "operations": [step["name"] for step in steps] + ["queue", "verify"], "date": day}
        verified = deps["verify"](evidence, config=config, date=day)
        passed, failed = verified.get("checks", []), verified.get("failures", [])
        steps.extend(({"name": "queue", "status": "PASS", "action": "QUEUED", "queue_action": action},
                      {"name": "verify", "status": "PASS" if verified.get("ok") else "FAIL",
                       "passed": len(passed), "failed": len(failed),
                       "workbook_passed": len(passed), "workbook_total": len(passed) + len(failed),
                       "live_passed": 0, "live_total": 0}))
        if not verified.get("ok"):
            return _result(FAILED, "VERIFY_FAILED", report=report, steps=steps, workbook=workbook, queue={"action": action, "record": record}, verification=verified)
        return _result(PARTIAL, dry["action"], report=report, steps=steps, workbook=workbook, verification=verified,
                       queue={"action": action, "record": record}, pending={"synced": 0, "failed": 0, "remaining": 1},
                       warnings=[f"Current timesheet queued: {dry['action']}"],
                       recovery="Open or correct the timesheet period, then run pending --sync.", verified_at=dt.datetime.now(dt.timezone.utc).isoformat())
    written = deps["write"](config, day, today, commit=True, dry_run=False,
                             auth_cache_path=context.auth_cache_path)
    steps.append({"name": "timesheet_write", "status": "PASS" if written.get("status") == "COMMITTED" else "FAIL",
                  "action": written.get("action", "NOT_RUN"), "result_status": written.get("status")})
    if written.get("status") != "COMMITTED":
        return _result(FAILED, written.get("code", "TIMESHEET_WRITE_FAILED"), report=report, steps=steps, workbook=workbook)
    evidence = {"workbook": workbook, "report": report, "timesheet": written, "queue": {"queued": False},
                "operations": [step["name"] for step in steps] + ["verify"]}
    evidence["date"] = day
    verified = deps["verify"](evidence, config=config, date=day)
    passed, failed = verified.get("checks", []), verified.get("failures", [])
    live_names = {"timesheet-post-write"}
    live_passed = len([name for name in passed if name in live_names])
    live_failed = len([name for name in failed if name in live_names])
    steps.append({"name": "verify", "status": "PASS" if verified.get("ok") else "FAIL",
                  "passed": len(passed), "failed": len(failed),
                  "workbook_passed": len(passed) - live_passed,
                  "workbook_total": len(passed) + len(failed) - live_passed - live_failed,
                  "live_passed": live_passed, "live_total": live_passed + live_failed})
    if not verified.get("ok"):
        return _result(FAILED, "VERIFY_FAILED", report=report, steps=steps, workbook=workbook, verification=verified)
    # Exact counters are emitted even when no historical work exists.
    pending = deps["sync"](context.queue_path, str(context.config_path), state_dir=context.state_dir); pruned = deps["prune"](context.queue_path, 30)
    pending = {**pending, "remaining": pending.get("remaining", pending.get("pending", 0))}
    steps.append({"name": "pending", "status": "PASS" if not (pending.get("failed") or pending.get("auth_required") or pending["remaining"]) else "WARN", "synced": pending.get("synced", 0), "remaining": pending["remaining"], "failed": pending.get("failed", 0), "pruned": len(pruned)})
    pending_problem = pending.get("failed") or pending.get("auth_required") or pending["remaining"]
    return _result(PARTIAL if pending_problem else SUCCESS, "PENDING_REMAINING" if pending_problem else "COMPLETED", report=report, steps=steps,
                   workbook=workbook, timesheet=written, verification=verified, pending=pending,
                   warnings=([f"Pending timesheets remain: synced={pending.get('synced', 0)} "
                              f"failed={pending.get('failed', 0)} remaining={pending['remaining']}"]
                             if pending_problem else []),
                   recovery="Run pending --sync after resolving the listed records." if pending_problem else None,
                   verified_at=dt.datetime.now(dt.timezone.utc).isoformat())


def _emit(result, as_json, stream):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, default=str), file=stream)
        return
    print("=== DAILY REPORT RESULT ===", file=stream)
    print(f"Overall: {result['status']}", file=stream)
    print(f"Code: {result['code']}", file=stream)
    print(f"Date: {result.get('date') or 'n/a'}", file=stream)
    steps = {step["name"]: step for step in result.get("steps", [])}
    gather, workbook = steps.get("gather", {}), steps.get("workbook", {})
    queue = steps.get("queue", {})
    timesheet, verification, pending_step = steps.get("timesheet_write", {}), steps.get("verify", {}), steps.get("pending", {})
    pending = result.get("pending", {})
    ids = [f"#{identifier}" for identifier in gather.get("details", {}).get("task_ids", [])]
    print(f"ADO: {gather.get('status', 'n/a')} — gathered {gather.get('details', {}).get('count', 0)} task(s): {', '.join(ids) or 'none'}", file=stream)
    workbook_verified = "reopened and verified" if workbook.get("verified") else "not verified"
    print(f"Workbook: {workbook.get('status', 'n/a')} — {workbook.get('action', 'NOT_RUN')}; {workbook_verified}", file=stream)
    if queue:
        print("Timesheet: QUEUED — NOT_RUN", file=stream)
    else:
        print(f"Timesheet: {timesheet.get('status', 'n/a')} — {timesheet.get('action', 'NOT_RUN')}", file=stream)
    verification_details = verification.get("details", {})
    print(f"Verification: {verification.get('status', 'n/a')} — workbook checks "
          f"{verification_details.get('workbook_passed', 0)}/{verification_details.get('workbook_total', 0)}; "
          f"live checks {verification_details.get('live_passed', 0)}/{verification_details.get('live_total', 0)}", file=stream)
    pending_status = pending_step.get("status", "WARN" if pending.get("failed") or pending.get("remaining", pending.get("pending", 0)) else "PASS")
    print(f"Pending: {pending_status} — synced={pending.get('synced', 0)} failed={pending.get('failed', 0)} remaining={pending.get('remaining', pending.get('pending', 0))}", file=stream)
    warnings = result.get("warnings") or []
    print(f"Warnings: {'; '.join(map(str, warnings)) if warnings else 'None'}", file=stream)
    print(f"Next action: {result.get('recovery') or 'None'}", file=stream)
    # A report is always emitted when it was available, including partial/failure states.
    if result.get("report"): print("=== COPY-READY REPORT ===\n```text\n" + result["report"] + "\n```", file=stream)


def build_parser():
    parser = argparse.ArgumentParser(description="Portable daily-report runtime.")
    parser.add_argument("--state-dir", help="Runtime state root (overrides DAILY_REPORT_HOME).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("setup", "Create missing local runtime state."), ("doctor", "Read-only prerequisites check."),
                            ("auth", "Sign in interactively."), ("status", "Read last run without mutation."),
                            ("pending", "Inspect or retry pending records."), ("run", "Create the daily report.")):
        command = sub.add_parser(name, help=help_text); command.add_argument("--json", action="store_true", help="Emit stable JSON result.")
    sub.choices["setup"].add_argument("--import-config"); sub.choices["setup"].add_argument("--import-workbook"); sub.choices["setup"].add_argument("--replace", action="store_true")
    sub.choices["doctor"].add_argument("--config"); sub.choices["auth"].add_argument("--config")
    sub.choices["pending"].add_argument("--config"); sub.choices["pending"].add_argument("--sync", action="store_true", help="Retry pending records."); sub.choices["pending"].add_argument("--prune-days", type=int, default=30)
    run_parser = sub.choices["run"]; run_parser.add_argument("--config"); run_parser.add_argument("--date"); run_parser.add_argument("--add", action="append", default=[]); run_parser.add_argument("--review-only", action="store_true")
    return parser


def main(argv=None, *, stdout=None, dependencies=None):
    args, output = build_parser().parse_args(argv), stdout or sys.stdout
    context, deps = _runtime(args), dependencies
    managed_commands = {"doctor", "auth"} | ({"pending"} if getattr(args, "sync", False) else set()) | ({"run"} if not getattr(args, "review_only", False) else set())
    if args.command in managed_commands and dependencies is None:
        from bootstrap import reexec_managed_venv, setup
        if args.command == "run":
            prepared = setup(context.state_dir)
            if prepared.status not in {"PASS", "WARN"}:
                result = _result(FAILED, prepared.details.get("code", "SETUP_FAILED"), recovery=prepared.message)
                result.update(command=args.command, state_dir=str(context.state_dir), date=getattr(args, "date", None) or dt.date.today().isoformat())
                _apply_exact_recovery(result, context)
                save_json_atomic(context.last_run_path, _sanitize(result))
                _emit(result, args.json, output)
                return _exit_code(result)
        elif not ((context.state_dir / ".venv").is_dir() and (context.state_dir / ".requirements.sha256").is_file()):
            result = _result(PARTIAL, "SETUP_REQUIRED", recovery="Run setup to create the managed runtime.")
            result.update(command=args.command, state_dir=str(context.state_dir), date=dt.date.today().isoformat())
            _apply_exact_recovery(result, context)
            _emit(result, args.json, output)
            return _exit_code(result)
        if reexec_managed_venv(context.state_dir / ".venv", [Path(__file__), *(argv or sys.argv[1:])]):
            return 0
    if args.command == "setup":
        deps = deps or _dependencies()
        raw = deps["setup"](context.state_dir, import_config=args.import_config, import_workbook=args.import_workbook, replace=args.replace)
        result = _result(SUCCESS if raw.status in {"PASS", "WARN"} else FAILED, raw.details.get("code", raw.status), setup=raw.to_dict() if hasattr(raw, "to_dict") else str(raw))
    elif args.command == "doctor":
        from doctor import run_doctor
        raw = run_doctor(config=args.config or str(context.config_path)); result = _result(SUCCESS if raw.status == "PASS" else PARTIAL if raw.status == "WARN" else FAILED, raw.status, checks=raw.to_dict())
    elif args.command == "auth":
        try: get_access_token(load_config(context.config_path), interactive=True, cache_path=context.auth_cache_path); result = _result(SUCCESS, "AUTH_OK")
        except Exception as error: result = _result(FAILED, "AUTH_REQUIRED", recovery="Complete device sign-in and retry.", message=str(error))
    elif args.command == "status":
        counters = {"synced": 0, "pending": 0, "failed": 0}
        if context.queue_path.is_file():
            deps = deps or _dependencies()
            records = deps["load_queue"](context.queue_path).get("records", [])
            counters["pending"] = sum(record.get("status") == "pending" for record in records)
            counters["synced"] = sum(record.get("status") == "synced" for record in records)
            counters["failed"] = sum(record.get("status") == "failed" for record in records)
        if not context.last_run_path.is_file(): result = _result(PARTIAL, "NO_LAST_RUN", recovery="Run the first report.", pending=counters)
        else:
            result = json.loads(context.last_run_path.read_text(encoding="utf-8"))
            result.update(read_only=True, current_queue=counters)
    elif args.command == "pending":
        if not context.config_path.is_file(): result = _result(PARTIAL, "SETUP_REQUIRED", recovery="Run setup and configure the runtime.")
        else:
            deps = deps or _dependencies()
            config = load_config(context.config_path); queue = context.queue_path
            if args.sync: data = deps["sync"](queue, str(context.config_path), state_dir=context.state_dir); pruned = deps["prune"](queue, args.prune_days); result = _result(SUCCESS if not (data.get("failed") or data.get("auth_required") or data.get("pending")) else PARTIAL, "PENDING_SYNC", pending=data, pruned=len(pruned))
            else: result = _result(SUCCESS, "PENDING_STATUS", records=deps["list_records"](deps["load_queue"](queue).get("records", [])), read_only=True)
    else:
        if args.review_only and not (context.config_path.is_file() and (context.state_dir / ".venv").is_dir() and (context.state_dir / ".requirements.sha256").is_file()): result = _result(PARTIAL, "SETUP_REQUIRED", recovery="Run setup before review-only can gather configured work.")
        elif not context.config_path.is_file(): result = _result(FAILED, "SETUP_REQUIRED", recovery="Run setup and complete the portable config.")
        else:
            deps = deps or _dependencies()
            when = dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
            result = run(load_config(args.config or context.config_path), context, date=when, additions=args.add, review_only=args.review_only, dependencies=deps)
        result.update(command=args.command, state_dir=str(context.state_dir), date=result.get("date") or (getattr(args, "date", None) or dt.date.today().isoformat()))
    result.update(command=args.command, state_dir=str(context.state_dir), date=result.get("date") or (getattr(args, "date", None) or dt.date.today().isoformat()))
    _apply_exact_recovery(result, context)
    if args.command == "run" and not args.review_only:
        save_json_atomic(context.last_run_path, _sanitize(result))
    _emit(result, args.json, output)
    return _exit_code(result)


if __name__ == "__main__": raise SystemExit(main())
