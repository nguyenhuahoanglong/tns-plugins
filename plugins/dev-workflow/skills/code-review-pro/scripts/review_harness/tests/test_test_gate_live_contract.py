"""Spec-first symbol discovery and execution regressions for DoD-1.6.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 live-contract audit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from review_harness.test_gate import discover_tests, extract_changed_symbols, main, run_test_command


@pytest.mark.parametrize(
    ("source_path", "diff", "expected"),
    [
        (
            "src/OrderService.cs",
            "+public class OrderService\n+{\n+    public decimal CalculateTotal(Order order) => order.Total;\n+}",
            ["OrderService.CalculateTotal"],
        ),
        (
            "src/payment.ts",
            "+export function calculateTotal(order: Order): number { return order.total; }\n+export class PaymentService {\n+  approve(payment: Payment): boolean { return true; }\n+}",
            ["calculateTotal", "PaymentService.approve"],
        ),
        (
            "src/payment.js",
            "+export function calculateTotal(order) { return order.total; }\n+class PaymentService {\n+  approve(payment) { return true; }\n+}",
            ["calculateTotal", "PaymentService.approve"],
        ),
        (
            "scripts/Invoke-Review.ps1",
            "+function Invoke-Review {\n+    param([string] $Target)\n+}",
            ["Invoke-Review"],
        ),
    ],
)
def test_tc_030_extracts_changed_symbols_from_supported_languages(
    source_path: str, diff: str, expected: list[str]
) -> None:
    """TC-030 / DoD-1.6: supported source declarations produce direct-test symbols.

    Steps:
      1. Provide an added declaration in C#, TypeScript, JavaScript, or PowerShell.
      2. Extract changed symbols for the matching source extension.
      3. Verify function and class-method names are returned in source order.
    """
    # Arrange / Act / Assert
    assert extract_changed_symbols(diff, source_path) == expected


def test_tc_031_discovers_all_supported_direct_test_naming_patterns(tmp_path: Path) -> None:
    """TC-031 / DoD-1.6: conventional test folders and suffixes are all discoverable.

    Steps:
      1. Store direct tests using *.Tests, __tests__, *.test.*, *.spec.*, and test_*.py patterns.
      2. Discover tests for one changed production symbol.
      3. Verify every conventional direct-test file is returned.
    """
    # Arrange
    paths = [
        tmp_path / "Payments.Tests" / "OrderServiceChecks.cs",
        tmp_path / "src" / "__tests__" / "payment_checks.ts",
        tmp_path / "src" / "payment.test.js",
        tmp_path / "src" / "payment.spec.ts",
        tmp_path / "tests" / "test_payment.py",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("calculate_total\n", encoding="utf-8")

    # Act
    result = discover_tests(tmp_path, ["src/payment.py"], ["calculate_total"])

    # Assert
    assert result["status"] == "pass"
    assert result["directTests"] == sorted(str(path.relative_to(tmp_path)) for path in paths)


@pytest.mark.parametrize(
    ("program", "timeout_seconds", "expected_status", "expected_exit"),
    [
        ("print('1 passed'); raise SystemExit(0)", 5, "pass", 0),
        ("print('1 failed'); raise SystemExit(3)", 5, "fail", 3),
        ("import time; time.sleep(2)", 0.01, "timeout", 124),
    ],
)
def test_tc_032_reports_pass_fail_and_timeout_execution_status(
    tmp_path: Path,
    program: str,
    timeout_seconds: float,
    expected_status: str,
    expected_exit: int,
) -> None:
    """TC-032 / DoD-1.6: command evidence includes a deterministic outcome status.

    Steps:
      1. Run a command that passes, fails, or exceeds its timeout.
      2. Capture structured execution evidence.
      3. Verify its status and process exit code represent the observed outcome.
    """
    # Arrange
    command = [sys.executable, "-c", program]

    # Act
    result = run_test_command(command, tmp_path, timeout_seconds=timeout_seconds)

    # Assert
    assert result["status"] == expected_status
    assert result["exitCode"] == expected_exit


def test_tc_033_test_gate_cli_exits_nonzero_when_test_command_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-033 / DoD-1.6: a failed test command makes the test-gate CLI fail.

    Steps:
      1. Invoke the test-gate CLI with a command that exits unsuccessfully.
      2. Capture its CLI exit code and structured output.
      3. Verify the gate exits nonzero instead of reporting shell success.
    """
    # Arrange
    argv = ["--cwd", str(tmp_path), sys.executable, "-c", "raise SystemExit(4)"]

    # Act
    exit_code = main(argv)
    output = capsys.readouterr().out

    # Assert
    assert exit_code != 0
    assert '"exitCode": 4' in output
