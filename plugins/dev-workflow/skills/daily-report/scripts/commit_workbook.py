#!/usr/bin/env python3
"""Optional, workbook-only Git backup for the portable daily-report state."""
import argparse
import subprocess
from pathlib import Path

from lib_common import load_config


def _default_runner(argv):
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _result(value):
    if isinstance(value, dict):
        return value
    return {"returncode": value.returncode, "stdout": value.stdout, "stderr": value.stderr}


def _run(runner, argv):
    result = _result(runner(argv))
    if result.get("returncode", 0) != 0:
        raise RuntimeError(result.get("stderr") or result.get("stdout") or "Git command failed")
    return result


def backup_workbook(config, runner=_default_runner, message="chore: update daily task workbook"):
    """Optionally stage and commit only the configured workbook using argv Git calls."""
    backup = config.get("backup", {})
    if not backup.get("enabled", False):
        return {"status": "SKIP", "code": "BACKUP_DISABLED"}
    workbook = Path(config["excel"]["path"]).expanduser().resolve()
    repo = backup.get("repo")
    if not repo:
        return {"status": "SKIP", "code": "OUTSIDE_CONFIGURED_REPO"}
    repo = Path(repo).expanduser().resolve()
    try:
        relative = workbook.relative_to(repo).as_posix()
    except ValueError:
        return {"status": "SKIP", "code": "OUTSIDE_CONFIGURED_REPO"}

    prefix = ["git", "-C", str(repo)]
    try:
        _run(runner, [*prefix, "add", "--", relative])
        changed = _result(runner([*prefix, "diff", "--cached", "--quiet", "--", relative]))
        if changed.get("returncode", 0) == 0:
            return {"status": "SKIP", "code": "NO_WORKBOOK_CHANGES", "path": relative}
        if changed.get("returncode") != 1:
            raise RuntimeError(changed.get("stderr") or "Unable to inspect staged workbook")
        _run(runner, [*prefix, "commit", "--only", "-m", message, "--", relative])
        commit = _run(runner, [*prefix, "rev-parse", "--short", "HEAD"])["stdout"].strip()
        return {"status": "COMMITTED", "path": relative, "commit": commit}
    except RuntimeError as error:
        return {"status": "FAIL", "code": "BACKUP_FAILED", "message": str(error)}


# Legacy public API retained for callers that provide a workbook path directly.
def run_git(cwd, *args, check=True):
    result = subprocess.run(["git", "-C", str(cwd), *args], check=False, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if check and result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result


def find_repo_root(workbook_path):
    return Path(run_git(Path(workbook_path).parent, "rev-parse", "--show-toplevel").stdout.strip())


def commit_workbook(workbook_path, message):
    workbook = Path(workbook_path).resolve()
    repo = find_repo_root(workbook)
    try:
        relative = workbook.relative_to(repo).as_posix()
    except ValueError as error:
        raise SystemExit(f"ERROR: workbook is outside Git repo: {workbook}") from error
    result = backup_workbook({"excel": {"path": str(workbook)}, "backup": {"enabled": True, "repo": str(repo)}},
                             runner=lambda argv: run_git(argv[2], *argv[3:], check=False), message=message)
    if result["status"] == "FAIL":
        raise SystemExit(result["message"])
    if result["status"] == "SKIP":
        print("=== WORKBOOK COMMIT ===")
        print(f"SKIP: no workbook changes to commit ({relative})")
        return None
    print("=== WORKBOOK COMMIT ===")
    print(f"COMMIT: {result['commit']} {message}")
    print(f"FILE: {relative}")
    return result["commit"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--message", default="chore: update daily task workbook")
    args = parser.parse_args()
    config = load_config(args.config)
    result = backup_workbook(config, message=args.message)
    print("=== WORKBOOK BACKUP ===")
    print(result)
    if result["status"] == "FAIL":
        raise SystemExit(result["code"])


if __name__ == "__main__":
    main()
