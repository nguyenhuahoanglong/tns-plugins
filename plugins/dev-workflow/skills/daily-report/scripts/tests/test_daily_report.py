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

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import daily_report  # noqa: E402
import verify_output  # noqa: E402


TODAY = dt.date(2026, 7, 27)


def _config():
    return {
        "excel": {"path": "C:/offline/daily.xlsx", "sheet": "Daily Report"},
        "backup": {"enabled": False},
        "timesheet": {"org_url": "https://offline.example"},
    }


def _deps(events, *, tasks=None, verify_ok=True, auth_error=None, period_error=None,
          old_pending_error=None):
    """Minimal public seam expected from daily_report.run/main."""
    tasks = [{"id": 101, "title": "Build portable report"}] if tasks is None else tasks

    def record(name, value=None):
        events.append(name)
        return value

    def gather(config):
        record("gather")
        return list(tasks)

    def merge(gathered, additions):
        record("merge")
        return list(gathered) + list(additions)

    def update(config, items, when):
        record("workbook")
        return {"workbook": config["excel"]["path"], "report": "Yesterday\nDone\nToday\n- #101 Build portable report"}

    def auth(config):
        record("auth")
        if auth_error:
            raise auth_error
        return {"identity": "offline-user"}

    def write(config, when, description, *, commit, dry_run):
        record("timesheet-dry-run" if dry_run else "timesheet-write")
        if period_error:
            raise period_error
        return {"action": "CREATE", "dry_run": dry_run, "description": description}

    def enqueue(config, payload, error=None):
        record("enqueue")
        return {"queued": True, "error": str(error) if error else None}

    def verify(result):
        record("verify")
        return {"ok": verify_ok, "checks": ["portable-path", "workbook", "report", "timesheet", "order"]}

    def backup(config, workbook):
        record("backup")
        return {"backed_up": True}

    def sync(config):
        record("sync-old-pending")
        if old_pending_error:
            raise old_pending_error
        return {"synced": 1}

    def prune(config):
        record("prune-old-pending")
        return {"pruned": 1}

    return SimpleNamespace(
        bootstrap=lambda config: record("bootstrap", {"ok": True}),
        doctor=lambda config: record("doctor", {"ok": True}),
        gather_tasks=gather,
        merge_additions=merge,
        update_workbook=update,
        auth_preflight=auth,
        write_timesheet=write,
        enqueue_current=enqueue,
        verify=verify,
        backup_workbook=backup,
        sync_old_pending=sync,
        prune_old_pending=prune,
    )


# TC-080: Exact happy-path mutation sequence is observable without live services.
# Steps: 1. Supply offline callbacks. 2. Run with an addition. 3. Verify exact operation order and result.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9 through AC-13.
def test_tc_080_runs_exact_portable_happy_path_order_with_injected_fakes():
    events = []
    result = daily_report.run(_config(), date=TODAY, additions=["- Planning"], dependencies=_deps(events))
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"]
    assert result["ok"] is True
    assert result["operations"] == events
    assert result["report"].startswith("Yesterday\n")


# TC-081: Review mode stops before workbook, auth, queue, backup, or remote mutation.
# Steps: 1. Run review-only with offline callbacks. 2. Read result. 3. Verify only read/merge stages ran.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_081_review_only_escape_hatch_stops_before_all_mutations():
    events = []
    result = daily_report.run(_config(), date=TODAY, review_only=True, dependencies=_deps(events))
    assert events == ["bootstrap", "gather", "merge"]
    assert result == {"ok": True, "review_only": True, "operations": events, "tasks": [{"id": 101, "title": "Build portable report"}]}


# TC-082: Auth failure queues current work and never starts stale retries.
# Steps: 1. Make auth preflight fail. 2. Run offline workflow. 3. Verify current queue precedes and blocks old pending.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-7, AC-10, AC-12.
def test_tc_082_auth_required_queues_current_and_blocks_old_pending_work():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, auth_error=RuntimeError("AUTH_REQUIRED")))
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "enqueue"]
    assert result["ok"] is False
    assert result["timesheet"]["queued"] is True
    assert "sync-old-pending" not in events


# TC-083: Empty gathered work produces safe no-task result without workbook or timesheet work.
# Steps: 1. Return zero tasks. 2. Run workflow. 3. Verify no write path begins.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_083_no_task_path_returns_actionable_stop_without_mutation():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, tasks=[]))
    assert events == ["bootstrap", "gather", "merge"]
    assert result["ok"] is False
    assert result["code"] == "NO_TASKS"


# TC-084: Locked workbook is an explicit stop before auth/write/queue/retry.
# Steps: 1. Make workbook callback raise lock error. 2. Run workflow. 3. Verify later callbacks never run.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_084_workbook_lock_stops_before_auth_or_timesheet_work():
    events = []
    deps = _deps(events)
    def locked(*_args):
        events.append("workbook")
        raise RuntimeError("WORKBOOK_LOCKED")
    deps.update_workbook = locked
    result = daily_report.run(_config(), date=TODAY, dependencies=deps)
    assert events == ["bootstrap", "gather", "merge", "workbook"]
    assert result["code"] == "WORKBOOK_LOCKED"


@pytest.mark.parametrize("marker", ["NO_ACTIVE_PERIOD", "AMBIGUOUS_PERIOD"])
def test_tc_085_086_period_stops_queue_current_then_block_old_pending(marker):
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, period_error=RuntimeError(marker)))
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "enqueue"]
    assert result["code"] == marker
    assert "sync-old-pending" not in events


# TC-087: Verification failure blocks both backup and stale queue synchronization.
# Steps: 1. Return a failed portable verifier result. 2. Run workflow. 3. Verify backup/sync/prune did not run.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_087_verification_failure_blocks_backup_and_pending_sync():
    events = []
    result = daily_report.run(_config(), date=TODAY, backup=True, dependencies=_deps(events, verify_ok=False))
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify"]
    assert result["code"] == "VERIFY_FAILED"


# TC-088: Explicit optional backup follows verification and precedes old queue work.
# Steps: 1. Enable backup. 2. Run success path. 3. Verify backup only appears in approved slot.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_088_optional_backup_runs_only_after_verify_and_before_old_pending_sync():
    events = []
    result = daily_report.run(_config(), date=TODAY, backup=True, dependencies=_deps(events))
    assert result["ok"] is True
    assert events.index("verify") < events.index("backup") < events.index("sync-old-pending") < events.index("prune-old-pending")


# TC-089: Stale retry failure remains isolated after current report success.
# Steps: 1. Let current report complete. 2. Fail stale sync. 3. Verify current result/report remains intact.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-10, AC-12.
def test_tc_089_old_pending_failure_happens_after_current_success_and_preserves_report():
    events = []
    result = daily_report.run(_config(), date=TODAY, dependencies=_deps(events, old_pending_error=RuntimeError("OLD_PENDING_FAILED")))
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify", "sync-old-pending"]
    assert result["current"]["ok"] is True
    assert result["report"].endswith("Build portable report")
    assert result["old_pending"]["ok"] is False


# TC-090: CLI exposes setup, doctor, run, and pending without module-global patching.
# Steps: 1. Call each command with injected fakes. 2. Read exit/result. 3. Verify correct command callback.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
@pytest.mark.parametrize("argv, expected", [(["setup"], "bootstrap"), (["doctor"], "doctor"), (["pending"], "sync-old-pending")])
def test_tc_090_cli_commands_use_injected_dependencies(argv, expected):
    events = []
    output = io.StringIO()
    exit_code = daily_report.main(argv, config_loader=lambda _path=None: _config(), dependencies=_deps(events), stdout=output)
    assert exit_code == 0
    assert events == [expected]


# TC-091: CLI emits structured status before one final copy-ready report boundary.
# Steps: 1. Run success command with fake output sink. 2. Split status/report marker. 3. Verify report is final text.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_091_successful_cli_output_ends_with_copy_ready_report_after_status_boundary():
    events = []
    output = io.StringIO()
    assert daily_report.main(["run", "--date", TODAY.isoformat()], config_loader=lambda _path=None: _config(), dependencies=_deps(events), stdout=output) == 0
    text = output.getvalue()
    assert "=== daily-report status ===" in text
    assert "=== copy-ready report ===\n" in text
    assert text.rstrip().endswith("- #101 Build portable report")


# TC-092: Portable verifier validates all orchestrator evidence, not legacy live auth.
# Steps: 1. Supply complete offline result. 2. Verify artifacts. 3. Verify portable checks all pass.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12, AC-13.
def test_tc_092_verifier_validates_portable_paths_workbook_report_queue_and_order():
    result = {
        "ok": True, "report": "Yesterday\nDone\nToday\n- #101 Build portable report",
        "workbook": {"path": "C:/offline/daily.xlsx", "updated": True},
        "timesheet": {"action": "CREATE", "dry_run": False}, "queue": {"queued": False},
        "operations": ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "timesheet-write", "verify", "sync-old-pending", "prune-old-pending"],
    }
    verdict = verify_output.verify_run_result(result)
    assert verdict["ok"] is True
    assert {"portable-path", "workbook", "report", "timesheet-or-queue", "operation-order"} <= set(verdict["checks"])


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
    assert verdict["ok"] is True


# TC-100: Default dependency wiring calls gather_tasks.gather, not a stale symbol.
# Steps: 1. Inject a local gather_tasks module. 2. Build default dependencies. 3. Invoke gather boundary.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_100_default_dependencies_imports_and_calls_existing_gather_function(monkeypatch):
    calls = []
    module = SimpleNamespace(gather=lambda config: calls.append(config) or ["task"])
    monkeypatch.setitem(sys.modules, "gather_tasks", module)
    factory = getattr(daily_report, "_default_dependencies", None)
    assert callable(factory), "daily_report must expose _default_dependencies for portable production wiring."
    deps = factory()
    assert deps.gather_tasks({"ado": {}}) == ["task"]
    assert calls == [{"ado": {}}]


# TC-101: Setup uses state path before config and forwards explicit migration inputs.
# Steps: 1. Make config loader fail if called. 2. Run setup with injected state/dependency seams. 3. Verify forwarded options.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-6, AC-12.
def test_tc_101_setup_bootstraps_from_portable_state_before_config_loading():
    calls = []
    deps = _deps(calls)
    deps.bootstrap = lambda state_dir, **options: calls.append((state_dir, options)) or {"status": "PASS"}
    config_loader = lambda *_args: pytest.fail("setup must not load config before bootstrap")
    state_resolver = lambda: {"state_dir": "C:/offline/state"}

    exit_code = daily_report.main(
        ["setup", "--import-config", "legacy.json", "--import-workbook", "legacy.xlsx", "--replace"],
        config_loader=config_loader, dependencies=deps, state_resolver=state_resolver,
    )
    assert exit_code == 0
    assert calls == [("C:/offline/state", {
        "import_config": "legacy.json", "import_workbook": "legacy.xlsx", "replace": True,
    })]


# TC-102: Review-only returns a merged copy-ready report preview with zero mutation.
# Steps: 1. Supply offline render/read callbacks. 2. Run review-only. 3. Verify preview and no write/auth/queue calls.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_102_review_only_returns_merged_copy_ready_preview_without_mutation():
    events = []
    deps = _deps(events)
    deps.render_report = lambda items: "Yesterday\nDone\nToday\n" + "\n".join(items)
    result = daily_report.run(_config(), date=TODAY, additions=["- Planning"], review_only=True, dependencies=deps)
    assert events == ["bootstrap", "gather", "merge"]
    assert result["report"] == "Yesterday\nDone\nToday\n{'id': 101, 'title': 'Build portable report'}\n- Planning"
    assert result["tasks"][-1] == "- Planning"


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
    assert events == ["bootstrap", "gather", "merge", "workbook", "auth", "timesheet-dry-run", "enqueue"]
    assert result["code"] == action
    assert result["report"].startswith("Yesterday\n")
    assert result["queue"]["queued"] is True


# TC-104: Successful output has one fenced text report block after structured status and ends at its closing fence.
# Steps: 1. Run successful CLI offline. 2. Inspect output boundaries. 3. Verify final copy-ready fenced report only.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-9, AC-12.
def test_tc_104_successful_cli_output_uses_one_final_fenced_text_report_block():
    events, output = [], io.StringIO()
    assert daily_report.main(["run"], config_loader=lambda *_args: _config(), dependencies=_deps(events), stdout=output) == 0
    text = output.getvalue()
    assert text.index("=== daily-report status ===") < text.index("```text\n")
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

    def workbook(config, items, when):
        received.append(daily_report._today_block(items))
        events.append("workbook")
        return {"status": "UPDATED", "report": received[-1], "path": "book.xlsx"}

    deps.update_workbook = workbook

    daily_report.main(["run", "--add", "reviewed the migration"],
                      config_loader=lambda *_a: _config(), dependencies=deps, stdout=io.StringIO())

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
def test_tc_107_doctor_diagnoses_before_config_loading(tmp_path):
    events, received = [], []
    deps = _deps(events)
    deps.doctor = lambda config: received.append(config) or events.append("doctor")
    config_loader = lambda *_args: pytest.fail("doctor must not load config before diagnosing")
    config_path = tmp_path / "daily-report.config.json"

    assert daily_report.main(
        ["doctor"], config_loader=config_loader, dependencies=deps,
        state_resolver=lambda: {"state_dir": tmp_path, "config_path": config_path},
    ) == 0

    # Diagnostics run without loading config, but still receive the path so an existing
    # config is validated; a missing file is reported as "not initialized".
    assert events == ["doctor"]
    assert received == [config_path]


# TC-107b: An explicit --config path reaches doctor unchanged and is still not loaded.
# Steps: 1. Pass --config. 2. Run doctor with a failing loader. 3. Verify the path passes through.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_107b_doctor_forwards_explicit_config_path_without_loading_it():
    events, received = [], []
    deps = _deps(events)
    deps.doctor = lambda config: received.append(config) or events.append("doctor")
    config_loader = lambda *_args: pytest.fail("doctor must not load config before diagnosing")

    assert daily_report.main(
        ["doctor", "--config", "explicit.json"], config_loader=config_loader, dependencies=deps,
        state_resolver=lambda: pytest.fail("an explicit --config must not need state resolution"),
    ) == 0
    assert received == ["explicit.json"]


# TC-108: Config-bound commands still refuse to work before config exists.
# Steps: 1. Make the config loader stop like the real loader. 2. Run each config-bound command. 3. Verify the stop propagates unchanged.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
@pytest.mark.parametrize("argv", (["run"], ["pending"]))
def test_tc_108_run_and_pending_still_require_config(argv):
    events = []

    def missing_config(*_args):
        raise SystemExit("ERROR: config not found")

    with pytest.raises(SystemExit):
        daily_report.main(argv, config_loader=missing_config, dependencies=_deps(events), stdout=io.StringIO())
    assert events == []


# TC-109: Default doctor wiring emits its checks instead of discarding a silent result.
# Steps: 1. Inject a local doctor module. 2. Build default dependencies. 3. Invoke the doctor boundary with no config.
# Design: portable-git-daily-report-dev-workflow.md Task 13, AC-5, AC-9, AC-12.
def test_tc_109_default_dependencies_emit_doctor_checks_without_config(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "doctor", SimpleNamespace(main=lambda argv: calls.append(argv) or 0))
    daily_report._default_dependencies().doctor(None)
    assert calls == [[]]
