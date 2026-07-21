"""Spec-first package CLI and policy-filename regressions.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 final CLI audit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from review_harness import runtime_preflight


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PACKAGE_ROOT.parent


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "review_harness", *arguments],
        cwd=SCRIPTS_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_atomic_json_output(output_path: Path) -> dict[str, object]:
    assert output_path.is_file()
    assert list(output_path.parent.glob("*.tmp")) == []
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_tc_040_package_exposes_python_module_entrypoint() -> None:
    """TC-040 / Task 1 CLI: review_harness is directly executable as a package.

    Steps:
      1. Locate the canonical review_harness package.
      2. Inspect its module-execution entrypoint.
      3. Verify python -m review_harness has a package dispatcher.
    """
    # Arrange / Act / Assert
    assert (PACKAGE_ROOT / "__main__.py").is_file()


@pytest.mark.parametrize(
    "command",
    [
        "runtime-preflight",
        "scope-manifest",
        "discover-tests",
        "test-gate",
        "statusline-bridge",
        "statusline-setup",
    ],
)
def test_tc_041_package_dispatches_every_review_harness_command(command: str) -> None:
    """TC-041 / Task 1 CLI: every published harness command is discoverable.

    Steps:
      1. Invoke one published command through python -m review_harness.
      2. Request its command-specific help.
      3. Verify dispatch succeeds without executing the command workflow.
    """
    # Arrange / Act
    completed = _run_cli(command, "--help")

    # Assert
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "usage:" in completed.stdout.lower()


def test_tc_042_scope_manifest_cli_persists_atomic_json_output(tmp_path: Path) -> None:
    """TC-042 / DoD-1.5: scope-manifest supports durable machine-readable evidence.

    Steps:
      1. Invoke scope-manifest with production and documentation paths plus an output path.
      2. Load the persisted manifest.
      3. Verify its scope buckets and that no temporary output artifact remains.
    """
    # Arrange
    output_path = tmp_path / "evidence" / "scope.json"

    # Act
    completed = _run_cli(
        "scope-manifest",
        "--output",
        str(output_path),
        "src/service.py",
        "docs/runtime-policy.md",
    )

    # Assert
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = _assert_atomic_json_output(output_path)
    assert result["status"] == "pass"
    assert result["productionFiles"] == ["src/service.py"]
    assert result["evidenceFiles"] == ["docs/runtime-policy.md"]


def test_tc_043_discover_tests_cli_accepts_repeated_inputs_and_atomic_output(tmp_path: Path) -> None:
    """TC-043 / DoD-1.6: discover-tests accepts complete changed-code context.

    Steps:
      1. Create direct test evidence for two changed symbols.
      2. Invoke discover-tests with repeated production-file and symbol arguments.
      3. Verify both symbols and direct tests persist with no temporary artifact.
    """
    # Arrange
    repo = tmp_path / "repo"
    test_file = repo / "tests" / "test_service.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("calculate_total\nformat_total\n", encoding="utf-8")
    output_path = tmp_path / "evidence" / "discovery.json"

    # Act
    completed = _run_cli(
        "discover-tests",
        "--repo",
        str(repo),
        "--production-file",
        "src/service.py",
        "--production-file",
        "src/formatter.py",
        "--symbol",
        "calculate_total",
        "--symbol",
        "format_total",
        "--output",
        str(output_path),
    )

    # Assert
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = _assert_atomic_json_output(output_path)
    assert result["status"] == "pass"
    assert result["changedSymbols"] == ["calculate_total", "format_total"]
    assert result["directTests"] == [str(test_file.relative_to(repo))]


@pytest.mark.parametrize(
    ("program", "timeout_seconds", "expected_status", "expected_exit_code"),
    [
        ("raise SystemExit(7)", "5", "fail", 7),
        ("import time; time.sleep(2)", "0.01", "timeout", 124),
    ],
)
def test_tc_044_test_gate_cli_persists_failure_and_returns_nonzero(
    tmp_path: Path,
    program: str,
    timeout_seconds: str,
    expected_status: str,
    expected_exit_code: int,
) -> None:
    """TC-044 / DoD-1.6: failed or timed-out test evidence cannot return CLI success.

    Steps:
      1. Invoke test-gate with a failing or timing-out command and an output path.
      2. Capture both the CLI result and persisted test evidence.
      3. Verify nonzero gate exit, exact outcome, and no temporary output artifact.
    """
    # Arrange
    output_path = tmp_path / "evidence" / f"{expected_status}.json"

    # Act
    completed = _run_cli(
        "test-gate",
        "--cwd",
        str(tmp_path),
        "--timeout-seconds",
        timeout_seconds,
        "--output",
        str(output_path),
        "--",
        sys.executable,
        "-c",
        program,
    )

    # Assert
    assert completed.returncode != 0
    result = _assert_atomic_json_output(output_path)
    assert result["status"] == expected_status
    assert result["exitCode"] == expected_exit_code


def test_tc_045_runtime_policy_uses_canonical_kebab_case_filename() -> None:
    """TC-045 / DoD-1.1: source and runtime agree on one portable policy filename.

    Steps:
      1. Locate runtime policy files beside the preflight module.
      2. Inspect the preflight module's configured policy path.
      3. Verify only runtime-policy.json exists and is used.
    """
    # Arrange
    canonical = PACKAGE_ROOT / "runtime-policy.json"
    legacy = PACKAGE_ROOT / "runtime_policy.json"

    # Act / Assert
    assert canonical.is_file()
    assert runtime_preflight.POLICY_PATH == canonical
    assert not legacy.exists()
