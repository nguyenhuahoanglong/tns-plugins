#!/usr/bin/env python3
"""
publish_state.py — read/write/diff the publish state file.

Usage:
    publish_state.py read <state-path>
    publish_state.py write <state-path> --json <state.json>
    publish_state.py init <state-path> --wi <id> --branch <name> [other fields via --field key=value]
    publish_state.py diff <state-path> <new-report.md>

`diff` runs parse_must_fix.py internally and emits:
    {"resolved": [...], "remaining": [...], "new": [...], "resolved_count": n, "total_count": m, "remaining_count": k}

Exit codes:
  0 — success
  2 — file/IO error
  3 — invalid JSON / missing required fields
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone


def cmd_read(args):
    p = Path(args.state)
    if not p.exists():
        print(f"State not found: {p}", file=sys.stderr)
        sys.exit(2)
    print(p.read_text(encoding="utf-8"))


def cmd_write(args):
    if args.json:
        try:
            data = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}", file=sys.stderr)
            sys.exit(3)
    elif args.json_file:
        try:
            data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Invalid JSON file: {exc}", file=sys.stderr)
            sys.exit(3)
    else:
        # Read from stdin
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON on stdin: {exc}", file=sys.stderr)
            sys.exit(3)

    p = Path(args.state)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic-ish write
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)
    print(f"Wrote {p}")


def cmd_init(args):
    fields = {}
    for raw in (args.field or []):
        if "=" not in raw:
            print(f"Invalid --field (need key=value): {raw}", file=sys.stderr)
            sys.exit(3)
        k, v = raw.split("=", 1)
        fields[k] = v
    state = {
        "wiId": args.wi,
        "branch": args.branch,
        "iteration": 1,
        "postedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mustFixSlugs": [],
        **fields,
    }
    p = Path(args.state)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state, indent=2))


def parse_must_fix_via_helper(report_path: Path):
    """Invoke sibling parse_must_fix.py and return parsed JSON."""
    helper = Path(__file__).parent / "parse_must_fix.py"
    if not helper.exists():
        print(f"Sibling helper not found: {helper}", file=sys.stderr)
        sys.exit(2)
    result = subprocess.run(
        [sys.executable, str(helper), str(report_path)],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return json.loads(result.stdout)


def cmd_diff(args):
    state_path = Path(args.state)
    if not state_path.exists():
        print(f"State not found: {state_path}", file=sys.stderr)
        sys.exit(2)
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        sys.exit(2)

    try:
        prior = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"State file invalid JSON: {exc}", file=sys.stderr)
        sys.exit(3)

    prior_slugs = set(prior.get("mustFixSlugs") or [])
    parsed = parse_must_fix_via_helper(report_path)
    new_slugs = set(item["slug"] for item in parsed["mustFix"])

    resolved = sorted(prior_slugs - new_slugs)
    remaining = sorted(prior_slugs & new_slugs)
    new_items = sorted(new_slugs - prior_slugs)

    out = {
        "resolved": resolved,
        "remaining": remaining,
        "new": new_items,
        "resolved_count": len(resolved),
        "total_count": len(prior_slugs),
        "remaining_count": len(remaining),
        "newReportSlugs": sorted(new_slugs),
        "newReportBuildStatus": parsed["buildStatus"],
        "newReportCounts": parsed["counts"],
    }
    print(json.dumps(out, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_read = sub.add_parser("read")
    p_read.add_argument("state")
    p_read.set_defaults(func=cmd_read)

    p_write = sub.add_parser("write")
    p_write.add_argument("state")
    p_write.add_argument("--json", default=None, help="Inline JSON string")
    p_write.add_argument("--json-file", default=None, help="Path to JSON file")
    p_write.set_defaults(func=cmd_write)

    p_init = sub.add_parser("init")
    p_init.add_argument("state")
    p_init.add_argument("--wi", type=int, required=True)
    p_init.add_argument("--branch", required=True)
    p_init.add_argument("--field", action="append", default=[], help="extra key=value (repeatable)")
    p_init.set_defaults(func=cmd_init)

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("state")
    p_diff.add_argument("report")
    p_diff.set_defaults(func=cmd_diff)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
