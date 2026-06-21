#!/usr/bin/env python3
"""
Output guardrail for the design-scaffold skill.

Run this as the final step of the skill's workflow to verify the OUTPUT is
consistent and meets the skill's acceptance criteria before declaring a task done.

Fill in `evaluate()` with one check per *deterministic* acceptance criterion
captured in Step 1 (mirrored in evals/evals.json `expectations`). Keep checks
deterministic — anything subjective (writing quality, design taste) belongs in
human/LLM review, not here.

Usage:
    verify_output.py <output_path>

Exit codes: 0 = all checks pass, 1 = at least one FAIL.
"""

import re
import sys
import argparse
from pathlib import Path

# Source extensions this skill scaffolds.
SOURCE_EXTS = {".cs", ".py", ".ts", ".tsx", ".js", ".jsx"}

# A body containing one of these is recognized as a deliberate non-implementing stub.
STUB_MARKERS = (
    "notimplementedexception",   # C#
    "notimplementederror",       # Python
    'error("not implemented',    # TS/JS
    "error('not implemented",
    "todo: implement",
    "todo implement",
)

# Lines that indicate real behavior leaked into a scaffold (control flow doing work).
# Comment/doc lines are stripped before matching to limit false positives.
LOGIC_PATTERNS = (
    re.compile(r"\b(if|for|while|foreach|switch)\b\s*\("),   # C#/TS/JS control flow
    re.compile(r"^\s*(if|for|while|elif|with)\b.*:\s*$"),     # Python control flow
    re.compile(r"^\s*(try|except|catch)\b"),                  # error handling
    re.compile(r"\.(map|filter|reduce|forEach|select|where|aggregate)\s*\("),  # data transforms
    re.compile(r"\breturn\s+.+[-+*/%]\s"),                    # computed return expression
)

# Comment prefixes to ignore per line.
_COMMENT_PREFIXES = ("//", "#", "*", "/*", '"""', "'''", "///")


def _is_comment(line):
    s = line.strip()
    return (not s) or s.startswith(_COMMENT_PREFIXES)


def _scan_file(path):
    """Return (has_stub, logic_hits) for a single source file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (False, [])
    lower = text.lower()
    has_stub = any(m in lower for m in STUB_MARKERS)
    logic_hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _is_comment(line):
            continue
        for pat in LOGIC_PATTERNS:
            if pat.search(line):
                logic_hits.append((i, line.strip()[:80]))
                break
    return (has_stub, logic_hits)


def _iter_sources(p):
    if p.is_file():
        if p.suffix in SOURCE_EXTS:
            yield p
        return
    for child in sorted(p.rglob("*")):
        if child.is_file() and child.suffix in SOURCE_EXTS:
            # skip test files — those are out of scope for scaffold
            name = child.name.lower()
            if "test" in name or "spec" in name:
                continue
            yield child


def evaluate(output_path):
    """Check that the scaffold at output_path is structure-only (no implementation)."""
    results = []
    p = Path(output_path)

    if not p.exists():
        results.append(("FAIL", f"scaffold path does not exist: {p}"))
        return results

    sources = list(_iter_sources(p))
    if not sources:
        results.append(("WARN", f"no source files ({', '.join(sorted(SOURCE_EXTS))}) found under {p}"))
        return results

    results.append(("PASS", f"found {len(sources)} scaffold source file(s)"))

    stubbed = 0
    for src in sources:
        has_stub, logic = _scan_file(src)
        rel = src.name
        if logic and not has_stub:
            sample = "; ".join(f"L{n}: {t}" for n, t in logic[:3])
            results.append(("FAIL", f"{rel}: looks implemented (no stub marker; logic at {sample})"))
        elif logic and has_stub:
            results.append(("WARN", f"{rel}: stub present but {len(logic)} logic-like line(s) — review L{logic[0][0]}"))
            stubbed += 1
        elif has_stub:
            stubbed += 1

    results.append((
        "PASS" if stubbed else "WARN",
        f"{stubbed}/{len(sources)} file(s) carry an explicit not-implemented stub",
    ))
    return results


def report(skill_name, results):
    """Render a structured report. Returns (text, fail_count)."""
    lines = [f"=== OUTPUT CHECK: {skill_name} ==="]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    fails = sum(1 for level, _ in results if level == "FAIL")
    warns = sum(1 for level, _ in results if level == "WARN")
    passes = sum(1 for level, _ in results if level == "PASS")
    lines.append("")
    parts = []
    if fails:
        parts.append(f"{fails} FAIL")
    if warns:
        parts.append(f"{warns} WARN")
    parts.append(f"{passes} PASS")
    lines.append(f"Result: {', '.join(parts)}")
    return "\n".join(lines), fails


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify design-scaffold output.")
    parser.add_argument("output_path", nargs="?", default=".",
                        help="Path to the output to verify")
    args = parser.parse_args(argv)

    results = evaluate(args.output_path)
    text, fails = report("design-scaffold", results)
    print(text)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
