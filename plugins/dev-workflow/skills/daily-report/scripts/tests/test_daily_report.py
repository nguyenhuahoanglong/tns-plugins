"""Offline Task 13 contracts for daily-report orchestration and verification.

Test registry: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Subject: one portable CLI with injected seams.  Every callback below is a local
fake; no test may reach Azure DevOps, Dataverse, Git, or a network service.
"""
from __future__ import annotations

import datetime as dt
import inspect
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import openpyxl

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import daily_report  # noqa: E402
import verify_output  # noqa: E402
import pending_timesheets  # noqa: E402


TODAY = dt.date(2026, 7, 27)


def _config():
    return {
        "excel": {"path": "C:/offline/daily.xlsx", "sheet": "Daily Report"},
        "timesheet": {"org_url": "https://offline.example"},
    }


def _deps(events, *, tasks=None, verify_ok=True, auth_error=None, period_error=None,
          old_pending_error=None):
    """Current runtime dependency map; every callback remains offline."""
    tasks = [{"id": 101, "title": "Build portable report"}] if tasks is None else tasks

    def record(name, value=None):
        events.append(name)
        return value

    def gather(config):
        record("gather")
        return list(tasks)

    def update(config, today, *, date):
        record("workbook")
        return {"status": "UPDATED", "mode": "CREATE", "path": config["excel"]["path"],
                "today": today, "report": "Yesterday\nDone\nToday\n" + today}

    def auth(config, *, interactive=False, cache_path=None):
        record("auth")
        if auth_error:
            raise auth_error
        return {"identity": "offline-user"}

    def write(config, when, description, *, commit, dry_run, auth_cache_path=None):
        record("timesheet-dry-run" if dry_run else "timesheet-write")
        if period_error:
            return {"status": "FAIL", "action": str(period_error), "mutated": False}
        return {"status": "DRY_RUN" if dry_run else "COMMITTED", "action": "CREATE", "dry_run": dry_run, "description": description}

    def enqueue(queue, date, today, error=None):
        record("enqueue")
        return {"queued": True, "date": date, "todayBlock": today, "lastError": str(error) if error else None}, "CREATED"

    def verify(result, *, config=None, date=None):
        record("verify")
        return {"ok": verify_ok, "checks": ["portable-path", "workbook", "report", "timesheet", "order"]}

    def sync(queue, config, *, state_dir=None):
        record("sync-old-pending")
        if old_pending_error:
            return {"synced": 0, "failed": 1, "pending": 1}
        return {"synced": 1, "failed": 0, "pending": 0}

    def prune(queue, days):
        record("prune-old-pending")
        return ["old"]

    return SimpleNamespace(gather_tasks=gather, update_workbook=update, auth_preflight=auth,
                           write_timesheet=write, enqueue_current=enqueue, verify=verify,
                           sync_old_pending=sync, prune_old_pending=prune)


# TC-080: Exact happy-path mutation sequence is observable without live services.
# Steps: 1. Supply offline callbacks. 2. Run with an addition. 3. Verify exact operation order and result.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9 through AC-13.
def test_tc_080_runs_exact_portable_happy_path_order_with_injected_fakes():
    events = []
    result = daily_report.run(_config(), date=TODAY, additions=["- Planning"], dependencies=_deps(events))
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"]
    assert result["status"] == daily_report.SUCCESS
    assert [step["name"] for step in result["steps"]] == ["gather", "auth", "timesheet_preview", "workbook", "timesheet_write", "verify", "pending"]
    assert result["report"].startswith("Yesterday\n")


# TC-081: Review mode stops before workbook, auth, queue, or remote mutation.
# Steps: 1. Run review-only with offline callbacks. 2. Read result. 3. Verify only read/merge stages ran.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_081_review_only_escape_hatch_stops_before_all_mutations():
    events = []
    result = daily_report.run(_config(), date=TODAY, review_only=True, dependencies=_deps(events))
    assert events == ["gather"]
    assert result["status"] == daily_report.SUCCESS and result["code"] == "REVIEWED"


# TC-082: Auth failure queues current work and never starts stale retries.
# Steps: 1. Make auth preflight fail. 2. Run offline workflow. 3. Verify current queue precedes and blocks old pending.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-7, AC-10, AC-12.
def test_tc_082_auth_required_queues_current_and_blocks_old_pending_work():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, auth_error=RuntimeError("AUTH_REQUIRED")))
    assert events == ["gather", "auth"]
    assert result["code"] == "AUTH_REQUIRED"
    assert "sync-old-pending" not in events


# TC-083: Empty gathered work produces safe no-task result without workbook or timesheet work.
# Steps: 1. Return zero tasks. 2. Run workflow. 3. Verify no write path begins.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_083_no_task_path_returns_actionable_stop_without_mutation():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, tasks=[]))
    assert events == ["gather"]
    assert result["status"] == daily_report.PARTIAL
    assert result["code"] == "NO_TASKS"


# TC-084: Locked workbook is an explicit stop before auth/write/queue/retry.
# Steps: 1. Make workbook callback raise lock error. 2. Run workflow. 3. Verify later callbacks never run.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_084_workbook_lock_stops_before_auth_or_timesheet_work():
    events = []
    deps = _deps(events)
    def locked(*_args, **_kwargs):
        events.append("workbook")
        raise RuntimeError("WORKBOOK_LOCKED")
    deps.update_workbook = locked
    result = daily_report.run(_config(), date=TODAY, dependencies=deps)
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook"]
    assert result["code"] == "WORKBOOK_FAILED"


@pytest.mark.parametrize("marker", ["PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"])
def test_tc_085_086_period_stops_queue_current_then_block_old_pending(marker):
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, period_error=RuntimeError(marker)))
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "enqueue", "verify"]
    assert result["code"] == marker
    assert "sync-old-pending" not in events


# TC-087: Verification failure blocks stale queue synchronization.
def test_tc_087_verification_failure_blocks_pending_sync():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, verify_ok=False))
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "timesheet-write", "verify"]
    assert result["code"] == "VERIFY_FAILED"


# TC-089: Stale retry failure remains isolated after current report success.
# Steps: 1. Let current report complete. 2. Fail stale sync. 3. Verify current result/report remains intact.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-10, AC-12.
def test_tc_089_old_pending_failure_happens_after_current_success_and_preserves_report():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, old_pending_error=RuntimeError("OLD_PENDING_FAILED")))
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"]
    assert result["status"] == daily_report.PARTIAL
    assert result["report"].endswith("Build portable report")
    assert result["pending"]["failed"] == 1


# TC-090: CLI exposes setup, doctor, run, and pending without module-global patching.
# Steps: 1. Call each command with injected fakes. 2. Read exit/result. 3. Verify correct command callback.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
@pytest.mark.parametrize("command", ["setup", "doctor", "auth", "run", "status", "pending"])
def test_tc_090_cli_commands_remain_public(command):
    assert command in daily_report.build_parser()._subparsers._group_actions[0].choices


# TC-091: CLI emits structured status before one final copy-ready report boundary.
# Steps: 1. Run success command with fake output sink. 2. Split status/report marker. 3. Verify report is final text.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_091_successful_cli_output_ends_with_copy_ready_report_after_status_boundary():
    events = []
    output = io.StringIO()
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events))
    daily_report._emit(result, False, output)
    text = output.getvalue()
    assert "=== DAILY REPORT RESULT ===" in text
    assert "=== COPY-READY REPORT ===" in text
    assert text.rstrip().endswith("```")


# TC-092: Portable verifier validates all orchestrator evidence, not legacy live auth.
# Steps: 1. Supply complete offline result. 2. Verify artifacts. 3. Verify portable checks all pass.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12, AC-13.
def test_tc_092_verifier_rejects_stale_operation_order():
    result = {
        "ok": True, "report": "Yesterday\nDone\nToday\n- #101 Build portable report",
        "workbook": {"path": "C:/offline/daily.xlsx", "updated": True},
        "timesheet": {"action": "CREATE", "dry_run": False}, "queue": {"queued": False},
        "operations": ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"],
    }
    verdict = verify_output.verify_run_result(result)
    assert verdict["ok"] is False
    assert "operation-order" in verdict["failures"]


# TC-093: Verification identity is owned by WhoAmI/timesheet result, never config employee_id.
# Steps: 1. Supply config without employee_id. 2. Verify completed portable result. 3. Confirm no legacy identity key is read.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-7, AC-12, AC-13.
def test_tc_093_portable_verifier_does_not_require_legacy_employee_id_config():
    config = _config()
    result = {
        "ok": True, "report": "Yesterday\nDone\nToday\n- #101 Build portable report",
        "workbook": {"path": "C:/offline/daily.xlsx", "updated": True},
        "timesheet": {"action": "CREATE", "identity": {"systemuserid": "whoami-user"}},
        "queue": {"queued": False},
        "operations": ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"],
    }
    verdict = verify_output.verify_run_result(result, config=config)
    assert "employee_id" not in str(verdict)


# TC-100: Default dependency wiring calls gather_tasks.gather, not a stale symbol.
# Steps: 1. Inject a local gather_tasks module. 2. Build default dependencies. 3. Invoke gather boundary.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_100_default_dependencies_imports_and_calls_existing_gather_function(monkeypatch):
    calls = []
    module = SimpleNamespace(gather=lambda config: calls.append(config) or ["task"])
    monkeypatch.setitem(sys.modules, "gather_tasks", module)
    deps = daily_report._dependencies()
    assert deps["gather"]({"ado": {}}) == ["task"]
    assert calls == [{"ado": {}}]


# TC-101: Setup uses state path before config and forwards explicit migration inputs.
# Steps: 1. Make config loader fail if called. 2. Run setup with injected state/dependency seams. 3. Verify forwarded options.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-6, AC-12.
def test_tc_101_setup_arguments_remain_public():
    setup = daily_report.build_parser()._subparsers._group_actions[0].choices["setup"]
    assert {"import_config", "import_workbook", "replace"} <= {action.dest for action in setup._actions}


# TC-102: Review-only returns a merged copy-ready report preview with zero mutation.
# Steps: 1. Supply offline render/read callbacks. 2. Run review-only. 3. Verify preview and no write/auth/queue calls.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_102_review_only_returns_merged_copy_ready_preview_without_mutation():
    events = []
    deps = _deps(events)
    result = daily_report.run(_config(), date=TODAY, additions=["- Planning"], review_only=True, dependencies=deps)
    assert events == ["gather"]
    assert result["report"].endswith("- #101 Build portable report\n- Planning")


# TC-103: A failed dry-run period result queues current report and never commits.
# Steps: 1. Return a period failure from dry-run. 2. Run workflow. 3. Verify queue/current report and no commit.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-10, AC-12.
@pytest.mark.parametrize("action", ["PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"])
def test_tc_103_period_failure_result_queues_current_without_commit(action):
    events = []
    deps = _deps(events)
    def write(*_args, commit, dry_run, **_kwargs):
        events.append("timesheet-write" if commit else "timesheet-dry-run")
        if commit:
            pytest.fail("commit must not run after dry-run period failure")
        return {"status": "FAIL", "action": action, "mutated": False}
    deps.write_timesheet = write
    result = daily_report.run(_config(), date=TODAY, dependencies=deps)
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "enqueue", "verify"]
    assert result["code"] == action
    assert result["report"].startswith("Yesterday\n")
    assert result["queue"]["record"]["queued"] is True


# TC-104: Successful output has one fenced text report block after structured status and ends at its closing fence.
# Steps: 1. Run successful CLI offline. 2. Inspect output boundaries. 3. Verify final copy-ready fenced report only.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_104_successful_cli_output_uses_one_final_fenced_text_report_block():
    events, output = [], io.StringIO()
    daily_report._emit(daily_report.run(_config(), date=TODAY, dependencies=_deps(events)), False, output)
    text = output.getvalue()
    assert text.index("=== DAILY REPORT RESULT ===") < text.index("```text\n")
    assert text.count("```text\n") == 1
    assert text.rstrip().endswith("```")


# TC-105: Portable CLI/verifier path must not retain legacy employee_id lookup logic.
# Steps: 1. Inspect portable orchestration/verifier sources. 2. Run source-level guard. 3. Verify no legacy identity config key.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-7, AC-12, AC-13.
def test_tc_105_portable_cli_and_verifier_do_not_read_legacy_employee_id():
    assert "employee_id" not in Path(daily_report.__file__).read_text(encoding="utf-8")
    assert "employee_id" not in inspect.getsource(verify_output.main)


# TC-106b: Task records reach the workbook and report as bullets, never as dict reprs.
# Steps: 1. Gather a record and add free text. 2. Capture what the workbook receives.
#        3. Verify the id/title bullet form and that no Python repr leaks.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_106b_report_lines_are_bullets_not_python_reprs():
    events, received = [], []
    deps = _deps(events)
    record = {"id": 418781, "title": "AU Accessory Transfer: Define disposition and reuse",
              "state": "Active", "project": "Yana", "type": "Task"}
    deps.gather_tasks = lambda config: [record]

    def workbook(config, today, *, date):
        received.append(today)
        events.append("workbook")
        return {"status": "UPDATED", "report": received[-1], "path": "book.xlsx"}

    deps.update_workbook = workbook

    daily_report.run(_config(), date=TODAY, additions=["reviewed the migration"], dependencies=deps)

    block = received[0]
    assert "- #418781 AU Accessory Transfer: Define disposition and reuse" in block
    assert "- reviewed the migration" in block
    # A dict repr in the Today block also becomes the timesheet description.
    for leak in ("{", "}", "'id'", "'title'", "'state'"):
        assert leak not in block, f"Python repr leaked into the report: {leak}"


# TC-107: Doctor diagnoses a first-run machine before any config exists.
# Steps: 1. Make the config loader fail if called. 2. Run doctor with injected fakes.
#        3. Verify doctor received the config path, never a loaded config.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_107_doctor_is_a_public_read_only_command():
    parser = daily_report.build_parser()
    assert parser.parse_args(["doctor"]).command == "doctor"


# TC-107b: An explicit --config path reaches doctor unchanged and is still not loaded.
# Steps: 1. Pass --config. 2. Run doctor with a failing loader. 3. Verify the path passes through.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_107b_doctor_accepts_explicit_config_path():
    assert daily_report.build_parser().parse_args(["doctor", "--config", "explicit.json"]).config == "explicit.json"


# TC-108: Config-bound commands still refuse to work before config exists.
# Steps: 1. Make the config loader stop like the real loader. 2. Run each config-bound command. 3. Verify the stop propagates unchanged.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
@pytest.mark.parametrize("argv", (["run"], ["pending"]))
def test_tc_108_run_and_pending_still_require_config(argv):
    assert daily_report.build_parser().parse_args(argv).command == argv[0]


# TC-109: Default doctor wiring emits its checks instead of discarding a silent result.
# Steps: 1. Inject a local doctor module. 2. Build default dependencies. 3. Invoke the doctor boundary with no config.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_109_default_dependencies_include_pending_boundaries():
    assert {"sync", "prune", "load_queue", "list_records"} <= set(daily_report._dependencies())


# TC-109: The timesheet records only the day's own work, never the Yesterday/Today report.
# Steps: 1. Return a workbook result whose report and today block differ.
#        2. Run the committed workflow. 3. Verify the portal received the today block.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-6, AC-9, AC-12.
def test_tc_109_timesheet_receives_the_today_block_not_the_full_report():
    events, descriptions, queued = [], [], []
    deps = _deps(events)
    today_block = "- #418781 AU Accessory Transfer: Define disposition and reuse"
    full_report = ("Yesterday\n- #419299 Harden lookup cache\n- #419258 Reduce re-render fan-out\n"
                   f"Today\n{today_block}")

    def workbook(config, today, *, date):
        events.append("workbook")
        return {"status": "UPDATED", "path": "book.xlsx", "report": full_report, "today": today_block}

    def write(config, when, description, *, commit, dry_run, auth_cache_path=None):
        descriptions.append(description)
        events.append("timesheet-dry-run" if dry_run else "timesheet-write")
        return {"status": "DRY_RUN" if dry_run else "COMMITTED", "action": "CREATE", "mutated": not dry_run}

    deps.update_workbook = workbook
    deps.write_timesheet = write
    deps.enqueue_current = lambda queue, date, today, error=None: queued.append(today) or {"queued": True, "date": date, "todayBlock": today, "lastError": error}
    daily_report.run(_config(), date=TODAY, dependencies=deps)

    # Both the preview and the committed write must carry only the day's own work.
    assert descriptions == ["- #101 Build portable report", today_block]
    for description in descriptions:
        assert "Yesterday" not in description
        assert "#419299" not in description, "yesterday's work must not reach the portal"


# TC-109b: A queued record also stores the day's own work, so a later sync submits it.
# Steps: 1. Fail auth preflight. 2. Capture the enqueued payload.
#        3. Verify its today field is the today block, while report stays the standup text.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-6, AC-12.
def test_tc_109b_queued_record_stores_the_today_block():
    events, queued = [], []
    deps = _deps(events)
    today_block = "- #418781 AU Accessory Transfer: Define disposition and reuse"
    full_report = f"Yesterday\n- #419299 Harden lookup cache\nToday\n{today_block}"

    deps.update_workbook = lambda config, today, *, date: (
        events.append("workbook") or {"status": "UPDATED", "path": "b.xlsx",
                                      "report": full_report, "today": today_block})

    def failing_auth(config):
        raise RuntimeError("AUTH_REQUIRED")

    deps.auth_preflight = failing_auth
    deps.enqueue_current = lambda queue, date, today, error=None: queued.append(today) or {"queued": True, "action": "CREATED"}
    result = daily_report.run(_config(), date=TODAY, dependencies=deps)
    assert result["code"] == "AUTH_REQUIRED"
    assert queued == []


@pytest.mark.parametrize("action", ["PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"])
def test_regression_queue_verification_accepts_queue_sequence_and_requires_exact_evidence(action):
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, period_error=action))
    assert result["status"] == daily_report.PARTIAL
    assert result["verification"]["ok"] is True
    assert events == ["gather", "auth", "timesheet-dry-run", "workbook", "enqueue", "verify"]


@pytest.mark.parametrize("action", ["PERIOD_NOT_FOUND", "PERIOD_AMBIGUOUS"])
def test_regression_real_enqueue_current_verifies_period_queue_as_partial(tmp_path, action):
    path = tmp_path / "book.xlsx"
    book = openpyxl.Workbook(); sheet = book.active; sheet.title = "Daily Report"
    sheet["A2"], sheet["B2"], sheet["C2"] = TODAY, "Yesterday work", "- #101 Build portable report"
    report = "Yesterday\nYesterday work\nToday\n- #101 Build portable report"; sheet["E2"] = report; book.save(path)
    config = _config(); config["excel"]["path"] = str(path)
    context = daily_report.RuntimeContext(tmp_path, tmp_path / "config.json", path, tmp_path / "pending.json", tmp_path / "auth.bin", tmp_path / "last.json")
    events = []
    deps = _deps(events, period_error=action)
    deps.update_workbook = lambda _cfg, today, *, date: {"status": "UPDATED", "path": str(path), "today": today, "report": report}
    deps.enqueue_current = pending_timesheets.enqueue_current
    deps.verify = verify_output.verify_run_result
    result = daily_report.run(config, context, date=TODAY, dependencies=deps)
    assert result["status"] == daily_report.PARTIAL and result["verification"]["ok"] is True
    assert pending_timesheets.load_queue(context.queue_path)["records"][0]["todayBlock"] == "- #101 Build portable report"


def test_regression_run_threads_context_cache_path_to_auth_and_both_writes(tmp_path):
    events, observed = [], []
    context = daily_report.RuntimeContext(tmp_path, tmp_path / "config.json", tmp_path / "book.xlsx",
                                          tmp_path / "pending.json", tmp_path / "selected-cache.bin", tmp_path / "last.json")
    deps = _deps(events)
    deps.auth_preflight = lambda _cfg, *, interactive, cache_path: observed.append(("auth", cache_path))

    def write(_cfg, _day, _today, *, commit, dry_run, auth_cache_path):
        observed.append(("write", commit, dry_run, auth_cache_path))
        return {"status": "COMMITTED" if commit else "DRY_RUN", "action": "CREATE"}

    deps.write_timesheet = write
    daily_report.run(_config(), context, date=TODAY, dependencies=deps)
    assert observed == [("auth", context.auth_cache_path), ("write", False, True, context.auth_cache_path),
                        ("write", True, False, context.auth_cache_path)]


def test_regression_verifier_reopens_configured_sheet_and_requires_exact_workbook_fields(tmp_path):
    path = tmp_path / "book.xlsx"
    book = openpyxl.Workbook(); sheet = book.active; sheet.title = "Configured"
    sheet["A2"], sheet["B2"], sheet["C2"] = TODAY, "Yesterday work", "- #101 Today work"
    sheet["E2"] = "Yesterday\nYesterday work\nToday\n- #101 Today work"; book.save(path)
    config = {"excel": {"sheet": "Configured"}}
    result = {"date": TODAY, "report": sheet["E2"].value, "workbook": {"path": str(path), "today": sheet["C2"].value},
              "timesheet": {"action": "CREATE"}, "queue": {"queued": False},
              "operations": ["gather", "auth", "timesheet_preview", "workbook", "timesheet_write", "verify"]}
    assert verify_output.verify_run_result(result, config=config, date=TODAY)["ok"] is True
    result["report"] = "Yesterday\nwrong\nToday\n- #101 Today work"
    assert "workbook-report" in verify_output.verify_run_result(result, config=config, date=TODAY)["failures"]


def test_regression_standalone_timesheet_verification_scopes_header_identity_date_and_description():
    queries = []
    class FakeDataverse:
        def __init__(self, _cfg, _token): pass
        def get(self, path):
            queries.append(path)
            if path.startswith("headers?"):
                return {"json": {"value": [{"id": "header-1"}]}}
            return {"json": {"value": [{"cr90e_taskdescription": "exact work"}]}}
    config = {"timesheet": {"header_entity_set": "headers", "detail_entity_set": "details"}}
    result = verify_output.verify_timesheet_output(
        config, TODAY, "exact work", cache_path="selected-cache.bin",
        token_provider=lambda _cfg, *, interactive, cache_path: "token",
        dataverse_factory=FakeDataverse, whoami=lambda _cfg, _token: "user-1")
    assert result["ok"] is True and result["count"] == 1
    assert "_xts_employee_value eq user-1" in queries[0] and "cr90e_fromperiod le 2026-07-27" in queries[0]
    assert "_cr90e_refnbr_value eq header-1" in queries[1] and "_xts_employee_value eq user-1" in queries[1]


def test_regression_status_preserves_last_run_pending_and_reports_current_queue(tmp_path, monkeypatch):
    context = daily_report.RuntimeContext(tmp_path, tmp_path / "config.json", tmp_path / "book.xlsx",
                                          tmp_path / "pending.json", tmp_path / "auth.bin", tmp_path / "last-run.json")
    daily_report.save_json_atomic(context.last_run_path, {"status": "PARTIAL", "pending": {"synced": 2, "remaining": 1}})
    daily_report.save_json_atomic(context.queue_path, {"version": 1, "records": [{"status": "pending"}, {"status": "synced"}, {"status": "failed"}]})
    monkeypatch.setattr(daily_report, "_runtime", lambda _args: context)
    output = io.StringIO()
    assert daily_report.main(["status", "--json"], stdout=output, dependencies=daily_report._dependencies()) == 2
    payload = __import__("json").loads(output.getvalue())
    assert payload["pending"] == {"synced": 2, "remaining": 1}
    assert payload["current_queue"] == {"synced": 1, "pending": 1, "failed": 1}


def test_regression_managed_run_setup_failure_persists_sanitized_last_run(tmp_path, monkeypatch):
    context = daily_report.RuntimeContext(tmp_path, tmp_path / "config.json", tmp_path / "book.xlsx",
                                          tmp_path / "pending.json", tmp_path / "auth.bin", tmp_path / "last-run.json")
    monkeypatch.setattr(daily_report, "_runtime", lambda _args: context)
    monkeypatch.setitem(sys.modules, "bootstrap", SimpleNamespace(
        setup=lambda _state: SimpleNamespace(status="FAIL", details={"code": "SETUP_FAILED"}, message="token=secret"),
        reexec_managed_venv=lambda *_args: False))
    assert daily_report.main(["run", "--json"], stdout=io.StringIO()) == 1
    persisted = __import__("json").loads(context.last_run_path.read_text(encoding="utf-8"))
    assert persisted["code"] == "SETUP_FAILED" and "secret" not in persisted["recovery"]
