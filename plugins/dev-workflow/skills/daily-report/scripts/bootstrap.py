"""Portable, idempotent first-run setup for the daily-report skill."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class BootstrapResult:
    """A stable, serializable outcome returned by every setup boundary."""

    status: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "details": dict(self.details),
            "exit_code": self.exit_code,
        }


def _pass(message: str, **details: Any) -> BootstrapResult:
    return BootstrapResult("PASS", message, details)


def _fail(code: str, message: str, **details: Any) -> BootstrapResult:
    return BootstrapResult("FAIL", message, {"code": code, **details}, exit_code=1)


def _as_result(value: Any, operation: str) -> BootstrapResult:
    if isinstance(value, BootstrapResult):
        return value
    if isinstance(value, Mapping):
        status = str(value.get("status", "PASS"))
        return BootstrapResult(status, str(value.get("message", operation)), dict(value.get("details", {})),
                               0 if status == "PASS" else 1)
    if isinstance(value, int):
        return _pass(operation) if value == 0 else _fail("DEPENDENCY_INSTALL_FAILED", f"{operation} failed.")
    return _pass(operation)


def _default_version_reader(candidate: str | Path) -> tuple[int, int, int]:
    completed = subprocess.run(
        [str(candidate), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "could not read Python version")
    parts = completed.stdout.strip().split(".")
    return tuple(int(part) for part in parts[:3])  # type: ignore[return-value]


def resolve_python(
    python: str | Path | None = None,
    *,
    executable_exists: Callable[[str | Path], bool] | None = None,
    version_reader: Callable[[str | Path], tuple[int, int, int]] | None = None,
) -> BootstrapResult:
    """Select a Python 3.11+ runtime without modifying it."""
    candidate = python or sys.executable
    exists = executable_exists or (lambda path: Path(path).is_file() or shutil.which(str(path)) is not None)
    reader = version_reader or _default_version_reader
    if not exists(candidate):
        return _fail("PYTHON_NOT_FOUND", "Python runtime was not found.", python=str(candidate))
    try:
        version = reader(candidate)
    except (OSError, RuntimeError, ValueError) as error:
        return _fail("PYTHON_VERSION_UNAVAILABLE", "Could not determine Python version.", python=str(candidate), error=str(error))
    if tuple(version[:2]) < (3, 11):
        return _fail("PYTHON_UNSUPPORTED", "Python 3.11 or newer is required.", python=str(candidate), version=".".join(map(str, version)))
    return _pass("Supported Python runtime resolved.", python=str(candidate), version=".".join(map(str, version)))


def _default_venv_creator(python: str | Path, destination: str | Path) -> None:
    completed = subprocess.run([str(python), "-m", "venv", str(destination)], check=False)
    if completed.returncode:
        raise RuntimeError(f"venv creation exited {completed.returncode}")


def ensure_venv(
    venv_path: str | Path,
    *,
    python: str | Path,
    path_exists: Callable[[str | Path], bool] | None = None,
    venv_creator: Callable[[str | Path, str | Path], None] | None = None,
) -> BootstrapResult:
    """Create the skill-owned virtual environment once, or reuse it."""
    destination = Path(venv_path)
    exists = path_exists or (lambda path: Path(path).exists())
    if exists(destination):
        return _pass("Existing isolated virtual environment reused.", venv=str(destination), changed=False)
    try:
        (venv_creator or _default_venv_creator)(python, destination)
    except (OSError, RuntimeError) as error:
        return _fail("VENV_CREATE_FAILED", "Could not create the isolated virtual environment.", venv=str(destination), error=str(error))
    return _pass("Isolated virtual environment created.", venv=str(destination), changed=True)


def install_requirements(
    venv_python: str | Path,
    requirements_path: str | Path,
    *,
    runner: Callable[[list[str]], Any] | None = None,
) -> BootstrapResult:
    """Install packages only through the isolated environment's interpreter."""
    argv = [str(venv_python), "-m", "pip", "install", "--requirement", str(requirements_path)]
    try:
        outcome = (runner or (lambda command: subprocess.run(command, check=False).returncode))(argv)
    except OSError as error:
        return _fail("DEPENDENCY_INSTALL_FAILED", "Could not run the isolated pip installer.", error=str(error))
    result = _as_result(outcome, "Dependency installation")
    if result.status != "PASS":
        return _fail("DEPENDENCY_INSTALL_FAILED", "Dependency installation failed in the isolated environment.")
    return _pass("Dependencies installed in the isolated environment.", argv=argv)


def _default_json_writer(path: str | Path, payload: Any) -> None:
    from lib_common import save_json_atomic
    save_json_atomic(path, payload)


def _default_workbook_creator(path: str | Path) -> None:
    import openpyxl
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Daily Report"
    worksheet.append(["Date", "Yesterday", "Today", "", "Report", "Timesheet"])
    worksheet["A1"].number_format = "yyyy-mm-dd"
    workbook.save(path)


def _state_artifacts(state_dir: str | Path) -> dict[str, Path]:
    root = Path(state_dir)
    return {
        "config": root / "daily-report.config.json",
        "workbook": root / "DailyTask.xlsx",
        "queue": root / "pending-timesheets.json",
    }


def initialize_state(
    state_dir: str | Path,
    *,
    template_path: str | Path,
    workbook_creator: Callable[[str | Path], None] | None = None,
    json_writer: Callable[[str | Path, Any], None] | None = None,
    permission_setter: Callable[[str | Path, int], None] | None = None,
    platform_name: str | None = None,
    artifacts: Sequence[str | Path] | None = None,
) -> BootstrapResult:
    """Create only missing config, workbook, and queue artifacts from local assets."""
    paths = _state_artifacts(state_dir)
    requested = {Path(item) for item in artifacts} if artifacts is not None else set(paths.values())
    writer = json_writer or _default_json_writer
    create_workbook = workbook_creator or _default_workbook_creator
    is_posix = (platform_name or os.name).lower() not in {"windows", "nt", "win32"}
    chmod = permission_setter or os.chmod
    try:
        Path(state_dir).mkdir(parents=True, exist_ok=True)
        if paths["config"] in requested and not paths["config"].exists():
            template = json.loads(Path(template_path).read_text(encoding="utf-8"))
            template["excel"]["path"] = str(paths["workbook"])
            writer(paths["config"], template)
            if is_posix:
                chmod(paths["config"], stat.S_IRUSR | stat.S_IWUSR)
        if paths["workbook"] in requested and not paths["workbook"].exists():
            create_workbook(paths["workbook"])
        if paths["queue"] in requested and not paths["queue"].exists():
            writer(paths["queue"], {"version": 1, "records": []})
            if is_posix:
                chmod(paths["queue"], stat.S_IRUSR | stat.S_IWUSR)
    except PermissionError as error:
        return _fail("WORKBOOK_LOCKED", "The workbook is locked; close it and rerun setup.", error=str(error))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _fail("STATE_INITIALIZATION_FAILED", "Could not initialize local daily-report state.", error=str(error))
    return _pass("Local daily-report state initialized.", changed=True, state_dir=str(state_dir))


def _venv_python(venv_path: Path) -> Path:
    return venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _default_copy(source: str | Path, destination: str | Path) -> None:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _default_secure_setup(state_dir: Path) -> BootstrapResult:
    """Refuse unconfigured secured setup without starting authentication."""
    config_path = _state_artifacts(state_dir)["config"]
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        timesheet = config["timesheet"]
        configured = all(timesheet.get(key) for key in ("org_url", "tenant_id", "client_id"))
    except (FileNotFoundError, OSError, KeyError, TypeError, json.JSONDecodeError):
        configured = False
    if not configured:
        return BootstrapResult(
            "AUTH_REQUIRED",
            "Configure Dataverse organization, tenant, and client values before secure setup.",
            {"code": "SECURE_SETUP_CONFIGURATION_REQUIRED"},
            exit_code=1,
        )
    return BootstrapResult(
        "WARN",
        "Secure authentication/discovery is deferred; rerun the daily workflow when ready to sign in.",
        {"code": "SECURE_SETUP_DEFERRED"},
    )


def setup(
    state_dir: str | Path,
    *,
    python: str | Path | None = None,
    requirements_path: str | Path | None = None,
    template_path: str | Path | None = None,
    import_config: str | Path | None = None,
    import_workbook: str | Path | None = None,
    replace: bool = False,
    resolve_runtime: Callable[[], Any] | None = None,
    ensure_environment: Callable[[], Any] | None = None,
    install_dependencies: Callable[[], Any] | None = None,
    path_exists: Callable[[str | Path], bool] | None = None,
    initialize: Callable[[Path], Any] | None = None,
    copy_file: Callable[[str | Path, str | Path], None] | None = None,
    secure_setup: Callable[[], Any] | None = None,
) -> BootstrapResult:
    """Run ordered setup with injectable boundaries; dependency failure precedes state writes."""
    skill_root = Path(__file__).resolve().parents[1]
    state = Path(state_dir)
    requirements = Path(requirements_path) if requirements_path else Path(__file__).with_name("requirements.txt")
    template = Path(template_path) if template_path else skill_root / "assets" / "config-template.json"
    exists = path_exists or (lambda path: Path(path).exists())
    runtime = resolve_runtime or (lambda: resolve_python(python))
    runtime_result = _as_result(runtime(), "Python resolution")
    if runtime_result.status != "PASS":
        return runtime_result
    runtime_python = runtime_result.details.get("python", str(python or sys.executable))
    venv_path = state / ".venv"
    environment = ensure_environment or (lambda: ensure_venv(venv_path, python=runtime_python))
    environment_result = _as_result(environment(), "Virtual environment setup")
    if environment_result.status != "PASS":
        return environment_result
    installer = install_dependencies or (lambda: install_requirements(_venv_python(venv_path), requirements))
    dependency_result = _as_result(installer(), "Dependency installation")
    if dependency_result.status != "PASS":
        return _fail("DEPENDENCY_INSTALL_FAILED", "Dependency installation failed; local state was not changed.")

    paths = _state_artifacts(state)
    copier = copy_file or _default_copy
    try:
        if import_config is not None:
            if copy_file is None and exists(paths["config"]) and not replace:
                return _fail("IMPORT_DESTINATION_EXISTS", "Config already exists; rerun with --replace to import over it.")
            copier(import_config, paths["config"])
        if import_workbook is not None:
            if copy_file is None and exists(paths["workbook"]) and not replace:
                return _fail("IMPORT_DESTINATION_EXISTS", "Workbook already exists; rerun with --replace to import over it.")
            copier(import_workbook, paths["workbook"])
    except (OSError, shutil.Error) as error:
        return _fail("LEGACY_IMPORT_FAILED", "Could not copy explicitly requested legacy data.", error=str(error))

    missing = [path for path in paths.values() if not exists(path)]
    if not missing:
        return _pass("Existing local state is complete; no changes were made.", changed=False, state_dir=str(state))
    if initialize is None:
        initialized = _as_result(
            initialize_state(state, template_path=template, artifacts=missing), "Local state initialization"
        )
    else:
        # The injected boundary represents the complete local-state phase.  The
        # first missing path provides a concrete recovery target for test doubles.
        initialized = _as_result(initialize(missing[0]), "Local state initialization")
    if initialized.status != "PASS":
        return initialized
    if secure_setup is not None:
        secured = _as_result(secure_setup(), "Secure setup")
        if secured.status != "PASS":
            return secured
    return _pass("Local daily-report setup completed.", changed=True, state_dir=str(state), replaced=replace)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the portable daily-report skill.")
    subcommands = parser.add_subparsers(dest="command")
    setup_parser = subcommands.add_parser("setup", help="Create or validate local daily-report setup.")
    setup_parser.add_argument("--python", help="Python interpreter for the isolated environment.")
    setup_parser.add_argument("--import-config", help="Explicit legacy config file to copy.")
    setup_parser.add_argument("--import-workbook", help="Explicit legacy workbook to copy.")
    setup_parser.add_argument("--replace", action="store_true", help="Record an explicit replacement request.")
    return parser


def _emit(result: BootstrapResult) -> None:
    print(f"STATUS: {result.status}")
    print(result.message)
    if result.details.get("code"):
        print(f"CODE: {result.details['code']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command in (None, "setup"):
        from lib_common import resolve_state_paths
        result = setup(
            resolve_state_paths()["state_dir"], python=getattr(arguments, "python", None),
            import_config=getattr(arguments, "import_config", None), import_workbook=getattr(arguments, "import_workbook", None),
            replace=getattr(arguments, "replace", False),
            secure_setup=lambda: _default_secure_setup(resolve_state_paths()["state_dir"]),
        )
        _emit(result)
        return result.exit_code
    parser.error(f"Unsupported command: {arguments.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
