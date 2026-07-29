"""Read-only prerequisites diagnostics for the portable daily-report skill."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class DoctorResult:
    status: str
    message: str
    checks: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message, "checks": dict(self.checks), "exit_code": self.exit_code}


def _default_python_check() -> tuple[str, str]:
    version = sys.version_info
    return ("PASS", f"Python {version.major}.{version.minor}") if (version.major, version.minor) >= (3, 11) else ("FAIL", "Python 3.11 or newer is required")


def _resolve_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    resolved = shutil.which(argv[0])
    return [resolved, *argv[1:]] if resolved else argv


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(_resolve_argv(argv), check=False, capture_output=True, text=True)


def _command_result(value: Any, label: str) -> tuple[str, str]:
    returncode = value.get("returncode", 1) if isinstance(value, Mapping) else getattr(value, "returncode", 1)
    stderr = value.get("stderr", "") if isinstance(value, Mapping) else getattr(value, "stderr", "")
    return ("PASS", f"{label} available") if int(returncode) == 0 else ("FAIL", f"{label} unavailable" + (f": {str(stderr).strip()}" if str(stderr).strip() else ""))


def _run_read_only(runner: Callable[[list[str]], Any], argv: list[str]) -> Any:
    try:
        return runner(argv)
    except OSError as error:
        return {"returncode": 127, "stdout": "", "stderr": str(error)}


def _default_config_validator(config: str | None) -> list[str]:
    if not config:
        return ["config path is required for semantic validation"]
    try:
        payload = json.loads(Path(config).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["config is not initialized"]
    except (OSError, json.JSONDecodeError):
        return ["config is unreadable or invalid JSON"]
    errors = []
    for section, key in (("ado", "organization"), ("timesheet", "org_url"), ("timesheet", "tenant_id"), ("timesheet", "client_id")):
        if not payload.get(section, {}).get(key):
            errors.append(f"{section}.{key} is required")
    return errors


def _default_workbook_probe(config: str | None) -> tuple[str, str]:
    if not config:
        return "WARN", "Workbook was not inspected without an explicit config"
    try:
        workbook = Path(json.loads(Path(config).read_text(encoding="utf-8"))["excel"]["path"])
    except (FileNotFoundError, OSError, KeyError, TypeError, json.JSONDecodeError):
        return "WARN", "Workbook is not initialized or cannot be resolved"
    return ("PASS", "Workbook exists") if workbook.is_file() else ("WARN", "Workbook is not initialized")


def _normalize_check(value: Any, name: str) -> dict[str, str]:
    if isinstance(value, tuple) and len(value) >= 2:
        status, message = value[0], value[1]
    elif isinstance(value, Mapping):
        status, message = value.get("status", "FAIL"), value.get("message", name)
    else:
        status, message = "FAIL", f"{name} returned an invalid result"
    status = str(status).upper()
    return {"status": status if status in {"PASS", "WARN", "FAIL"} else "FAIL", "message": str(message)}


def _validator_result(errors: Any) -> tuple[str, str]:
    if errors is None or errors == []:
        return "PASS", "Config semantics are valid"
    if isinstance(errors, (list, tuple)):
        return "FAIL", "; ".join(map(str, errors))
    return "FAIL", str(errors)


def run_doctor(
    *,
    config: str | None = None,
    verbose: bool = False,
    runner: Callable[[list[str]], Any] | None = None,
    python_check: Callable[[], Any] | None = None,
    azure_cli_check: Callable[[], Any] | None = None,
    extension_check: Callable[[], Any] | None = None,
    login_check: Callable[[], Any] | None = None,
    secure_cache_check: Callable[[], Any] | None = None,
    config_check: Callable[[], Any] | None = None,
    workbook_check: Callable[[], Any] | None = None,
    service_check: Callable[[], Any] | None = None,
    secure_cache_probe: Callable[[], Any] | None = None,
    config_validator: Callable[[], Any] | None = None,
    workbook_probe: Callable[[], Any] | None = None,
    service_probe: Callable[[], Any] | None = None,
) -> DoctorResult:
    """Collect diagnostics with only read-only argv commands and guarded service access."""
    run = runner or _default_runner
    checks: dict[str, dict[str, str]] = {}
    checks["python"] = _normalize_check((python_check or _default_python_check)(), "python")
    checks["azure_cli"] = _normalize_check(azure_cli_check() if azure_cli_check else _command_result(_run_read_only(run, ["az", "--version"]), "Azure CLI"), "azure_cli")

    if extension_check:
        checks["azure_devops_extension"] = _normalize_check(extension_check(), "azure_devops_extension")
    elif checks["azure_cli"]["status"] == "PASS":
        checks["azure_devops_extension"] = _normalize_check(_command_result(_run_read_only(run, ["az", "extension", "show", "--name", "azure-devops", "--output", "json"]), "Azure DevOps extension"), "azure_devops_extension")
    else:
        checks["azure_devops_extension"] = {"status": "WARN", "message": "Skipped because Azure CLI is unavailable"}
    if login_check:
        checks["azure_login"] = _normalize_check(login_check(), "azure_login")
    elif checks["azure_cli"]["status"] == "PASS":
        checks["azure_login"] = _normalize_check(_command_result(_run_read_only(run, ["az", "account", "show", "--output", "json"]), "Azure CLI login"), "azure_login")
    else:
        checks["azure_login"] = {"status": "WARN", "message": "Skipped because Azure CLI is unavailable"}

    checks["secure_cache"] = _normalize_check((secure_cache_probe or secure_cache_check or (lambda: ("WARN", "Encrypted cache backend was not initialized")))(), "secure_cache")
    if config_validator is not None:
        checks["config"] = _normalize_check(_validator_result(config_validator()), "config")
    else:
        checks["config"] = _normalize_check((config_check or (lambda: _validator_result(_default_config_validator(config))))(), "config")
    checks["workbook"] = _normalize_check((workbook_probe or workbook_check or (lambda: _default_workbook_probe(config)))(), "workbook")

    guarded = ("azure_cli", "azure_devops_extension", "azure_login", "secure_cache", "config")
    failures = [name for name in guarded if checks[name]["status"] == "FAIL"]
    if service_probe is not None:
        if failures:
            labels = {"azure_cli": "Azure CLI", "azure_devops_extension": "Azure DevOps extension", "azure_login": "Azure CLI login", "secure_cache": "secure cache", "config": "config"}
            checks["service"] = {"status": "WARN", "message": f"Skipped service probe because {', '.join(labels[name] for name in failures)} prerequisite failed"}
        else:
            checks["service"] = _normalize_check(service_probe(), "service")
    else:
        # Legacy explicit service_check remains unguarded for its prior public contract.
        checks["service"] = _normalize_check(service_check(), "service") if service_check else {"status": "WARN", "message": "Read-only service access was not queried"}

    statuses = {check["status"] for check in checks.values()}
    status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return DoctorResult(status, "Doctor checks completed without authentication or mutation.", checks, 1 if status == "FAIL" else 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check portable daily-report prerequisites.")
    parser.add_argument("--config", help="Local config to inspect read-only.")
    parser.add_argument("--verbose", action="store_true", help="Include all diagnostic details.")
    return parser


def _emit(result: DoctorResult) -> None:
    print(f"STATUS: {result.status}")
    for name, check in result.checks.items():
        print(f"[{check['status']}] {name}: {check['message']}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    result = run_doctor(config=arguments.config, verbose=arguments.verbose)
    _emit(result)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
