"""Guardrail for the daily-report skill — verifies the day's outputs against the acceptance criteria.

Checks (deterministic):
  1. Excel row 2 is today's date, with a real datetime + preserved number format.
  2. Yesterday / Today / Report / Timesheet-memo columns are all populated.
  3. The report (column E) matches the "Yesterday\\n...\\nToday\\n..." template.
  4. Unless --skip-timesheet: a timesheet detail line exists for today in the portal.

Exit 0 = all pass; exit 1 = at least one FAIL.

Usage:
  python verify_output.py [--date YYYY-MM-DD] [--config PATH] [--skip-timesheet]
"""
import argparse, datetime, sys
import openpyxl
from lib_common import load_config

PASS, FAIL = "PASS", "FAIL"


def verify_run_result(result, config=None):
    """Verify portable orchestration evidence; no live token or employee config needed."""
    checks = []
    workbook = result.get("workbook") if isinstance(result, dict) else None
    workbook_path = (workbook or {}).get("path") if isinstance(workbook, dict) else None
    if not workbook_path and isinstance(workbook, dict):
        workbook_path = workbook.get("workbook")
    checks.append((bool(workbook_path), "portable-path"))
    checks.append((bool(workbook) and (workbook.get("updated", True) is not False), "workbook"))
    report = result.get("report", "") if isinstance(result, dict) else ""
    checks.append((isinstance(report, str) and report.startswith("Yesterday\n") and "\nToday\n" in report, "report"))
    timesheet = result.get("timesheet", {}) if isinstance(result, dict) else {}
    queue = result.get("queue", {}) if isinstance(result, dict) else {}
    checks.append((bool(timesheet.get("action") or queue.get("queued")), "timesheet-or-queue"))
    operations = result.get("operations", []) if isinstance(result, dict) else []
    expected = ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify"]
    checks.append((operations[:len(expected)] == expected, "operation-order"))
    return {"ok": all(ok for ok, _ in checks), "checks": [name for ok, name in checks if ok],
            "failures": [name for ok, name in checks if not ok]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--config")
    ap.add_argument("--skip-timesheet", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    today = (datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
             if args.date else datetime.date.today())
    results = []

    # --- Excel checks ---
    wb = openpyxl.load_workbook(cfg["excel"]["path"])
    ws = wb[cfg["excel"]["sheet"]]
    a2, b2, c2, e2, f2 = (ws["A2"].value, ws["B2"].value, ws["C2"].value,
                          ws["E2"].value, ws["F2"].value)

    a2_date = a2.date() if isinstance(a2, datetime.datetime) else None
    results.append((a2_date == today, "Excel row 2 date is today",
                    f"got {a2_date!r}, expected {today}"))
    results.append((isinstance(a2, datetime.datetime) and ws["A2"].number_format not in (None, "General"),
                    "Date cell keeps a date number format", f"format={ws['A2'].number_format!r}"))
    results.append((bool(b2 and str(b2).strip()), "Yesterday populated", repr(b2)[:60]))
    results.append((bool(c2 and str(c2).strip()), "Today populated", repr(c2)[:60]))
    results.append((bool(f2 and "Task Description:" in str(f2)), "Timesheet memo populated", repr(f2)[:60]))

    expected_report = f"Yesterday\n{b2}\nToday\n{c2}"
    results.append((e2 == expected_report, "Report matches Yesterday/Today template",
                    "column E differs from composed report"))

    # --- Timesheet check ---
    if not args.skip_timesheet:
        try:
            from lib_common import get_access_token, Dataverse, who_am_i
            tok = get_access_token(cfg, interactive=False)
            dv = Dataverse(cfg, tok)
            ts = cfg["timesheet"]
            who_am_i(cfg, tok)
            flt = f"cr90e_taskdate eq {today.isoformat()}"
            r = dv.get(f"{ts['detail_entity_set']}?$filter={flt}&$select=cr90e_linenbr")
            n = len(r["json"].get("value", []))
            results.append((n >= 1, "Timesheet line exists for today", f"found {n} line(s)"))
        except SystemExit as e:
            results.append((False, "Timesheet line exists for today", f"auth/query unavailable: {e}"))

    # --- report ---
    ok = all(r[0] for r in results)
    print("=== daily-report verify ===")
    for passed, name, detail in results:
        print(f"  [{PASS if passed else FAIL}] {name}" + ("" if passed else f"  ({detail})"))
    print(f"=== {'ALL PASS' if ok else 'FAILURES PRESENT'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
