"""Offline contracts for Task 9 portable first-run setup and diagnostics.

Test registry: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Subject: bootstrap.py and doctor.py
Design: .plans/portable-git-daily-report-dev-workflow.md (Task 9; AC-5,
AC-6, AC-7, AC-11, AC-12).

TC-032 through TC-036 characterize the intentionally inert scaffold.  The
remaining tests are spec-first and must stay RED until Task 9 implementation
adds the documented injected-boundary contracts.  No test installs packages,
authenticates, invokes Azure CLI, or changes system Python.
"""
from __future__ import annotations

import inspect
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import openpyxl


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import bootstrap  # noqa: E402
import doctor  # noqa: E402
import pending_timesheets as pending  # noqa: E402


def _result_dict(result):
    return result.to_dict() if hasattr(result, "to_dict") else result


def _setup_contract():
    setup = getattr(bootstrap, "setup", None)
    assert callable(setup), "Task 9 must expose bootstrap.setup as the injected first-run orchestration boundary."
    _require_parameters(
        setup,
        "resolve_runtime", "ensure_environment", "install_dependencies", "path_exists", "initialize", "copy_file",
    )
    return setup


def _require_parameters(function, *names):
    parameters = inspect.signature(function).parameters
    missing = [name for name in names if name not in parameters]
    assert not missing, f"Task 9 must inject external boundaries: {', '.join(missing)}."


def _offline_setup_boundaries(**overrides):
    """Supply every setup boundary so tests cannot install, create a venv, or authenticate."""
    boundaries = {
        "resolve_runtime": lambda: {"status": "PASS"},
        "ensure_environment": lambda: {"status": "PASS"},
        "install_dependencies": lambda: 0,
        "path_exists": lambda _path: False,
        "initialize": lambda *_args: None,
        "copy_file": lambda *_args: None,
    }
    boundaries.update(overrides)
    return boundaries


# TC-032: Both CLI entrypoints remain usable from an unrelated caller directory.
# Steps:
#   1. Set an isolated DAILY_REPORT_HOME and change to an unrelated directory.
#   2. Run bootstrap.py --help and doctor.py --help using their absolute paths.
#   3. Verify help succeeds without creating local state.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-12.
def test_tc_032_scaffold_help_works_from_unrelated_cwd_without_creating_state(tmp_path):
    unrelated_cwd = tmp_path / "unrelated"
    unrelated_cwd.mkdir()
    state_home = tmp_path / "daily-home"
    environment = {**os.environ, "DAILY_REPORT_HOME": str(state_home)}

    for script in ("bootstrap.py", "doctor.py"):
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS_DIR / script), "--help"],
            cwd=unrelated_cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert "usage:" in completed.stdout.lower()

    assert not state_home.exists()


# TC-033: Bootstrap parser accepts portable explicit setup inputs without side effects.
# Steps:
#   1. Build the bootstrap parser without invoking setup.
#   2. Parse explicit import/replace inputs.
#   3. Verify parser routing is independent of the caller state directory.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-12.
def test_tc_033_bootstrap_parser_accepts_explicit_setup_inputs_without_side_effects():
    arguments = bootstrap.build_parser().parse_args(
        ["setup", "--python", "python311", "--import-config", "legacy.json", "--import-workbook", "legacy.xlsx", "--replace"]
    )

    assert arguments.command == "setup"
    assert arguments.python == "python311"
    assert arguments.import_config == "legacy.json"
    assert arguments.import_workbook == "legacy.xlsx"
    assert arguments.replace is True


# TC-034: Doctor parser accepts read-only diagnostic inputs without side effects.
# Steps:
#   1. Build the doctor parser without running diagnostics.
#   2. Parse config and verbose inputs.
#   3. Verify parsing does not require state or authentication.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_034_doctor_parser_accepts_read_only_inputs_without_side_effects():
    arguments = doctor.build_parser().parse_args(["--config", "daily-report.config.json", "--verbose"])

    assert arguments.config == "daily-report.config.json"
    assert arguments.verbose is True


# TC-035: Bootstrap runtime signature retains an optional explicit Python input.
# Steps:
#   1. Inspect the public resolver signature without probing Python.
#   2. Identify its requested-runtime input.
#   3. Verify the portable CLI retains a testable resolution seam.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_035_bootstrap_exposes_a_testable_python_resolution_seam():
    parameters = inspect.signature(bootstrap.resolve_python).parameters

    assert "python" in parameters
    assert parameters["python"].default is None


# TC-036: Scaffold modules remain syntax-valid before behavior implementation.
# Steps:
#   1. Compile bootstrap.py and doctor.py without writing bytecode.
#   2. Inspect the compiler result.
#   3. Verify both modules are compile-ready.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-12.
def test_tc_036_scaffold_modules_are_importable_and_compile_ready():
    assert callable(bootstrap.main)
    assert callable(doctor.main)


# TC-037: Resolve only a supported explicit/runtime Python using injected discovery.
# Steps:
#   1. Provide fake interpreter existence and version readers.
#   2. Resolve a Python 3.11 interpreter and an unsupported Python 3.10 interpreter.
#   3. Verify the supported executable is selected and unsupported Python is a structured failure.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_037_resolves_supported_python_without_running_system_python(tmp_path):
    _require_parameters(bootstrap.resolve_python, "executable_exists", "version_reader")
    executable = tmp_path / "python311"

    supported = bootstrap.resolve_python(
        executable,
        executable_exists=lambda candidate: Path(candidate) == executable,
        version_reader=lambda _candidate: (3, 11, 14),
    )
    unsupported = bootstrap.resolve_python(
        executable,
        executable_exists=lambda _candidate: True,
        version_reader=lambda _candidate: (3, 10, 18),
    )

    assert _result_dict(supported)["status"] == "PASS"
    assert _result_dict(supported)["details"]["python"] == str(executable)
    assert _result_dict(unsupported)["status"] == "FAIL"


# TC-038: Create an isolated virtual environment once and reuse it thereafter.
# Steps:
#   1. Provide fake filesystem and venv-creation boundaries.
#   2. Ensure the same environment twice.
#   3. Verify creation occurs once and the system interpreter is never a target.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_038_creates_and_reuses_isolated_venv_only(tmp_path):
    _require_parameters(bootstrap.ensure_venv, "python", "path_exists", "venv_creator")
    venv_path = tmp_path / ".venv"
    created = []
    existing = set()

    def create(python, destination):
        created.append((Path(python), Path(destination)))
        existing.add(Path(destination))

    first = bootstrap.ensure_venv(
        venv_path, python=tmp_path / "python311", path_exists=lambda path: Path(path) in existing,
        venv_creator=create,
    )
    second = bootstrap.ensure_venv(
        venv_path, python=tmp_path / "python311", path_exists=lambda path: Path(path) in existing,
        venv_creator=create,
    )

    assert _result_dict(first)["status"] == "PASS"
    assert _result_dict(second)["status"] == "PASS"
    assert created == [(tmp_path / "python311", venv_path)]


# TC-039: Install requirements with the venv interpreter only.
# Steps:
#   1. Supply a fake command runner and a venv Python path.
#   2. Request dependency installation for the packaged requirements file.
#   3. Verify the runner receives a venv-local argv array and never system Python.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_039_installs_requirements_inside_venv_only(tmp_path):
    installer = getattr(bootstrap, "install_requirements", None)
    assert callable(installer), "Task 9 must expose bootstrap.install_requirements."
    _require_parameters(installer, "runner")
    venv_python = tmp_path / ".venv" / "bin" / "python"
    requirements = SCRIPTS_DIR / "requirements.txt"
    commands = []

    result = installer(venv_python, requirements, runner=lambda argv: commands.append(argv) or 0)

    assert _result_dict(result)["status"] == "PASS"
    assert commands == [[str(venv_python), "-m", "pip", "install", "--requirement", str(requirements)]]
    assert all(command[0] != sys.executable for command in commands)


def test_tc_039b_default_installer_captures_pip_output(tmp_path, monkeypatch, capsys):
    venv_python = tmp_path / ".venv" / "bin" / "python"
    requirements = SCRIPTS_DIR / "requirements.txt"
    calls = []

    class Completed:
        returncode = 0
        stdout = "pip progress must stay private"
        stderr = ""

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)

    result = bootstrap.install_requirements(venv_python, requirements)

    assert _result_dict(result)["status"] == "PASS"
    assert capsys.readouterr().out == ""
    assert calls[0][1]["capture_output"] is True
    assert calls[0][1]["text"] is True


# TC-040: Initialize missing config, workbook, and queue without external services.
# Steps:
#   1. Provide an empty state directory and fake local file creators.
#   2. Initialize state.
#   3. Verify all three artifacts are created from local inputs only.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-11.
def test_tc_040_initializes_config_workbook_and_queue_on_empty_first_run(tmp_path):
    _require_parameters(bootstrap.initialize_state, "template_path", "workbook_creator", "json_writer")
    state_dir = tmp_path / "daily-home"
    writes = []
    result = bootstrap.initialize_state(
        state_dir,
        template_path=SCRIPTS_DIR.parent / "assets" / "config-template.json",
        workbook_creator=lambda path: writes.append(("workbook", Path(path))),
        json_writer=lambda path, payload: writes.append(("json", Path(path), payload)),
        platform_name="posix",
    )

    assert _result_dict(result)["status"] == "PASS"
    assert {entry[0] for entry in writes} == {"workbook", "json"}
    assert any(entry[1].name == "daily-report.config.json" for entry in writes)
    assert any(entry[1].name == "pending-timesheets.json" for entry in writes)


# TC-041: A repeated setup is a no-op and never overwrites existing local artifacts.
# Steps:
#   1. Mark config, workbook, and queue as existing with distinctive content.
#   2. Run injected setup without replacement input.
#   3. Verify PASS/no-op and no write boundary invocation.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-12.
def test_tc_041_repeated_setup_is_noop_and_preserves_existing_state(tmp_path):
    setup = _setup_contract()
    state_dir = tmp_path / "daily-home"
    writes = []

    result = setup(
        state_dir,
        **_offline_setup_boundaries(
            path_exists=lambda _path: True,
            initialize=lambda *_args: writes.append(True),
        ),
    )

    assert _result_dict(result)["status"] == "PASS"
    assert _result_dict(result)["details"]["changed"] is False
    assert writes == []


# TC-042: Recover only missing local artifacts while preserving existing artifacts.
# Steps:
#   1. Simulate an existing config and queue with a missing workbook.
#   2. Run injected setup.
#   3. Verify only the workbook recovery boundary is called.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-11.
def test_tc_042_recovers_partial_state_without_overwriting_existing_files(tmp_path):
    setup = _setup_contract()
    calls = []

    result = setup(
        tmp_path / "daily-home",
        **_offline_setup_boundaries(
            path_exists=lambda path: Path(path).name != "DailyTask.xlsx",
            initialize=lambda missing: calls.append(Path(missing).name),
        ),
    )

    assert _result_dict(result)["status"] == "PASS"
    assert calls == ["DailyTask.xlsx"]


# TC-043: Dependency installation failure is structured and leaves user state untouched.
# Steps:
#   1. Inject a requirements installer that returns a nonzero result.
#   2. Run setup against an empty temporary home.
#   3. Verify FAIL and no config/workbook/queue initialization.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_043_reports_dependency_install_failure_without_initializing_state(tmp_path):
    setup = _setup_contract()
    initialized = []

    result = setup(
        tmp_path / "daily-home",
        **_offline_setup_boundaries(
            install_dependencies=lambda: 1,
            initialize=lambda *_args: initialized.append(True),
        ),
    )

    assert _result_dict(result)["status"] == "FAIL"
    assert _result_dict(result)["details"]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert initialized == []


# TC-044: A locked workbook produces actionable recovery without overwrite.
# Steps:
#   1. Inject a workbook creator that raises a lock error.
#   2. Initialize local state.
#   3. Verify a structured lock result and preserved config/queue boundaries.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-11, AC-12.
def test_tc_044_reports_locked_workbook_without_overwrite(tmp_path):
    _require_parameters(bootstrap.initialize_state, "workbook_creator", "json_writer")

    result = bootstrap.initialize_state(
        tmp_path / "daily-home",
        template_path=SCRIPTS_DIR.parent / "assets" / "config-template.json",
        workbook_creator=lambda _path: (_ for _ in ()).throw(PermissionError("locked")),
        json_writer=lambda *_args: None,
    )

    assert _result_dict(result)["status"] == "FAIL"
    assert _result_dict(result)["details"]["code"] == "WORKBOOK_LOCKED"


# TC-045: Legacy config/workbook data moves only through explicit copy inputs.
# Steps:
#   1. Provide distinguishable legacy sources and an injected copy boundary.
#   2. Run setup once without imports and once with explicit imports.
#   3. Verify no implicit copy, then exactly the requested copies without source deletion.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-12.
def test_tc_045_copies_legacy_data_only_when_explicitly_requested(tmp_path):
    setup = _setup_contract()
    _require_parameters(setup, "import_config", "import_workbook")
    copied = []
    legacy_config = tmp_path / "legacy-config.json"
    legacy_workbook = tmp_path / "legacy.xlsx"

    setup(
        tmp_path / "clean-home",
        **_offline_setup_boundaries(
            path_exists=lambda _path: True,
            copy_file=lambda *_args: copied.append(_args),
        ),
    )
    assert copied == []

    result = setup(
        tmp_path / "import-home",
        import_config=legacy_config,
        import_workbook=legacy_workbook,
        **_offline_setup_boundaries(
            path_exists=lambda _path: True,
            copy_file=lambda source, destination: copied.append((Path(source), Path(destination))),
        ),
    )

    assert _result_dict(result)["status"] == "PASS"
    assert [source for source, _destination in copied] == [legacy_config, legacy_workbook]
    assert all(source in (legacy_config, legacy_workbook) for source, _destination in copied)


# TC-046: New JSON state receives owner-only POSIX permissions through an injected boundary.
# Steps:
#   1. Simulate POSIX permission tightening for generated config and queue files.
#   2. Initialize state with injected local writers.
#   3. Verify mode 0600 is requested without probing host permissions.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-12.
def test_tc_046_tightens_generated_state_permissions_on_posix(tmp_path):
    _require_parameters(bootstrap.initialize_state, "permission_setter", "platform_name")
    permissions = []

    bootstrap.initialize_state(
        tmp_path / "daily-home", template_path=SCRIPTS_DIR.parent / "assets" / "config-template.json",
        workbook_creator=lambda _path: None, json_writer=lambda *_args: None,
        platform_name="Linux", permission_setter=lambda path, mode: permissions.append((Path(path), mode)),
    )

    assert {path.name for path, mode in permissions if mode == stat.S_IRUSR | stat.S_IWUSR} >= {
        "daily-report.config.json", "pending-timesheets.json"
    }


# TC-047: Doctor returns a structured offline matrix across every prerequisite boundary.
# Steps:
#   1. Inject Python/Azure CLI/cache/config/workbook/service outcomes.
#   2. Run read-only diagnostics.
#   3. Verify PASS, WARN, and FAIL entries with no real command, auth, or service call.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-7, AC-11, AC-12.
def test_tc_047_doctor_reports_structured_pass_warn_fail_without_external_calls(tmp_path):
    _require_parameters(
        doctor.run_doctor, "python_check", "azure_cli_check", "extension_check",
        "login_check", "secure_cache_check", "config_check", "workbook_check", "service_check",
    )
    calls = []
    result = doctor.run_doctor(
        config=str(tmp_path / "daily-report.config.json"),
        python_check=lambda: ("PASS", "Python 3.11"),
        azure_cli_check=lambda: ("PASS", "Azure CLI available"),
        extension_check=lambda: ("WARN", "azure-devops extension missing"),
        login_check=lambda: ("FAIL", "Azure CLI login required"),
        secure_cache_check=lambda: ("PASS", "encrypted cache backend available"),
        config_check=lambda: ("PASS", "config valid"),
        workbook_check=lambda: ("WARN", "workbook not initialized"),
        service_check=lambda: calls.append("service") or ("WARN", "service check skipped"),
    )

    rendered = _result_dict(result)
    assert rendered["status"] == "FAIL"
    assert set(rendered["checks"]) == {
        "python", "azure_cli", "azure_devops_extension", "azure_login",
        "secure_cache", "config", "workbook", "service",
    }
    assert rendered["checks"]["python"]["status"] == "PASS"
    assert rendered["checks"]["azure_devops_extension"]["status"] == "WARN"
    assert rendered["checks"]["azure_login"]["status"] == "FAIL"
    assert calls == ["service"]


# TC-048: Production doctor routes prerequisite commands through an injected argv runner.
# Steps:
#   1. Supply a fake command runner and successful read-only probes.
    #   2. Run doctor without providing Azure CLI/extension/login check functions.
#   3. Verify the default production route issues only the required argv lists.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-7, AC-12.
def test_tc_048_default_doctor_routes_read_only_prerequisites_through_argv_runner(tmp_path):
    _require_parameters(
        doctor.run_doctor,
        "runner", "python_check", "secure_cache_probe", "config_validator", "workbook_probe", "service_probe",
    )
    commands = []

    def runner(argv):
        commands.append(argv)
        return {"returncode": 0, "stdout": "{}", "stderr": ""}

    result = doctor.run_doctor(
        config=str(tmp_path / "daily-report.config.json"),
        runner=runner,
        python_check=lambda: ("PASS", "Python 3.10"),
        secure_cache_probe=lambda: ("PASS", "secure cache available"),
        config_validator=lambda: [],
        workbook_probe=lambda: ("PASS", "workbook available"),
        service_probe=lambda: ("PASS", "read-only service check passed"),
    )

    assert _result_dict(result)["status"] == "PASS"
    assert commands == [
        ["az", "--version"],
        ["az", "extension", "show", "--name", "azure-devops", "--output", "json"],
        ["az", "account", "show", "--output", "json"],
    ]
    assert all(isinstance(argv, list) for argv in commands)


# TC-049: Missing Azure prerequisites are actionable and prevent blind service probing.
# Steps:
#   1. Inject a runner that reports Azure CLI unavailable.
#   2. Supply safe local probes and a service probe recorder.
#   3. Verify Azure CLI is FAIL, dependent checks explain the skip, and service is not called.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-7, AC-12.
def test_tc_049_doctor_maps_missing_azure_cli_and_skips_service_probe(tmp_path):
    _require_parameters(
        doctor.run_doctor,
        "runner", "python_check", "secure_cache_probe", "config_validator", "workbook_probe", "service_probe",
    )
    service_calls = []

    def runner(argv):
        if argv == ["az", "--version"]:
            return {"returncode": 127, "stdout": "", "stderr": "not found"}
        return {"returncode": 0, "stdout": "{}", "stderr": ""}

    rendered = _result_dict(doctor.run_doctor(
        config=str(tmp_path / "daily-report.config.json"),
        runner=runner,
        python_check=lambda: ("PASS", "Python 3.10"),
        secure_cache_probe=lambda: ("PASS", "secure cache available"),
        config_validator=lambda: [],
        workbook_probe=lambda: ("PASS", "workbook available"),
        service_probe=lambda: service_calls.append(True) or ("PASS", "must not run"),
    ))

    assert rendered["status"] == "FAIL"
    assert rendered["checks"]["azure_cli"]["status"] == "FAIL"
    assert rendered["checks"]["azure_devops_extension"]["status"] in {"WARN", "FAIL"}
    assert rendered["checks"]["azure_login"]["status"] in {"WARN", "FAIL"}
    assert rendered["checks"]["service"]["status"] == "WARN"
    assert "Azure CLI" in rendered["checks"]["service"]["message"]
    assert service_calls == []


# TC-050: Doctor semantically validates config and skips service after prerequisite/auth failure.
# Steps:
#   1. Inject ordered secure-cache, config-validator, workbook, and service probes.
#   2. Return semantic config errors although the file could be valid JSON.
#   3. Verify config is FAIL and the service probe is skipped with actionable WARN.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-7, AC-12.
def test_tc_050_doctor_uses_semantic_config_validation_and_safe_probe_order(tmp_path):
    _require_parameters(
        doctor.run_doctor,
        "runner", "python_check", "secure_cache_probe", "config_validator", "workbook_probe", "service_probe",
    )
    calls = []

    rendered = _result_dict(doctor.run_doctor(
        config=str(tmp_path / "daily-report.config.json"),
        runner=lambda _argv: {"returncode": 0, "stdout": "{}", "stderr": ""},
        python_check=lambda: ("PASS", "Python 3.10"),
        secure_cache_probe=lambda: calls.append("secure-cache") or ("PASS", "secure cache available"),
        config_validator=lambda: calls.append("config") or ["ado.organization is required"],
        workbook_probe=lambda: calls.append("workbook") or ("PASS", "workbook available"),
        service_probe=lambda: calls.append("service") or ("PASS", "must not run"),
    ))

    assert rendered["checks"]["config"]["status"] == "FAIL"
    assert "ado.organization" in rendered["checks"]["config"]["message"]
    assert rendered["checks"]["service"]["status"] == "WARN"
    assert "config" in rendered["checks"]["service"]["message"].lower()
    assert calls == ["secure-cache", "config", "workbook"]


# TC-051: Setup runs secured auth/discovery only after local setup succeeds.
# Steps:
#   1. Inject successful runtime, venv, dependency, state, and secure setup boundaries.
#   2. Run first setup against missing local state.
#   3. Verify secure setup occurs exactly once after local state initialization.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-7, AC-12.
def test_tc_051_setup_runs_secure_setup_once_after_local_state_success(tmp_path):
    setup = _setup_contract()
    _require_parameters(setup, "secure_setup")
    calls = []

    result = setup(
        tmp_path / "daily-home",
        **_offline_setup_boundaries(
            initialize=lambda *_args: calls.append("state"),
            secure_setup=lambda: calls.append("secure") or {"status": "PASS"},
        ),
    )

    assert _result_dict(result)["status"] == "PASS"
    assert calls == ["state", "secure"]


# TC-052: Auth-required secured setup is structured and never runs before local setup.
# Steps:
#   1. Inject successful dependency/state boundaries and an AUTH_REQUIRED secure result.
#   2. Run first setup.
#   3. Verify local state is initialized first, then setup returns actionable auth-required failure.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-6, AC-7, AC-12.
def test_tc_052_setup_returns_auth_required_after_local_state_success(tmp_path):
    setup = _setup_contract()
    _require_parameters(setup, "secure_setup")
    calls = []

    rendered = _result_dict(setup(
        tmp_path / "daily-home",
        **_offline_setup_boundaries(
            initialize=lambda *_args: calls.append("state"),
            secure_setup=lambda: calls.append("secure") or {"status": "AUTH_REQUIRED", "message": "Sign in required"},
        ),
    ))

    assert calls == ["state", "secure"]
    assert rendered["status"] == "AUTH_REQUIRED"
    assert "Sign in" in rendered["message"]


# TC-077: A portable bootstrap workbook has headers only; report creation owns the first data row.
# Steps:
#   1. Create a workbook through the packaged bootstrap creator in an isolated temporary path.
#   2. Open the generated workbook locally.
#   3. Verify the Daily Report sheet contains exactly its formatted header row and no seeded history.
# Design: portable-git-daily-report-dev-workflow.md Task 9/Task 11, AC-5, AC-9, AC-12.
def test_tc_077_bootstrap_default_workbook_is_headers_only_without_seeded_history(tmp_path):
    workbook_path = tmp_path / "DailyTask.xlsx"

    bootstrap._default_workbook_creator(workbook_path)

    workbook = openpyxl.load_workbook(workbook_path)
    worksheet = workbook["Daily Report"]
    assert worksheet.max_row == 1
    assert [worksheet[cell].value for cell in ("A1", "B1", "C1", "E1", "F1")] == [
        "Date", "Yesterday", "Today", "Report", "Timesheet"
    ]
    assert worksheet["A1"].number_format == "yyyy-mm-dd"


# TC-094: Bootstrap queue uses the portable pending-timesheets schema immediately.
# Steps: 1. Initialize local state in an isolated directory. 2. Load raw/portable queue. 3. Enqueue current work.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-10, AC-12.
def test_tc_094_bootstrap_queue_matches_pending_schema_and_accepts_first_enqueue(tmp_path):
    state_dir = tmp_path / "daily-home"
    result = bootstrap.initialize_state(
        state_dir,
        template_path=SCRIPTS_DIR.parent / "assets" / "config-template.json",
    )
    assert _result_dict(result)["status"] == "PASS"

    queue_path = state_dir / "pending-timesheets.json"
    assert json.loads(queue_path.read_text(encoding="utf-8")) == {"version": 1, "records": []}
    assert pending.load_queue(queue_path) == {"version": 1, "records": []}

    record, action = pending.enqueue_current(
        queue_path, "2026-07-27", "- Portable report", "AUTH_REQUIRED",
        now=lambda: "2026-07-27T00:00:00",
    )
    assert action == "CREATED"
    assert record["status"] == "pending"


# TC-095: Bootstrap and doctor reject Python 3.10 under one Python 3.11+ policy.
# Steps: 1. Inject a 3.10 runtime/version. 2. Resolve bootstrap and run doctor default check. 3. Verify matching stop policy.
# Design: portable-git-daily-report-dev-workflow.md Task 9, AC-5, AC-12.
def test_tc_095_bootstrap_and_doctor_require_python_311_or_newer(monkeypatch, tmp_path):
    bootstrap_result = bootstrap.resolve_python(
        tmp_path / "python310",
        executable_exists=lambda _candidate: True,
        version_reader=lambda _candidate: (3, 10, 14),
    )
    monkeypatch.setattr(doctor, "sys", type("DoctorSys", (), {
        "version_info": type("Version", (), {"major": 3, "minor": 10})(),
    })())
    doctor_status, doctor_message = doctor._default_python_check()

    assert _result_dict(bootstrap_result)["status"] == "FAIL"
    assert _result_dict(bootstrap_result)["details"]["code"] == "PYTHON_UNSUPPORTED"
    assert "3.11" in _result_dict(bootstrap_result)["message"]
    assert doctor_status == "FAIL"
    assert "3.11" in doctor_message
