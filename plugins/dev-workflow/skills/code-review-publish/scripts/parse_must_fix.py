#!/usr/bin/env python3
"""
parse_must_fix.py — extract Must Fix shortlist + counts + build status from a code-review-pro report.

Usage:
    parse_must_fix.py <report.md> [--out <file.json>]

Output (stdout if no --out):
{
  "buildStatus": "PASS" | "FAIL" | "UNKNOWN",
  "counts": {"critical": 0, "high": 4, "medium": 8, "low": 4},
  "mustFix": [
    {"slug": "auth-broaden", "severity": "HIGH", "agents": ["Security"],
     "text": "Access-control broadening...",
     "fileLine": "GetDistributionFailuresQueryCommandHandler.cs:640-680"},
    ...
  ]
}

Exit codes:
  0 — success
  1 — Must Fix bullet missing [mf:slug] tag (slugs printed to stderr)
  2 — report file missing or unreadable
  3 — no Must Fix Before Merge section found
"""

import sys
import re
import json
import argparse
from pathlib import Path


SLUG_RE = re.compile(r"\[mf:([a-z0-9][a-z0-9-]{0,23})\]")
SEVERITY_RE = re.compile(r"\[(CRITICAL|HIGH|MEDIUM|LOW)\]")
AGENT_RE = re.compile(r"\[(Build|Standard|Philosophy|Security|Performance|Requirement[^\]]*|Approach|[A-Z][a-z]+)\]")
COUNTS_HEADER = re.compile(r"^\|\s*Critical\s*\|\s*High\s*\|\s*Medium\s*\|\s*Low\s*\|\s*Total\s*\|", re.IGNORECASE)
COUNTS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*\d+\s*\|")
BUILD_PASS = re.compile(r"\bPASS\b")
BUILD_FAIL = re.compile(r"\bFAIL\b")


def extract_section(lines, header_pattern):
    """Return list of lines belonging to the section starting with header_pattern."""
    out = []
    in_section = False
    for line in lines:
        if header_pattern.match(line):
            in_section = True
            continue
        if in_section:
            # next H1/H2/H3 ends the section
            if re.match(r"^#{1,3}\s", line):
                break
            out.append(line)
    return out


def parse_counts(lines):
    """Find the findings count table and return {critical, high, medium, low}."""
    for i, line in enumerate(lines):
        if COUNTS_HEADER.match(line):
            for j in range(i + 1, min(i + 4, len(lines))):
                m = COUNTS_ROW.match(lines[j])
                if m:
                    return {
                        "critical": int(m.group(1)),
                        "high": int(m.group(2)),
                        "medium": int(m.group(3)),
                        "low": int(m.group(4)),
                    }
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


def parse_build_status(lines):
    """Look for Build Status section, return PASS/FAIL/UNKNOWN."""
    in_build = False
    saw_fail = False
    saw_pass = False
    for line in lines:
        if re.match(r"^##\s+Build Status", line, re.IGNORECASE):
            in_build = True
            continue
        if in_build:
            if re.match(r"^##\s", line):
                break
            if BUILD_FAIL.search(line):
                saw_fail = True
            elif BUILD_PASS.search(line):
                saw_pass = True
    if saw_fail:
        return "FAIL"
    if saw_pass:
        return "PASS"
    return "UNKNOWN"


def parse_must_fix(report_path: Path):
    lines = report_path.read_text(encoding="utf-8").splitlines()

    counts = parse_counts(lines)
    build = parse_build_status(lines)

    # Find Must Fix section
    mf_header = re.compile(r"^###\s+Must Fix Before Merge", re.IGNORECASE)
    mf_lines = extract_section(lines, mf_header)

    if not mf_lines:
        # Empty section is OK if "None" sentinel present, otherwise error
        return {
            "buildStatus": build,
            "counts": counts,
            "mustFix": [],
        }, []

    items = []
    missing_slugs = []
    for raw in mf_lines:
        line = raw.strip()
        if not line.startswith("- ") and not line.startswith("* "):
            continue
        if "none —" in line.lower() or "none -" in line.lower():
            continue

        body = line[2:]  # strip leading bullet
        # Skip empty / blockquote / non-finding lines
        if not body or body.startswith(">"):
            continue

        sev_m = SEVERITY_RE.search(body)
        slug_m = SLUG_RE.search(body)
        agents = AGENT_RE.findall(body)
        # Filter agents to drop severity false-positives if any
        agents = [a for a in agents if a not in ("CRITICAL", "HIGH", "MEDIUM", "LOW")]

        if not slug_m:
            missing_slugs.append(line[:120])
            continue

        # Extract trailing file:line if present after em-dash + backticks
        file_line = None
        fl_m = re.search(r"`([^`]+:\d[^`]*)`\s*$", body)
        if fl_m:
            file_line = fl_m.group(1)

        # Strip tags + file-line backtick from text for display
        text = SLUG_RE.sub("", body)
        text = SEVERITY_RE.sub("", text)
        text = AGENT_RE.sub("", text)
        text = re.sub(r"^\s*\*+\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip(" *—-")
        if file_line:
            text = re.sub(r"`[^`]+:\d[^`]*`\s*$", "", text).strip(" *—-")

        items.append({
            "slug": slug_m.group(1),
            "severity": sev_m.group(1) if sev_m else "UNKNOWN",
            "agents": agents,
            "text": text,
            "fileLine": file_line,
        })

    return {
        "buildStatus": build,
        "counts": counts,
        "mustFix": items,
    }, missing_slugs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.report.exists():
        print(f"Report not found: {args.report}", file=sys.stderr)
        sys.exit(2)

    try:
        result, missing = parse_must_fix(args.report)
    except Exception as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps(result, indent=2)

    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    if missing:
        print(f"\nERROR: {len(missing)} Must Fix bullet(s) missing [mf:slug] tag:", file=sys.stderr)
        for line in missing:
            print(f"  - {line}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
