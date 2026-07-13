"""Spec-first tests for build_gate.py.

Requirement -> test mapping (spec-first):
- successful/warning/failing builds -> TestExecuteBuild status tests
- missing repo/executable and timeout -> TestExecuteBuild infrastructure status tests
- dry-run, exact approved command, no install -> TestExecuteBuild safety tests
- UTF-8 replacement and log creation -> TestExecuteBuild output tests
- diagnostic cap and omitted counts -> TestExecuteBuild diagnostic test
- CLI exit codes 0/1/2 -> TestMain exit-code tests
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "build_gate.py"
SPEC = importlib.util.spec_from_file_location("build_gate", SCRIPT)
BUILD_GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_GATE)


class RecordingRunner:
    """Deterministic subprocess boundary used by execute_build tests."""

    def __init__(self, returncode=0, stdout=b"", stderr=b"", side_effect=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.side_effect = side_effect
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.side_effect is not None:
            raise self.side_effect
        return subprocess.CompletedProcess(
            args=command,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


class TestExecuteBuild(unittest.TestCase):
    def execute(self, root, runner, command=None, dry_run=False, timeout=30):
        command = command or ["python", "-m", "unittest"]
        return BUILD_GATE.execute_build(
            repo=root,
            command=command,
            timeout_seconds=timeout,
            log_path=Path(root) / "artifacts" / "build.log",
            runner=runner,
            dry_run=dry_run,
        )

    def test_returns_pass_when_command_succeeds_without_warnings(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(root, RecordingRunner(stdout=b"Build succeeded\n"))

        self.assertEqual("PASS", result["status"])
        self.assertEqual(0, result["exitCode"])
        self.assertEqual([], result["errors"])
        self.assertEqual([], result["warnings"])

    def test_returns_pass_with_warnings_when_command_succeeds_with_warning(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(
                root,
                RecordingRunner(stdout=b"warning CS0618: obsolete API\nBuild succeeded\n"),
            )

        self.assertEqual("PASS WITH WARNINGS", result["status"])
        self.assertEqual(0, result["exitCode"])
        self.assertEqual(["warning CS0618: obsolete API"], result["warnings"])

    def test_returns_fail_when_command_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(
                root,
                RecordingRunner(returncode=1, stderr=b"error CS1002: ; expected\n"),
            )

        self.assertEqual("FAIL", result["status"])
        self.assertEqual(1, result["exitCode"])
        self.assertEqual(["error CS1002: ; expected"], result["errors"])

    def test_missing_repo_returns_not_run_environment_without_running_command(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner()
            missing = Path(root) / "missing"
            result = BUILD_GATE.execute_build(
                missing,
                ["python", "-m", "unittest"],
                30,
                Path(root) / "build.log",
                runner=runner,
            )

        self.assertEqual("NOT RUN (environment)", result["status"])
        self.assertEqual(2, result["exitCode"])
        self.assertIn("repository", result["reason"].lower())
        self.assertEqual([], runner.calls)

    def test_missing_executable_returns_not_run_environment_without_install_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner(side_effect=FileNotFoundError("missing-build-tool"))
            command = ["missing-build-tool", "build"]
            result = self.execute(root, runner, command=command)

        self.assertEqual("NOT RUN (environment)", result["status"])
        self.assertEqual(2, result["exitCode"])
        self.assertIn("missing-build-tool", result["reason"])
        self.assertEqual(1, len(runner.calls))
        self.assertNotIn("install", " ".join(runner.calls[0][0]).lower())

    def test_timeout_returns_not_run_timeout(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner(
                side_effect=subprocess.TimeoutExpired(cmd="build", timeout=7)
            )
            result = self.execute(root, runner, timeout=7)

        self.assertEqual("NOT RUN (timeout)", result["status"])
        self.assertEqual(2, result["exitCode"])
        self.assertIn("timeout", result["reason"].lower())
        self.assertIn("7", result["reason"])

    def test_dry_run_returns_pass_without_invoking_runner(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner()
            command = ["dotnet", "build", "Project.sln", "--no-restore"]
            result = self.execute(root, runner, command=command, dry_run=True)

        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["dryRun"])
        self.assertEqual(command, result["command"])
        self.assertEqual([], runner.calls)

    def test_passes_approved_command_unchanged_and_never_installs(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner()
            command = ["dotnet", "build", "Project.sln", "--no-restore"]
            result = self.execute(root, runner, command=command)

        self.assertEqual(command, result["command"])
        self.assertEqual(command, runner.calls[0][0])
        self.assertEqual(str(Path(root)), str(runner.calls[0][1]["cwd"]))
        self.assertEqual(30, runner.calls[0][1]["timeout"])
        self.assertEqual(1, len(runner.calls))
        self.assertNotIn("install", " ".join(runner.calls[0][0]).lower())

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell adapter")
    def test_adapts_real_powershell_command_shape_without_shell(self):
        with tempfile.TemporaryDirectory() as root:
            runner = RecordingRunner()
            command = '& "C:\\Program Files\\nodejs\\npm.ps1" --prefix "C:\\repo" test'
            result = self.execute(root, runner, command=command)

        invoked, options = runner.calls[0]
        self.assertEqual(command, result["command"])
        self.assertEqual("powershell.exe", invoked[0])
        self.assertEqual("-Command", invoked[-2])
        self.assertEqual(command, invoked[-1])
        self.assertIs(False, options["shell"])

    def test_zero_count_summaries_are_not_diagnostics(self):
        output = b"Build succeeded.\n    0 Warning(s)\n    0 Error(s)\n"
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(root, RecordingRunner(stdout=output))

        self.assertEqual("PASS", result["status"])
        self.assertEqual(0, result["totalErrorCount"])
        self.assertEqual(0, result["totalWarningCount"])

    def test_invalid_utf8_is_decoded_with_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(root, RecordingRunner(stdout=b"ok\xffdone\n"))

        self.assertIn("ok\ufffddone", result["output"])

    def test_creates_parent_directory_and_full_log(self):
        with tempfile.TemporaryDirectory() as root:
            log_path = Path(root) / "new" / "nested" / "build.log"
            output = b"line one\nwarning W001: caution\n"
            result = BUILD_GATE.execute_build(
                root,
                ["python", "-m", "unittest"],
                30,
                log_path,
                runner=RecordingRunner(stdout=output),
            )

            self.assertTrue(log_path.is_file())
            self.assertEqual(output.decode("utf-8"), log_path.read_text(encoding="utf-8"))
            self.assertEqual(str(log_path), result["logPath"])

    def test_caps_error_and_warning_diagnostics_and_reports_omitted_counts(self):
        errors = [f"error E{i:02d}: broken" for i in range(12)]
        warnings = [f"warning W{i:02d}: caution" for i in range(13)]
        output = ("\n".join(errors + warnings) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as root:
            result = self.execute(root, RecordingRunner(returncode=1, stdout=output))

        self.assertEqual(errors[:10], result["errors"])
        self.assertEqual(warnings[:10], result["warnings"])
        self.assertEqual(2, result["omittedErrorCount"])
        self.assertEqual(3, result["omittedWarningCount"])


class TestMain(unittest.TestCase):
    def invoke(self, root, execute_result):
        argv = [
            "--repo", str(root),
            "--command", "python -m unittest",
            "--timeout", "30",
            "--log", str(Path(root) / "build.log"),
        ]
        output = io.StringIO()
        with mock.patch.object(BUILD_GATE, "execute_build", return_value=execute_result):
            with contextlib.redirect_stdout(output):
                exit_code = BUILD_GATE.main(argv)
        return exit_code, json.loads(output.getvalue())

    def test_cli_returns_zero_for_pass(self):
        with tempfile.TemporaryDirectory() as root:
            exit_code, payload = self.invoke(root, {"status": "PASS"})

        self.assertEqual(0, exit_code)
        self.assertEqual("PASS", payload["status"])

    def test_cli_returns_zero_for_pass_with_warnings(self):
        with tempfile.TemporaryDirectory() as root:
            exit_code, _ = self.invoke(root, {"status": "PASS WITH WARNINGS"})

        self.assertEqual(0, exit_code)

    def test_cli_returns_one_for_build_failure(self):
        with tempfile.TemporaryDirectory() as root:
            exit_code, payload = self.invoke(root, {"status": "FAIL", "exitCode": 1})

        self.assertEqual(1, exit_code)
        self.assertEqual("FAIL", payload["status"])

    def test_cli_returns_two_for_invalid_arguments(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            exit_code = BUILD_GATE.main([])

        self.assertEqual(2, exit_code)
        self.assertTrue(error.getvalue())


if __name__ == "__main__":
    unittest.main()
