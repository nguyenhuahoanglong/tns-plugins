import io
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import daily_report
from lib_common import resolve_runtime_context
from bootstrap import BootstrapResult, reexec_managed_venv


def test_runtime_context_defaults_to_portable_home_and_cli_override(tmp_path):
    context = resolve_runtime_context(home=tmp_path, env={})
    assert context.state_dir == tmp_path / ".ai" / "data" / "daily-report"
    overridden = resolve_runtime_context(home=tmp_path, env={"DAILY_REPORT_HOME": str(tmp_path / "state")})
    assert overridden.state_dir == tmp_path / "state"


@pytest.mark.parametrize("command", ["setup", "doctor", "auth", "run", "status", "pending"])
def test_every_public_command_has_help(command):
    with pytest.raises(SystemExit) as raised:
        daily_report.build_parser().parse_args([command, "--help"])
    assert raised.value.code == 0


def test_review_only_missing_runtime_is_non_mutating_setup_required(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILY_REPORT_HOME", str(tmp_path / "missing"))
    output = io.StringIO()
    assert daily_report.main(["run", "--review-only", "--json"], stdout=output) == 2
    payload = json.loads(output.getvalue())
    assert payload["code"] == "SETUP_REQUIRED"
    assert not (tmp_path / "missing").exists()


def test_status_is_read_only_and_preserves_sanitized_result(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    (state / "last-run.json").write_text(json.dumps({"status": "SUCCESS", "code": "COMPLETED"}), encoding="utf-8")
    monkeypatch.setenv("DAILY_REPORT_HOME", str(state))
    output = io.StringIO()
    assert daily_report.main(["status", "--json"], stdout=output) == 0
    assert json.loads(output.getvalue())["read_only"] is True


def test_status_without_history_returns_exact_runnable_command(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "daily-report.config.json").write_text("{}", encoding="utf-8")
    (state / ".venv").mkdir()
    (state / ".requirements.sha256").write_text("hash\n", encoding="ascii")
    monkeypatch.setenv("DAILY_REPORT_HOME", str(state))
    output = io.StringIO()

    assert daily_report.main(["status", "--json"], stdout=output) == 2

    payload = json.loads(output.getvalue())
    command = payload["next_action"]
    assert str(Path(daily_report.__file__).resolve()) in command
    assert str(state) in command
    assert " run --config " in command
    assert payload["recovery"] == command


def test_pending_accepts_explicit_config_for_resolved_context():
    arguments = daily_report.build_parser().parse_args(
        ["pending", "--config", "selected.json", "--json"]
    )
    assert arguments.config == "selected.json"


def test_human_result_always_reports_operational_status_and_next_action():
    result = daily_report._result(
        daily_report.SUCCESS,
        "COMPLETED",
        steps=[
            {"name": "gather", "status": "PASS", "count": 1, "task_ids": ["101"]},
            {"name": "workbook", "status": "PASS", "action": "UPDATED", "verified": True},
            {"name": "timesheet_write", "status": "PASS", "action": "CREATE"},
            {
                "name": "verify",
                "status": "PASS",
                "workbook_passed": 8,
                "workbook_total": 8,
                "live_passed": 1,
                "live_total": 1,
            },
            {"name": "pending", "status": "PASS"},
        ],
        pending={"synced": 0, "failed": 0, "remaining": 0},
    )
    output = io.StringIO()

    daily_report._emit(result, False, output)

    rendered = output.getvalue()
    assert "Overall: SUCCESS\nCode: COMPLETED" in rendered
    assert "ADO: PASS — gathered 1 task(s): #101" in rendered
    assert "Workbook: PASS — UPDATED; reopened and verified" in rendered
    assert "Timesheet: PASS — CREATE" in rendered
    assert "Verification: PASS — workbook checks 8/8; live checks 1/1" in rendered
    assert "Pending: PASS — synced=0 failed=0 remaining=0" in rendered
    assert "Warnings: None" in rendered
    assert "Next action: None" in rendered


def test_formatted_task_bullets_never_render_mapping_repr():
    report = daily_report._report([{"id": 12, "title": "Review changes"}, "Planning"])
    assert report.endswith("- #12 Review changes\n- Planning")


def test_last_run_sanitizer_redacts_nested_credentials():
    result = daily_report._sanitize({"token": "top", "nested": {"authorization": "Bearer secret", "safe": "ok"}})
    assert result == {"token": "[REDACTED]", "nested": {"authorization": "[REDACTED]", "safe": "ok"}}


def test_review_report_reads_yesterday_without_mutating_workbook(tmp_path):
    import openpyxl
    book = tmp_path / "DailyTask.xlsx"; workbook = openpyxl.Workbook(); sheet = workbook.active; sheet.title = "Daily Report"; sheet["C2"] = "- Yesterday work"; workbook.save(book)
    config = {"excel": {"path": str(book), "sheet": "Daily Report"}}
    before = book.read_bytes()
    assert "Yesterday work" in daily_report._review_report(config, ["Today work"])
    assert book.read_bytes() == before


def test_review_only_with_config_but_without_managed_runtime_is_non_mutating(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    config = state / "daily-report.config.json"; config.write_text('{"excel": {}}', encoding="utf-8")
    before = config.read_bytes()
    monkeypatch.setenv("DAILY_REPORT_HOME", str(state))
    output = io.StringIO()
    assert daily_report.main(["run", "--review-only", "--json"], stdout=output) == 2
    assert json.loads(output.getvalue())["code"] == "SETUP_REQUIRED"
    assert config.read_bytes() == before and not (state / ".venv").exists()


def test_managed_venv_reexec_passes_the_original_command_once(tmp_path):
    venv = tmp_path / ".venv"
    executable = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    calls = []
    assert reexec_managed_venv(venv, ["daily_report.py", "doctor"], current_python=tmp_path / "host.exe", executor=lambda target, argv: calls.append((target, argv)))
    assert calls == [(str(executable), [str(executable), "daily_report.py", "doctor"])]


def test_managed_venv_reexec_does_not_loop_when_already_managed(tmp_path):
    venv = tmp_path / ".venv"
    executable = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    assert not reexec_managed_venv(venv, ["daily_report.py", "auth"], current_python=executable, executor=lambda *_: pytest.fail("must not re-exec"))


def test_run_setup_failure_stops_before_reexec(tmp_path, monkeypatch):
    import bootstrap
    state = tmp_path / "state"; monkeypatch.setenv("DAILY_REPORT_HOME", str(state))
    monkeypatch.setattr(bootstrap, "setup", lambda *_args, **_kwargs: BootstrapResult("FAIL", "setup failed", {"code": "DEPENDENCY_INSTALL_FAILED"}, 1))
    monkeypatch.setattr(bootstrap, "reexec_managed_venv", lambda *_args, **_kwargs: pytest.fail("must not re-exec"))
    output = io.StringIO()
    assert daily_report.main(["run", "--json"], stdout=output) == 1
    assert json.loads(output.getvalue())["code"] == "DEPENDENCY_INSTALL_FAILED"
