#!/usr/bin/env python3
"""Run one approved build command and emit a bounded structured result."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


DIAGNOSTIC_LIMIT = 10
OUTPUT_LIMIT = 20_000
ERROR_PATTERN = re.compile(r"\berror\b", re.IGNORECASE)
WARNING_PATTERN = re.compile(r"\bwarning\b", re.IGNORECASE)
ZERO_DIAGNOSTIC_SUMMARY = re.compile(
    r"^0\s+(?:warning|error)\(s\)\s*$", re.IGNORECASE
)


def configure_utf8_console():
    """Keep console output deterministic when build output contains invalid text."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _decode(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _combine_output(stdout, stderr):
    output = _decode(stdout)
    error_output = _decode(stderr)
    if output and error_output and not output.endswith(("\n", "\r")):
        output += "\n"
    return output + error_output


def _write_log(log_path, output):
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="replace", newline="") as stream:
        stream.write(output)


def _diagnostics(output):
    errors = []
    warnings = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ZERO_DIAGNOSTIC_SUMMARY.fullmatch(line):
            continue
        if ERROR_PATTERN.search(line):
            errors.append(line)
        elif WARNING_PATTERN.search(line):
            warnings.append(line)
    return errors, warnings


def _execution_command(command, platform_name=None):
    """Adapt a CLI command string without invoking a platform shell implicitly."""
    if not isinstance(command, str):
        return command
    platform_name = platform_name or os.name
    if platform_name == "nt":
        return [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
    return shlex.split(command)


def _result(
    status,
    command,
    log_path,
    output="",
    reason="",
    exit_code=0,
    command_exit_code=None,
    dry_run=False,
):
    errors, warnings = _diagnostics(output)
    return {
        "status": status,
        "command": command,
        "exitCode": exit_code,
        "commandExitCode": command_exit_code,
        "totalErrorCount": len(errors),
        "totalWarningCount": len(warnings),
        "errors": errors[:DIAGNOSTIC_LIMIT],
        "warnings": warnings[:DIAGNOSTIC_LIMIT],
        "omittedErrorCount": max(0, len(errors) - DIAGNOSTIC_LIMIT),
        "omittedWarningCount": max(0, len(warnings) - DIAGNOSTIC_LIMIT),
        "reason": reason,
        "logPath": str(Path(log_path)),
        "dryRun": dry_run,
        "output": output[:OUTPUT_LIMIT],
        "outputTruncated": len(output) > OUTPUT_LIMIT,
    }


def execute_build(repo, command, timeout_seconds, log_path, runner=None, dry_run=False):
    """Execute exactly one approved command without restore or installation logic."""
    repo_path = Path(repo)
    run_command = _execution_command(command)
    runner = runner or subprocess.run

    if not repo_path.is_dir():
        reason = f"Repository does not exist or is not a directory: {repo_path}"
        _write_log(log_path, reason + "\n")
        return _result(
            "NOT RUN (environment)", command, log_path, reason=reason, exit_code=2,
            dry_run=dry_run,
        )
    if not command:
        reason = "Approved build command is empty"
        _write_log(log_path, reason + "\n")
        return _result(
            "NOT RUN (environment)", command, log_path, reason=reason, exit_code=2,
            dry_run=dry_run,
        )
    if timeout_seconds <= 0:
        reason = "Timeout must be greater than zero seconds"
        _write_log(log_path, reason + "\n")
        return _result(
            "NOT RUN (environment)", command, log_path, reason=reason, exit_code=2,
            dry_run=dry_run,
        )
    if dry_run:
        _write_log(log_path, "")
        return _result(
            "PASS",
            command,
            log_path,
            reason="Dry run: approved command not executed",
            dry_run=True,
        )

    try:
        completed = runner(
            run_command,
            cwd=repo_path,
            timeout=timeout_seconds,
            capture_output=True,
            shell=False,
        )
        output = _combine_output(completed.stdout, completed.stderr)
        _write_log(log_path, output)
    except subprocess.TimeoutExpired as exc:
        output = _combine_output(exc.stdout, exc.stderr)
        _write_log(log_path, output)
        reason = f"Build command timeout after {timeout_seconds} seconds"
        return _result(
            "NOT RUN (timeout)", command, log_path, output, reason, exit_code=2,
        )
    except OSError as exc:
        reason = f"Build environment unavailable: {exc}"
        _write_log(log_path, reason + "\n")
        return _result(
            "NOT RUN (environment)", command, log_path, reason=reason, exit_code=2,
        )

    command_exit_code = completed.returncode
    if command_exit_code != 0:
        return _result(
            "FAIL",
            command,
            log_path,
            output,
            f"Approved build command exited with code {command_exit_code}",
            exit_code=1,
            command_exit_code=command_exit_code,
        )

    _errors, warnings = _diagnostics(output)
    if warnings:
        return _result(
            "PASS WITH WARNINGS",
            command,
            log_path,
            output,
            "Approved build command completed with warnings",
            command_exit_code=command_exit_code,
        )
    return _result(
        "PASS",
        command,
        log_path,
        output,
        "Approved build command completed successfully",
        command_exit_code=command_exit_code,
    )


def main(argv=None):
    """Parse CLI input, execute the build gate, and return its stable exit code."""
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Absolute worktree path")
    parser.add_argument("--command", required=True, help="One approved build command")
    parser.add_argument(
        "--timeout-seconds", "--timeout", dest="timeout_seconds", type=int,
        required=True, help="Command timeout in seconds",
    )
    parser.add_argument("--log", required=True, help="Absolute full-log path")
    parser.add_argument("--json", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--dry-run", action="store_true", help="Validate without execution")
    try:
        args = parser.parse_args(argv)
        if args.timeout_seconds <= 0:
            parser.error("--timeout-seconds must be greater than zero")
        if not args.command.strip():
            parser.error("--command must not be empty")
    except SystemExit as exc:
        return int(exc.code)

    data = execute_build(
        repo=Path(args.repo),
        command=args.command,
        timeout_seconds=args.timeout_seconds,
        log_path=Path(args.log),
        dry_run=args.dry_run,
    )
    indent = 2 if args.json else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))
    if "exitCode" in data:
        return data["exitCode"]
    if data.get("status") in {"PASS", "PASS WITH WARNINGS"}:
        return 0
    if data.get("status") == "FAIL":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
