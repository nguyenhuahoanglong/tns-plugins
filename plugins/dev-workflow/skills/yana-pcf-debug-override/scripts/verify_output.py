#!/usr/bin/env python3
"""Mechanical guardrail for Yana PCF Debug Override skill."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "intent.json",
    "references/resource-contract.md",
    "references/browser-adapter.md",
    "scripts/resource_set.py",
    "scripts/capture_runtime.mjs",
    "scripts/tests/test_resource_set.py",
    "scripts/tests/test_capture_runtime.py",
    "scripts/yana_grid_debug_override.py",
    "scripts/tests/test_yana_grid_debug_override.py",
    "evals/evals.json",
)

REQUIRED_TEXT = (
    ("SKILL.md", "YanaQuickView", "dry-run", "fast-forward only", "NOT VERIFIED", "npm ci", "package-lock.json"),
    ("references/resource-contract.md", "browser profile", "deployed identity", "migrate-legacy-grid-map"),
    (
        "references/browser-adapter.md", "Claude Code", "Codex", "Chrome 136", "Chrome 144",
        "--user-data-dir", "Profile Path", "Debugger.getScriptSource", "Network.getResponseBody",
        "developer.chrome.com/blog/remote-debugging-port", "chrome-devtools-mcp/blob/main/docs/advanced-usage.md",
    ),
)


def evaluate(skill_root: str | Path) -> list[tuple[str, str]]:
    """Check deterministic delivery contract."""
    root = Path(skill_root).resolve()
    results: list[tuple[str, str]] = []

    results.append(("PASS" if root.is_dir() else "FAIL", f"skill root exists: {root}"))
    if not root.is_dir():
        return results

    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        results.append(("PASS" if path.is_file() else "FAIL", f"required file: {relative_path}"))

    for relative_path, *markers in REQUIRED_TEXT:
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            contents = path.read_text(encoding="utf-8-sig")
            missing = [marker for marker in markers if marker.casefold() not in contents.casefold()]
            results.append(("FAIL" if missing else "PASS", f"contract text {relative_path}: {', '.join(missing) if missing else 'all markers present'}"))
        except OSError as exc:
            results.append(("FAIL", f"contract text {relative_path}: {exc}"))

    for path in sorted((root / "scripts").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"))
            results.append(("PASS", f"Python syntax: {path.name}"))
        except (OSError, SyntaxError) as exc:
            results.append(("FAIL", f"Python syntax: {path.name}: {exc}"))
    for relative_path in ("intent.json", "evals/evals.json"):
        path = root / relative_path
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(value, dict):
                    raise ValueError("Root must be an object")
                if relative_path == "intent.json":
                    if value.get("active_revision") != 3:
                        raise ValueError("Active intent revision must be 3")
                    revision_ids = [item.get("id") for item in value.get("revisions", []) if isinstance(item, dict)]
                    if revision_ids.count(3) != 1:
                        raise ValueError("Intent must contain exactly one revision 3")
                if relative_path == "evals/evals.json":
                    evals = value.get("evals")
                    if not isinstance(evals, list) or len(evals) < 11:
                        raise ValueError("Behavioral evals must cover at least eleven scenarios")
                results.append(("PASS", f"JSON object: {relative_path}"))
            except (OSError, ValueError) as exc:
                results.append(("FAIL", f"JSON: {relative_path}: {exc}"))
    return results


def report(results: list[tuple[str, str]]) -> tuple[str, int]:
    """Render structured output and fail count."""
    lines = ["=== OUTPUT CHECK: yana-pcf-debug-override ==="]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    fails = sum(level == "FAIL" for level, _ in results)
    lines.append("")
    lines.append(f"Result: {fails} FAIL, {sum(level == 'PASS' for level, _ in results)} PASS")
    lines.append("Structure checks only. Run the unit/collector tests and skill-creator intent guard separately.")
    return "\n".join(lines), fails


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Yana PCF Debug Override skill.")
    parser.add_argument("skill_root", nargs="?", default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    text, fails = report(evaluate(args.skill_root))
    print(text)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
