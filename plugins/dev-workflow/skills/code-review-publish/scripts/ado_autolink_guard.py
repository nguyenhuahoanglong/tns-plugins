#!/usr/bin/env python3
"""
ado_autolink_guard.py - prevent accidental Azure DevOps #number autolinks.

ADO renders raw #123 as a work-item link. Code-review reports should keep raw
#number only when the text explicitly intends a work-item reference.

Usage:
    ado_autolink_guard.py check <file>
    ado_autolink_guard.py fix <file>
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


RAW_HASH_RE = re.compile(r"(?<!\\)#\d+\b")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
ALLOWED_CONTEXT_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:work\s*item|parent|wi|ado)\s*[:\-]?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    line: int
    column: int
    token: str
    text: str


def _inline_code_mask(line: str) -> list[bool]:
    mask = [False] * len(line)
    i = 0
    while i < len(line):
        if line[i] != "`":
            i += 1
            continue
        tick_count = 1
        while i + tick_count < len(line) and line[i + tick_count] == "`":
            tick_count += 1
        end = line.find("`" * tick_count, i + tick_count)
        if end == -1:
            break
        for j in range(i, end + tick_count):
            mask[j] = True
        i = end + tick_count
    return mask


def _normalise_context(text: str) -> str:
    # Keep words and separators, drop markdown emphasis/link punctuation.
    text = re.sub(r"[*_`[\]()>]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_allowed_context(line: str, start: int) -> bool:
    prefix = _normalise_context(line[max(0, start - 80):start])
    return bool(ALLOWED_CONTEXT_RE.search(prefix))


def _line_issues(line: str, line_no: int, in_fence: bool) -> list[Issue]:
    if in_fence:
        return []

    mask = _inline_code_mask(line)
    issues: list[Issue] = []
    for match in RAW_HASH_RE.finditer(line):
        if any(mask[match.start():match.end()]):
            continue
        if _is_allowed_context(line, match.start()):
            continue
        issues.append(Issue(
            line=line_no,
            column=match.start() + 1,
            token=match.group(0),
            text=line.rstrip("\n"),
        ))
    return issues


def find_issues(text: str) -> list[Issue]:
    issues: list[Issue] = []
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        issues.extend(_line_issues(line, line_no, in_fence))
    return issues


def _fix_line(line: str, in_fence: bool) -> tuple[str, int]:
    issues = _line_issues(line, 0, in_fence)
    if not issues:
        return line, 0

    fixed = line
    offset = 0
    for issue in issues:
        index = issue.column - 1 + offset
        fixed = fixed[:index] + "\\" + fixed[index:]
        offset += 1
    return fixed, len(issues)


def fix_text(text: str) -> tuple[str, int]:
    keep_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    fixed_lines: list[str] = []
    fixes = 0
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            fixed_lines.append(line)
            in_fence = not in_fence
            continue
        fixed, count = _fix_line(line, in_fence)
        fixed_lines.append(fixed)
        fixes += count
    fixed_text = "\n".join(fixed_lines)
    if keep_trailing_newline:
        fixed_text += "\n"
    return fixed_text, fixes


def check_file(path: Path) -> list[Issue]:
    return find_issues(path.read_text(encoding="utf-8"))


def fix_file(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    fixed, fixes = fix_text(original)
    if fixes and fixed != original:
        path.write_text(fixed, encoding="utf-8")
    return fixes


def _print_issues(path: Path, issues: list[Issue]) -> None:
    print(f"Unsafe ADO #number references in {path}:")
    for issue in issues:
        print(f"  {issue.line}:{issue.column} {issue.token}  {issue.text}")
    print("\nUse raw #number only for intentional work-item links.")
    print("Run: ado_autolink_guard.py fix <file>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard ADO #number autolinks")
    parser.add_argument("mode", choices=("check", "fix"))
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"not found: {args.file}", file=sys.stderr)
        return 2

    if args.mode == "fix":
        fixes = fix_file(args.file)
        print(f"fixed {fixes} unsafe #number reference(s) in {args.file}")

    issues = check_file(args.file)
    if issues:
        _print_issues(args.file, issues)
        return 1

    print(f"ADO autolink guard passed: {args.file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
