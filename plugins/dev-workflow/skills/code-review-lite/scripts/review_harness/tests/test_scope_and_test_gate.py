"""Spec-first tests for DoD-1.5 and DoD-1.6 harness behavior.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

from review_harness.scope_manifest import build_scope_manifest, classify_file
from review_harness.test_gate import discover_tests, extract_changed_symbols, run_test_command


def test_tc_011_classifies_production_evidence_and_excluded_paths_with_stable_codes() -> None:
    """TC-011 / DoD-1.5: review scope separates findings from evidence and exclusions.

    Steps:
      1. Provide production, test, document, generated, vendor, and binary paths.
      2. Classify each changed path.
      3. Verify their stable review buckets and reason codes.
    """
    # Arrange
    expected = {
        "src/service.py": ("production", "production_code"),
        "tests/test_service.py": ("evidence", "test_file"),
        "docs/decision.md": ("evidence", "documentation"),
        "dist/bundle.js": ("excluded", "generated_output"),
        "vendor/library.js": ("excluded", "vendor_code"),
        "assets/logo.png": ("excluded", "binary_file"),
    }

    # Act / Assert
    for path, classification in expected.items():
        assert classify_file(path) == classification


def test_tc_012_reports_no_production_code_when_only_evidence_or_exclusions_change() -> None:
    """TC-012 / DoD-1.5: non-production changes cannot produce review findings.

    Steps:
      1. Build a manifest from test, document, and generated files only.
      2. Inspect the production review allowlist.
      3. Verify the no-production-code outcome and empty allowlist.
    """
    # Arrange
    paths = ["tests/test_service.py", "docs/decision.md", "dist/bundle.js"]

    # Act
    manifest = build_scope_manifest(paths)

    # Assert
    assert manifest["status"] == "no-production-code"
    assert manifest["productionFiles"] == []
    assert manifest["evidenceFiles"] == ["tests/test_service.py", "docs/decision.md"]


def test_tc_013_extracts_changed_python_symbols_from_unified_diff() -> None:
    """TC-013 / DoD-1.6: changed symbols drive direct test discovery.

    Steps:
      1. Provide a unified diff that adds a Python function and class method.
      2. Extract changed symbols for the production file.
      3. Verify both changed symbols are returned in source order.
    """
    # Arrange
    diff = """diff --git a/src/payments.py b/src/payments.py
+++ b/src/payments.py
@@
+def calculate_total(order):
+    return order.total
+
+class PaymentService:
+    def approve(self, payment):
+        return True
"""

    # Act
    symbols = extract_changed_symbols(diff, "src/payments.py")

    # Assert
    assert symbols == ["calculate_total", "PaymentService.approve"]


def test_tc_043_extracts_the_enclosing_python_symbol_from_unmodified_hunk_context() -> None:
    """TC-043 / DoD-1.6: function-body changes retain their Python symbol.

    Steps:
      1. Provide a diff that changes only a line inside a Python function.
      2. Read the unified-diff hunk context naming that function.
      3. Verify direct test discovery receives the enclosing symbol.
    """
    diff = """diff --git a/src/payments.py b/src/payments.py
+++ b/src/payments.py
@@ -10,7 +10,7 @@ def calculate_total(order):
     subtotal = order.subtotal
-    return subtotal
+    return subtotal + order.tax
"""

    assert extract_changed_symbols(diff, "src/payments.py") == ["calculate_total"]


def test_tc_044_extracts_the_enclosing_csharp_symbol_from_unmodified_hunk_context() -> None:
    """TC-044 / DoD-1.6: method-body changes retain their C# method symbol.

    Steps:
      1. Provide a diff that changes only a line inside a C# method.
      2. Read the unified-diff hunk context naming that method.
      3. Verify direct test discovery receives the enclosing symbol.
    """
    diff = """diff --git a/src/Payments.cs b/src/Payments.cs
+++ b/src/Payments.cs
@@ -20,7 +20,7 @@ public decimal CalculateTotal(Order order)
 {
-    return order.Subtotal;
+    return order.Subtotal + order.Tax;
 }
"""

    assert extract_changed_symbols(diff, "src/Payments.cs") == ["CalculateTotal"]


def test_tc_014_discovers_direct_tests_and_reports_unit_testing_advisory_when_absent(tmp_path: Path) -> None:
    """TC-014 / DoD-1.6: direct tests are mapped, while absent tests stay advisory.

    Steps:
      1. Create a production file and a direct unit-test file that names one changed symbol.
      2. Discover tests for that symbol and verify the direct mapping.
      3. Discover tests for an untested symbol and verify a unit-testing advisory, not a defect.
    """
    # Arrange
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "payments.py").write_text("def calculate_total(): pass\ndef untested(): pass\n")
    test_path = tmp_path / "tests" / "test_payments.py"
    test_path.write_text("def test_calculate_total():\n    assert True\n")

    # Act
    covered = discover_tests(tmp_path, ["src/payments.py"], ["calculate_total"])
    uncovered = discover_tests(tmp_path, ["src/payments.py"], ["untested"])

    # Assert
    assert covered["directTests"] == [str(test_path.relative_to(tmp_path))]
    assert uncovered["directTests"] == []
    assert uncovered["advisory"] == "use-unit-testing"
    assert uncovered["status"] == "advisory"


def test_tc_015_runs_test_command_with_deterministic_evidence_fields(tmp_path: Path) -> None:
    """TC-015 / DoD-1.6: test execution records bounded, machine-readable evidence.

    Steps:
      1. Run a deterministic command that writes one line and exits with a known code.
      2. Capture the test-gate result.
      3. Verify command, exit status, duration, counts, and bounded logs are present.
    """
    # Arrange
    command = [sys.executable, "-c", "print('1 passed'); raise SystemExit(0)"]

    # Act
    result = run_test_command(command, tmp_path, log_limit=100)

    # Assert
    assert result["command"] == command
    assert result["exitCode"] == 0
    assert result["durationMs"] >= 0
    assert result["counts"] == {"passed": 1, "failed": 0, "skipped": 0}
    assert result["stdout"] == "1 passed\n"


def test_tc_045_treats_a_normal_exit_code_124_as_a_failed_test_command(tmp_path: Path) -> None:
    """TC-045 / DoD-1.6: only a real subprocess timeout receives timeout status.

    Steps:
      1. Run a command which exits normally with code 124.
      2. Capture the test-gate result.
      3. Verify the process is reported as failed, not as a timeout.
    """
    command = [sys.executable, "-c", "raise SystemExit(124)"]

    result = run_test_command(command, tmp_path)

    assert result["exitCode"] == 124
    assert result["status"] == "fail"


def test_tc_047_parses_dotnet_summary_counts(tmp_path: Path) -> None:
    """TC-047 / DoD-1.6: standard .NET test summaries produce exact counts.

    Steps:
      1. Run a successful command that emits a standard .NET summary.
      2. Capture its evidence through the test gate.
      3. Verify passed, failed, and skipped counts are parsed from label-first fields.
    """
    command = [
        sys.executable,
        "-c",
        "print('Failed: 0, Passed: 10, Skipped: 1'); raise SystemExit(0)",
    ]

    result = run_test_command(command, tmp_path)

    assert result["counts"] == {"passed": 10, "failed": 0, "skipped": 1}


def test_tc_048_parses_successful_python_unittest_summary_counts(tmp_path: Path) -> None:
    """TC-048 / DoD-1.6: successful Python unittest summaries report their test total.

    Steps:
      1. Run a successful command that emits the standard unittest completion summary.
      2. Capture its evidence through the test gate.
      3. Verify the ran-test count is recorded as passed tests.
    """
    command = [sys.executable, "-c", "print('Ran 5 tests'); print('OK')"]

    result = run_test_command(command, tmp_path)

    assert result["counts"] == {"passed": 5, "failed": 0, "skipped": 0}


def test_tc_049_parses_failed_python_unittest_summary_counts(tmp_path: Path) -> None:
    """TC-049 / DoD-1.6: failed Python unittest summaries retain exact failure totals.

    Steps:
      1. Run a command that emits a unittest run count and failure/error totals.
      2. Capture its evidence through the test gate.
      3. Verify passed, failed, and skipped counts are derived deterministically.
    """
    command = [
        sys.executable,
        "-c",
        "print('Ran 5 tests'); print('FAILED (failures=2, errors=1)'); raise SystemExit(1)",
    ]

    result = run_test_command(command, tmp_path)

    assert result["counts"] == {"passed": 2, "failed": 3, "skipped": 0}
