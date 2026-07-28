"""Portable state and config contracts for daily-report.

Test cases: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Design doc: .plans/portable-git-daily-report-dev-workflow.md (Task 6; AC-1, AC-5, AC-6, AC-12)

TC-001 and TC-002 are CHARACTERIZATION tests: they pin the current public
``load_config`` behaviour before portable state resolution changes it. The
remaining cases deliberately specify the Task 6 contract and are expected to
be RED until that implementation lands.
"""
import json
import os
import platform
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import lib_common  # noqa: E402


def _write_config(path: Path, marker: str) -> None:
    path.write_text(json.dumps({"marker": marker}), encoding="utf-8")


# TC-001: An explicit config path remains higher priority than DAILY_REPORT_CONFIG.
# Steps:
#   1. Create separate explicit and environment config files.
#   2. Set DAILY_REPORT_CONFIG to the environment file.
#   3. Load the explicit file and verify its contents are returned.
# Design: portable-git-daily-report-dev-workflow.md Task 6, AC-12.
def test_tc_001_characterize_load_config_prefers_explicit_path(tmp_path, monkeypatch):
    # Arrange
    explicit = tmp_path / "explicit.json"
    environment = tmp_path / "environment.json"
    _write_config(explicit, "explicit")
    _write_config(environment, "environment")
    monkeypatch.setenv("DAILY_REPORT_CONFIG", str(environment))

    # Act
    config = lib_common.load_config(str(explicit))

    # Assert
    assert config == {"marker": "explicit"}


# TC-002: DAILY_REPORT_CONFIG is usable after the caller changes directory.
# Steps:
#   1. Create a config file outside a different working directory.
#   2. Set DAILY_REPORT_CONFIG to that file.
#   3. Load the config after changing directory and verify its contents.
# Design: portable-git-daily-report-dev-workflow.md Task 6, AC-1 and AC-12.
def test_tc_002_characterize_load_config_uses_environment_path_without_cwd_dependency(tmp_path, monkeypatch):
    # Arrange
    config_path = tmp_path / "state" / "daily-report.config.json"
    config_path.parent.mkdir()
    _write_config(config_path, "environment")
    other_directory = tmp_path / "unrelated-cwd"
    other_directory.mkdir()
    monkeypatch.setenv("DAILY_REPORT_CONFIG", str(config_path))
    monkeypatch.chdir(other_directory)

    # Act
    config = lib_common.load_config()

    # Assert
    assert config == {"marker": "environment"}


@pytest.mark.parametrize(
    ("platform_name", "home", "env", "expected_state"),
    [
        (
            "Windows",
            Path("C:/Users/tester"),
            {"LOCALAPPDATA": "C:/Users/tester/AppData/Local"},
            Path("C:/Users/tester/AppData/Local/rd-team/dev-workflow/daily-report"),
        ),
        (
            "Darwin",
            Path("/Users/tester"),
            {},
            Path("/Users/tester/Library/Application Support/rd-team/dev-workflow/daily-report"),
        ),
        (
            "Linux",
            Path("/home/tester"),
            {},
            Path("/home/tester/.local/share/rd-team/dev-workflow/daily-report"),
        ),
    ],
)
def test_tc_003_resolves_os_standard_state_paths_without_cwd_dependency(
    tmp_path, monkeypatch, platform_name, home, env, expected_state
):
    """TC-003: Resolve standard state locations for each supported OS.

    Steps:
      1. Simulate a Windows local-app-data directory, macOS home, or Linux home.
      2. Change to an unrelated working directory.
      3. Resolve state and verify the OS-standard path is selected.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-1, AC-5, AC-6.
    """
    # Arrange
    unrelated_directory = tmp_path / "unrelated-cwd"
    unrelated_directory.mkdir()
    monkeypatch.chdir(unrelated_directory)

    # Act
    resolver = getattr(lib_common, "resolve_state_paths", None)

    # Assert
    assert callable(resolver), "Task 6 must expose resolve_state_paths for portable state resolution."
    paths = resolver(home=home, platform_name=platform_name, env=env)
    assert paths["state_dir"] == expected_state


def test_tc_004_applies_home_config_and_explicit_override_precedence(tmp_path):
    """TC-004: Apply explicit, config-env, then home-env override precedence.

    Steps:
      1. Supply a daily-report-home override and a separate config override.
      2. Resolve state and config locations.
      3. Verify home replaces the state root, config-env wins over home, and explicit wins.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-1, AC-5, AC-6.
    """
    # Arrange
    home = tmp_path / "daily-home"
    environment_config = tmp_path / "external" / "config.json"
    explicit_config = tmp_path / "explicit" / "config.json"
    env = {"DAILY_REPORT_HOME": str(home), "DAILY_REPORT_CONFIG": str(environment_config)}

    # Act
    resolver = getattr(lib_common, "resolve_config_path", None)
    state_resolver = getattr(lib_common, "resolve_state_paths", None)

    # Assert
    assert callable(resolver), "Task 6 must expose resolve_config_path with portable override precedence."
    assert callable(state_resolver), "Task 6 must expose resolve_state_paths with DAILY_REPORT_HOME support."
    assert state_resolver(env={"DAILY_REPORT_HOME": str(home)})["state_dir"] == home
    assert resolver(env={"DAILY_REPORT_HOME": str(home)}) == home / "daily-report.config.json"
    assert resolver(env=env) == environment_config
    assert resolver(path=explicit_config, env=env) == explicit_config


def test_tc_009_uses_xdg_data_home_for_linux_state_when_set(tmp_path, monkeypatch):
    """TC-009: Use XDG data home for Linux state when configured.

    Steps:
      1. Simulate Linux with a home directory and an XDG data-home directory.
      2. Change to an unrelated working directory.
      3. Resolve state and verify it is rooted under XDG data home.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-1, AC-5, AC-6.
    """
    # Arrange
    unrelated_directory = tmp_path / "unrelated-cwd"
    unrelated_directory.mkdir()
    monkeypatch.chdir(unrelated_directory)
    home = Path("/home/tester")
    xdg_data_home = Path("/var/lib/tester-data")
    resolver = getattr(lib_common, "resolve_state_paths", None)

    # Act / Assert
    assert callable(resolver), "Task 6 must expose resolve_state_paths for XDG data-home resolution."
    paths = resolver(
        home=home,
        platform_name="Linux",
        env={"XDG_DATA_HOME": str(xdg_data_home)},
    )
    assert paths["state_dir"] == xdg_data_home / "rd-team" / "dev-workflow" / "daily-report"


def test_tc_005_creates_state_directories_idempotently(tmp_path):
    """TC-005: Create all local state parents without touching external services.

    Steps:
      1. Choose an empty daily-report home directory.
      2. Initialize local state twice.
      3. Verify config, queue, and cache parent directories exist after both calls.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-5 and AC-12.
    """
    # Arrange
    home = tmp_path / "daily-home"
    resolver = getattr(lib_common, "resolve_state_paths", None)

    # Act
    assert callable(resolver), "Task 6 must expose resolve_state_paths for local state initialization."
    first = resolver(home=home, platform_name="Linux", create=True)
    second = resolver(home=home, platform_name="Linux", create=True)

    # Assert
    assert first == second
    assert first["config_path"].parent.is_dir()
    assert first["queue_path"].parent.is_dir()
    assert first["auth_cache_path"].parent.is_dir()


def test_tc_006_writes_json_atomically_without_corrupting_existing_document(tmp_path, monkeypatch):
    """TC-006: Preserve the prior JSON document if replacement fails.

    Steps:
      1. Save an initial local state document.
      2. Simulate a replacement failure while saving a changed document.
      3. Verify the initial document remains complete and readable.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-5, AC-6, AC-12.
    """
    # Arrange
    path = tmp_path / "state.json"
    path.write_text('{"version": 1}', encoding="utf-8")
    writer = getattr(lib_common, "save_json_atomic", None)

    # Act
    assert callable(writer), "Task 6 must expose save_json_atomic for durable local state."
    monkeypatch.setattr(lib_common.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))

    # Assert
    with pytest.raises(OSError, match="replace failed"):
        writer(path, {"version": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1}


def test_tc_007_tightens_json_file_permissions_when_posix_modes_are_observable(tmp_path, monkeypatch):
    """TC-007: Restrict local state JSON to its owner on POSIX platforms.

    Steps:
      1. Simulate a POSIX platform and choose a new local state file.
      2. Save state JSON.
      3. Verify group and other permissions are removed.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-5, AC-6, AC-12.
    """
    # Arrange
    path = tmp_path / "state.json"
    writer = getattr(lib_common, "save_json_atomic", None)

    # Act
    assert callable(writer), "Task 6 must expose save_json_atomic for protected local state."

    # Assert
    if os.name == "posix":
        writer(path, {"status": "safe"})
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    else:
        chmod_calls = []
        monkeypatch.setattr(lib_common.os, "name", "posix")
        monkeypatch.setattr(
            lib_common.os,
            "chmod",
            lambda requested_path, mode: chmod_calls.append((Path(requested_path), mode)),
        )

        writer(path, {"status": "safe"})

        assert (path, 0o600) in chmod_calls


def test_tc_010_uses_the_actual_os_family_when_platform_name_is_not_injected(tmp_path):
    """TC-010: Use the current operating system when no platform override is supplied.

    Steps:
      1. Supply deterministic home and environment directories for the current CI operating system.
      2. Resolve state paths without passing a platform name.
      3. Verify the OS-standard state directory for Windows, macOS, or Linux is selected.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-1, AC-5, AC-6.
    """
    # Arrange
    home = tmp_path / "home"
    system_name = platform.system()
    env = {
        "LOCALAPPDATA": str(tmp_path / "local-app-data"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
    }
    expected_state = {
        "Windows": Path(env["LOCALAPPDATA"]) / "rd-team" / "dev-workflow" / "daily-report",
        "Darwin": home / "Library" / "Application Support" / "rd-team" / "dev-workflow" / "daily-report",
    }.get(
        system_name,
        Path(env["XDG_DATA_HOME"]) / "rd-team" / "dev-workflow" / "daily-report",
    )
    resolver = getattr(lib_common, "resolve_state_paths", None)

    # Act
    assert callable(resolver), "Task 6 must expose resolve_state_paths for portable state resolution."
    paths = resolver(home=home, env=env)

    # Assert
    assert paths["state_dir"] == expected_state


def test_tc_008_reports_missing_and_malformed_config_as_actionable_errors(tmp_path):
    """TC-008: Explain missing and malformed configuration without a traceback.

    Steps:
      1. Load a config file that is absent and verify the recovery guidance.
      2. Load a malformed config file.
      3. Verify a structured validation error explains the invalid JSON.
    Design: portable-git-daily-report-dev-workflow.md Task 6, AC-5, AC-6, AC-12.
    """
    # Arrange
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    # Act / Assert
    with pytest.raises(SystemExit, match="config not found"):
        lib_common.load_config(missing)
    try:
        lib_common.load_config(malformed)
    except SystemExit as error:
        actual_error = str(error)
    except json.JSONDecodeError as error:
        actual_error = f"unstructured {type(error).__name__}: {error}"

    assert actual_error.startswith("ERROR: config is not valid JSON"), (
        "Task 6 must turn malformed JSON into an actionable validation error."
    )


# TC-096: Missing-config recovery points only to a packaged current asset.
# Steps: 1. Load an absent config. 2. Read error text. 3. Verify config-template.json exists and stale name is absent.
# Design: portable-git-daily-report-dev-workflow.md Task 6/9, AC-5, AC-12.
def test_tc_096_missing_config_guidance_references_existing_config_template_only(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(SystemExit) as error:
        lib_common.load_config(missing)

    message = str(error.value)
    current_asset = SCRIPTS_DIR.parent / "assets" / "config-template.json"
    assert current_asset.is_file()
    assert "assets/config-template.json" in message
    assert "config.template.json" not in message
