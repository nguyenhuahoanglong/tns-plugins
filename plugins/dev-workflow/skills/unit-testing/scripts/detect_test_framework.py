#!/usr/bin/env python3
"""
Detect the testing stack, framework, and conventions for a project or file.

Replaces several manual "read package.json / grep the .csproj / look for a test
project" tool calls with one deterministic scan, so the skill matches what the
project already uses instead of guessing (e.g. Vitest vs Jest).

Usage:
    detect_test_framework.py <path>          # file or directory
    detect_test_framework.py <path> --dry-run

Output: structured `=== DETECTION ===` report. Exit 0 if a stack was identified,
1 if nothing recognizable was found (so callers can branch).
"""

import argparse
import json
import re
import sys
from pathlib import Path

# How far up to walk looking for project roots, and what marks a root.
_MAX_UP = 6
_ROOT_MARKERS = ("package.json", ".git", "*.sln")


def _find_context_dir(start: Path) -> Path:
    """Return the directory to scan from (file -> its parent)."""
    return start if start.is_dir() else start.parent


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _nearest(start: Path, filename: str) -> Path | None:
    """Walk up from start looking for `filename`."""
    cur = start.resolve()
    for _ in range(_MAX_UP):
        candidate = cur / filename
        if candidate.is_file():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _glob_up(start: Path, pattern: str, limit: int = 20) -> list[Path]:
    """Find files matching pattern at/under each ancestor (shallow per level)."""
    found: list[Path] = []
    cur = start.resolve()
    for _ in range(_MAX_UP):
        found.extend(sorted(cur.glob(pattern))[: limit - len(found)])
        if len(found) >= limit or cur.parent == cur:
            break
        cur = cur.parent
    return found


def detect_node(ctx: Path) -> dict | None:
    """Detect React/TS / PCF testing setup from the nearest package.json."""
    pkg_path = _nearest(ctx, "package.json")
    if not pkg_path:
        return None
    try:
        pkg = json.loads(_read(pkg_path))
    except json.JSONDecodeError:
        pkg = {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    root = pkg_path.parent
    is_pcf = bool(list(root.rglob("ControlManifest.Input.xml"))) or "pcf-scripts" in deps

    # Framework: prefer config-file evidence, fall back to deps, then scripts.
    has_vitest = any((root / f).exists() for f in
                     ("vitest.config.ts", "vitest.config.js", "vitest.config.mts")) \
        or "vitest" in deps
    has_jest = any((root / f).exists() for f in
                   ("jest.config.js", "jest.config.ts", "jest.config.cjs", "jest.config.mjs")) \
        or "jest" in deps or "ts-jest" in deps \
        or isinstance(pkg.get("jest"), dict)

    if has_vitest and not has_jest:
        framework, run = "Vitest", "npx vitest run"
    elif has_jest and not has_vitest:
        framework, run = "Jest", "npx jest"
    elif has_vitest and has_jest:
        framework, run = "Vitest + Jest (both present — match the test dir in use)", "npx vitest run"
    else:
        framework, run = "(none installed — Vitest recommended for new React/Vite)", "npx vitest run"

    stack = "PCF (TypeScript)" if is_pcf else "React / TypeScript"
    reference = "references/pcf-testing.md" if is_pcf else "references/react-vitest-jest.md"

    libs = [name for name in (
        "@testing-library/react", "@testing-library/user-event",
        "msw", "@testing-library/jest-dom") if name in deps]

    test_files = _glob_up(root, "**/*.test.*", limit=5) + _glob_up(root, "**/*.spec.*", limit=5)
    return {
        "stack": stack,
        "framework": framework,
        "run": run,
        "reference": reference,
        "project_root": str(root),
        "libraries": libs,
        "existing_tests": [str(p) for p in test_files[:5]],
    }


def detect_dotnet(ctx: Path) -> dict | None:
    """Detect C# / xUnit testing setup from nearby .csproj files."""
    csprojs = _glob_up(ctx, "*.csproj", limit=20)
    # Also look for sibling test projects under the solution dir.
    sln = _glob_up(ctx, "*.sln", limit=2)
    if sln:
        csprojs += sorted(sln[0].parent.rglob("*.Tests.csproj"))[:10]
    csprojs = list(dict.fromkeys(csprojs))  # dedupe, keep order
    if not csprojs:
        return None

    text = "\n".join(_read(p) for p in csprojs)
    pkgs = set(re.findall(r'PackageReference\s+Include="([^"]+)"', text))

    framework_bits = []
    if any(p == "xunit" or p.startswith("xunit") for p in pkgs):
        framework_bits.append("xUnit")
    if "NSubstitute" in pkgs:
        framework_bits.append("NSubstitute")
    if "Moq" in pkgs:
        framework_bits.append("Moq")
    if any(p.startswith("FluentAssertions") for p in pkgs):
        framework_bits.append("FluentAssertions")
    if any(p.startswith("FakeXrmEasy") for p in pkgs):
        framework_bits.append("FakeXrmEasy")

    test_projects = [str(p) for p in csprojs if p.name.lower().endswith(".tests.csproj")
                     or "test" in _read(p).lower() and "Microsoft.NET.Test.Sdk" in _read(p)]

    framework = " + ".join(framework_bits) if framework_bits \
        else "(no test packages found — xUnit + NSubstitute + FluentAssertions recommended)"
    return {
        "stack": "C# .NET",
        "framework": framework,
        "run": 'dotnet test --collect:"XPlat Code Coverage"',
        "reference": "references/csharp-xunit.md",
        "projects": [str(p) for p in csprojs[:8]],
        "test_projects": test_projects[:5],
    }


def detect(path: Path) -> list[dict]:
    ctx = _find_context_dir(path)
    results = []
    for fn in (detect_dotnet, detect_node):
        r = fn(ctx)
        if r:
            results.append(r)
    return results


def report(path: Path, results: list[dict]) -> tuple[str, int]:
    lines = ["=== DETECTION ===", f"target: {path}"]
    if not results:
        lines.append("stack: UNKNOWN — no .csproj or package.json found nearby")
        lines.append("")
        lines.append("Result: 0 stacks detected")
        return "\n".join(lines), 1

    for i, r in enumerate(results, 1):
        lines.append("")
        lines.append(f"--- stack {i}: {r['stack']} ---")
        for key in ("framework", "run", "reference", "project_root"):
            if key in r:
                lines.append(f"{key}: {r[key]}")
        if r.get("libraries"):
            lines.append(f"libraries: {', '.join(r['libraries'])}")
        for key in ("projects", "test_projects", "existing_tests"):
            if r.get(key):
                lines.append(f"{key}: {', '.join(r[key])}")
    lines.append("")
    lines.append(f"Result: {len(results)} stack(s) detected — read the listed reference(s)")
    return "\n".join(lines), 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect test stack/framework/conventions.")
    parser.add_argument("path", nargs="?", default=".", help="File or directory to inspect")
    parser.add_argument("--dry-run", action="store_true",
                        help="No-op flag (this tool is read-only); accepted for convention")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print(f"=== DETECTION ===\nerror: path not found: {path}", file=sys.stderr)
        return 1

    text, code = report(path, detect(path))
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
