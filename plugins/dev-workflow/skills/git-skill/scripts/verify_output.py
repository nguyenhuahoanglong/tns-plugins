"""Read-only self-verification for structured git-skill results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from git_skill import CliResult, emit_result


_REQUIRED_FIELDS = {"status", "exit_code", "header", "message", "details"}


def verify_result(
    result: object,
    *,
    repository: Path,
    expected_files: Sequence[str] = (),
    expected_work_items: Sequence[str] = (),
    dry_run: bool = False,
) -> CliResult:
    """Validate result evidence without running Git, Azure, or filesystem writes."""

    if not isinstance(result, dict) or not _REQUIRED_FIELDS <= result.keys():
        return CliResult("ERROR", 1, "VERIFY", "Result schema is incomplete.")
    if (not isinstance(result["status"], str) or not isinstance(result["exit_code"], int)
            or isinstance(result["exit_code"], bool) or not isinstance(result["header"], str)
            or not isinstance(result["message"], str) or not isinstance(result["details"], dict)):
        return CliResult("ERROR", 1, "VERIFY", "Result schema has invalid field types.")

    details = result["details"]
    actual_files = {str(item) for item in details.get("touched_files", [])}
    actual_work_items = {str(item) for item in details.get("work_item_ids", [])}
    missing_files = [item for item in expected_files if item not in actual_files]
    missing_work_items = [item for item in expected_work_items if item not in actual_work_items]
    if missing_files or missing_work_items:
        missing = [*missing_files, *missing_work_items]
        return CliResult("ERROR", 1, "VERIFY", f"Missing verification evidence: {', '.join(missing)}")
    if (dry_run or details.get("dry_run") is True) and details.get("mutated") is True:
        return CliResult("ERROR", 1, "VERIFY", "Dry-run result reports a mutation.")
    return CliResult("OK", 0, "VERIFY", "Result verification completed.", {"repository": str(repository), "mutated": False})


def handle_verify(args: argparse.Namespace) -> CliResult:
    try:
        result = json.loads(args.result)
    except (TypeError, json.JSONDecodeError):
        return CliResult("ERROR", 1, "VERIFY", "--result must be valid JSON.")
    return verify_result(
        result,
        repository=Path(args.repository).resolve() if args.repository else Path.cwd(),
        expected_files=args.expected_file,
        expected_work_items=args.work_item,
        dry_run=args.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the verifier parser without performing repository inspection."""

    parser = argparse.ArgumentParser(
        prog="verify_output.py",
        description="Verify git-skill command results without initiating mutations.",
    )
    parser.add_argument("--repository", help="Repository path to verify.")
    parser.add_argument("--result", required=True, help="Structured result JSON to verify.")
    parser.add_argument("--expected-file", action="append", default=[], help="Expected touched file.")
    parser.add_argument("--work-item", action="append", default=[], help="Expected linked work item.")
    parser.add_argument("--dry-run", action="store_true", help="Assert dry-run invariants.")
    parser.set_defaults(handler=handle_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.handler(args)
    emit_result(result)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
