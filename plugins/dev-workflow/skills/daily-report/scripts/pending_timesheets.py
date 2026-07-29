"""Manage daily-report timesheet items that could not be written yet.

The queue is local runtime state next to DailyTask.xlsx. It lets the skill keep
returning the Teams report when Dynamics has no active period, then retry later.
"""
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

from lib_common import load_config, save_json_atomic
from write_timesheet import format_description


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def queue_path_for(cfg, override=None):
    if override:
        return Path(override)
    return Path(cfg["excel"]["path"]).resolve().parent / "pending-timesheets.json"


def load_queue(path):
    path = Path(path)
    if not path.exists():
        return {"version": 1, "records": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", 1)
    data.setdefault("records", [])
    return data


def save_queue(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def enqueue(queue_path, date_text, today_block, reason):
    data = load_queue(queue_path)
    stamp = now_iso()
    description = format_description(today_block)
    for rec in data["records"]:
        if rec.get("date") == date_text and rec.get("status") == "pending":
            rec.update({
                "todayBlock": today_block,
                "description": description,
                "reason": reason,
                "updatedAt": stamp,
                "lastError": reason,
            })
            save_queue(queue_path, data)
            return rec, "UPDATED"

    rec = {
        "id": date_text,
        "date": date_text,
        "todayBlock": today_block,
        "description": description,
        "reason": reason,
        "status": "pending",
        "attempts": 0,
        "createdAt": stamp,
        "updatedAt": stamp,
        "lastError": reason,
        "syncedAt": None,
    }
    data["records"].append(rec)
    save_queue(queue_path, data)
    return rec, "CREATED"


def enqueue_current(queue_path, date_text, today_block, reason, *, now=now_iso,
                    json_reader=load_queue, atomic_json_writer=save_json_atomic):
    """Atomically add or replace the latest pending record for the current date."""
    data, stamp = json_reader(queue_path), now()
    for record in data["records"]:
        if record.get("date") == date_text and record.get("status") == "pending":
            record.update({"todayBlock": today_block, "description": format_description(today_block),
                           "reason": reason, "updatedAt": stamp, "lastError": reason})
            atomic_json_writer(queue_path, data)
            return record, "UPDATED"
    record = {"id": date_text, "date": date_text, "todayBlock": today_block,
              "description": format_description(today_block), "reason": reason, "status": "pending",
              "attempts": 0, "createdAt": stamp, "updatedAt": stamp, "lastError": reason, "syncedAt": None}
    data["records"].append(record); atomic_json_writer(queue_path, data)
    return record, "CREATED"


def sync_after_current(queue_path, *, current, enqueue, retry):
    """Never let retries of stale records precede handling the current submission."""
    result = current()
    if result.get("status") != "COMMITTED":
        enqueue()
        return {"status": "QUEUED", "current": result}
    return {"status": "COMMITTED", "current": result, "retry": retry()}


def retry_records(records, *, submit, now=now_iso):
    for record in records:
        if record.get("status") != "pending":
            continue
        record["attempts"] = int(record.get("attempts") or 0) + 1
        record["updatedAt"] = now()
        try:
            outcome = submit(record)
            if isinstance(outcome, dict) and outcome.get("status") == "COMMITTED":
                record["status"], record["syncedAt"], record["lastError"] = "synced", record["updatedAt"], None
        except Exception as error:
            record["lastError"] = str(error)
    return records


def prune_records(records, *, now=datetime.datetime.now, days=30):
    cutoff = now() - datetime.timedelta(days=days)
    return [record for record in records if not (record.get("status") == "synced" and record.get("syncedAt") and datetime.datetime.fromisoformat(record["syncedAt"]) < cutoff)]


def list_records(records):
    return sorted(records, key=lambda record: record.get("date", ""))


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _combined_output(result):
    return ((result.stdout or "") + ("\n" if result.stdout and result.stderr else "") + (result.stderr or "")).strip()


def _writer_outcome(result):
    """Read the writer's final JSON envelope; a zero process exit is not proof of a write."""
    try:
        return json.loads((result.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return None


def sync(queue_path, config_path=None, state_dir=None, runner=None, script_path=None):
    data = load_queue(queue_path)
    pending = [r for r in data["records"] if r.get("status") == "pending"]
    if not pending:
        return {"synced": 0, "pending": 0, "failed": 0, "auth_required": False, "messages": ["No pending timesheets."]}

    runner = runner or _run
    script_path = Path(script_path or Path(__file__).with_name("write_timesheet.py"))
    script_dir = str(script_path.parent)
    base = [sys.executable, str(script_path)]
    cfg_args = ["--config", str(config_path)] if config_path else []
    state_args = ["--state-dir", str(state_dir)] if state_dir else []
    messages = []

    auth = runner(base + ["--check-auth"] + cfg_args + state_args, cwd=script_dir)
    if auth.returncode != 0:
        msg = _combined_output(auth)
        messages.append("AUTH_REQUIRED while syncing pending timesheets: " + msg)
        return {"synced": 0, "pending": len(pending), "failed": len(pending),
                "auth_required": True, "messages": messages}

    synced = failed = 0
    for rec in pending:
        rec["attempts"] = int(rec.get("attempts") or 0) + 1
        rec["updatedAt"] = now_iso()
        args = ["--date", rec["date"], "--description", rec["todayBlock"], "--json"]

        dry = runner(base + args + cfg_args + state_args, cwd=script_dir)
        dry_outcome = _writer_outcome(dry)
        if dry.returncode != 0 or not isinstance(dry_outcome, dict) or dry_outcome.get("status") != "DRY_RUN":
            rec["lastError"] = _combined_output(dry)[:1200]
            failed += 1
            messages.append(f"PENDING {rec['date']}: {rec['lastError']}")
            continue

        committed = runner(base + args + ["--commit"] + cfg_args + state_args, cwd=script_dir)
        committed_outcome = _writer_outcome(committed)
        verified = isinstance(committed_outcome, dict) and committed_outcome.get("post_write_verification", {}).get("ok") is True
        if committed.returncode != 0 or not isinstance(committed_outcome, dict) or committed_outcome.get("status") != "COMMITTED" or not verified:
            rec["lastError"] = _combined_output(committed)[:1200]
            failed += 1
            messages.append(f"PENDING {rec['date']}: {rec['lastError']}")
            continue

        rec["status"] = "synced"
        rec["syncedAt"] = now_iso()
        rec["lastError"] = None
        synced += 1
        messages.append(f"SYNCED {rec['date']}")

    save_queue(queue_path, data)
    still_pending = len([r for r in data["records"] if r.get("status") == "pending"])
    return {"synced": synced, "pending": still_pending, "failed": failed,
            "auth_required": False, "messages": messages}


def prune(queue_path, days):
    data = load_queue(queue_path)
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    kept, removed = [], []
    for rec in data["records"]:
        if rec.get("status") == "synced" and rec.get("syncedAt"):
            try:
                synced_at = datetime.datetime.fromisoformat(rec["syncedAt"])
            except ValueError:
                synced_at = datetime.datetime.now()
            if synced_at < cutoff:
                removed.append(rec)
                continue
        kept.append(rec)
    data["records"] = kept
    save_queue(queue_path, data)
    return removed


def print_summary(data):
    records = data.get("records", [])
    if not records:
        print("No pending-timesheet records.")
        return
    for rec in records:
        print(f"- {rec.get('date')} [{rec.get('status')}] attempts={rec.get('attempts', 0)}")
        if rec.get("lastError"):
            print(f"  lastError: {rec['lastError']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--queue")
    sub = ap.add_subparsers(dest="command", required=True)

    enq = sub.add_parser("enqueue")
    enq.add_argument("--date", required=True)
    enq.add_argument("--today", required=True)
    enq.add_argument("--reason", required=True)

    sub.add_parser("sync")

    pr = sub.add_parser("prune")
    pr.add_argument("--days", type=int, default=30)

    sub.add_parser("list")
    args = ap.parse_args()

    cfg = load_config(args.config)
    qpath = queue_path_for(cfg, args.queue)

    if args.command == "enqueue":
        rec, action = enqueue(qpath, args.date, args.today, args.reason)
        print(f"{action} pending timesheet {rec['date']} -> {qpath}")
    elif args.command == "sync":
        result = sync(qpath, args.config)
        print("=== pending-timesheets sync ===")
        for msg in result["messages"]:
            print(msg)
        print(f"synced={result['synced']} pending={result['pending']} failed={result['failed']}")
        if result["auth_required"]:
            sys.exit(2)
    elif args.command == "prune":
        removed = prune(qpath, args.days)
        print(f"Pruned {len(removed)} synced pending-timesheet record(s).")
    elif args.command == "list":
        print_summary(load_queue(qpath))


if __name__ == "__main__":
    main()
