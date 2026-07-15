#!/usr/bin/env python3
"""Verify a design-backbone document and its referenced project files.

Usage:
    verify_output.py <project-root> --design <backbone-design.md>

Exit codes: 0 = all checks pass, 1 = at least one check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "requirements",
    "existing flow",
    "touchpoint matrix",
    "runtime readiness",
    "test coverage matrix",
)

TABLE_COLUMNS = {
    "requirements": ("requirement id", "requirement", "required coverage"),
    "touchpoint matrix": ("requirement ids", "path", "symbol", "action", "justification"),
    "runtime readiness": ("concern", "decision", "verification", "evidence path", "evidence symbol"),
    "test coverage matrix": (
        "requirement id",
        "test path",
        "test name",
        "category",
        "initial state",
        "coverage",
    ),
}

ALLOWED_ACTIONS = {"reuse", "modify", "extract", "new"}
READINESS_CONCERNS = {
    "entrypoint",
    "dependency wiring",
    "local mock",
    "production isolation",
    "end to end workflow",
}
RUNTIME_SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".fs", ".go", ".h", ".hpp", ".java", ".js", ".jsx",
    ".kt", ".php", ".py", ".rb", ".rs", ".scala", ".swift", ".ts", ".tsx", ".vb",
}
CONFIG_SOURCE_EXTENSIONS = {
    ".config", ".conf", ".csproj", ".env", ".fsproj", ".gradle", ".ini", ".json", ".props",
    ".properties", ".targets", ".toml", ".vbproj", ".xml", ".yaml", ".yml",
}
READINESS_EVIDENCE_KINDS = {
    "entrypoint": {"runtime"},
    "dependency wiring": {"runtime", "config"},
    "local mock": {"runtime", "config"},
    "production isolation": {"runtime", "config"},
    "end to end workflow": {"runtime"},
}
PLACEHOLDER_PATTERNS = (
    re.compile(r"\bNotImplementedException\b", re.IGNORECASE),
    re.compile(r"\bNotImplementedError\b", re.IGNORECASE),
    re.compile(r"throw\s+new\s+Error\s*\(\s*['\"]Not implemented", re.IGNORECASE),
    re.compile(r"TODO\s*:?\s*implement", re.IGNORECASE),
)
SKIP_PATTERNS = (
    re.compile(r"@pytest\.mark\.skip\b", re.IGNORECASE),
    re.compile(r"\bpytest\.skip\s*\(", re.IGNORECASE),
    re.compile(r"@unittest\.skip\b", re.IGNORECASE),
    re.compile(r"\b(?:describe|it|test)\.skip\s*\(", re.IGNORECASE),
    re.compile(r"\[(?:Fact|Theory)\s*\([^\]]*\bSkip\s*=", re.IGNORECASE),
    re.compile(r"\[(?:Ignore|Explicit)\b", re.IGNORECASE),
    re.compile(r"\bAssert\.Inconclusive\s*\(", re.IGNORECASE),
)
PLACEHOLDER_VALUES = {"", "-", "n/a", "na", "none", "tbd", "todo", "unknown"}


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = _normal(match.group(1))
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _table(lines: list[str]) -> tuple[list[str], list[dict[str, str]]] | None:
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or not _is_separator(lines[index + 1]):
            continue
        headers = [_normal(cell) for cell in _cells(lines[index])]
        rows: list[dict[str, str]] = []
        for line in lines[index + 2 :]:
            if "|" not in line or not line.strip():
                break
            values = _cells(line)
            if len(values) != len(headers):
                break
            rows.append(dict(zip(headers, values)))
        return headers, rows
    return None


def _tokens(value: str) -> set[str]:
    return {_normal(token) for token in re.split(r"[,;+/]", value) if _normal(token)}


def _ids(value: str) -> set[str]:
    """Parse comma/semicolon-separated traceability identifiers."""
    return {token.strip().upper() for token in re.split(r"[,;]", value) if token.strip()}


def _placeholder(value: str) -> bool:
    return _normal(value) in PLACEHOLDER_VALUES


def _project_file(root: Path, value: str) -> tuple[Path | None, str | None]:
    raw = Path(value.strip().strip("`"))
    candidate = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"path escapes project root: {value}"
    if not candidate.is_file():
        return None, f"file does not exist: {value}"
    return candidate, None


def _scan(path: Path, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [pattern.pattern for pattern in patterns if pattern.search(text)]


def _has_symbol(path: Path, symbol: str) -> bool:
    """Check referenced source-visible symbol text without claiming semantic resolution."""
    text = path.read_text(encoding="utf-8", errors="replace")
    value = symbol.strip().strip("`")
    return bool(value) and value in text


def _is_test_source(path: Path) -> bool:
    if path.suffix.lower() not in RUNTIME_SOURCE_EXTENSIONS:
        return False
    parts = {part.lower() for part in path.parts}
    if parts & {"test", "tests", "spec", "specs", "__tests__"}:
        return True
    name = path.name.lower()
    stem = path.stem
    lower_stem = stem.lower()
    return (
        ".test." in name
        or ".spec." in name
        or lower_stem.startswith("test_")
        or lower_stem.endswith(("_test", "test", "tests", "spec", "specs"))
        or bool(re.fullmatch(r"[A-Z][A-Za-z0-9]*IT", stem))
    )


def _is_runtime_source(path: Path) -> bool:
    return path.suffix.lower() in RUNTIME_SOURCE_EXTENSIONS and not _is_test_source(path)


def _is_config_source(path: Path) -> bool:
    return path.suffix.lower() in CONFIG_SOURCE_EXTENSIONS or path.name.lower() in {"dockerfile", "makefile"}


def _evidence_kind(path: Path) -> str | None:
    if _is_runtime_source(path):
        return "runtime"
    if _is_config_source(path):
        return "config"
    return None


def evaluate(project_root: str | Path, design_path: str | Path) -> list[tuple[str, str]]:
    """Return deterministic PASS/FAIL checks for one backbone output."""
    results: list[tuple[str, str]] = []
    root = Path(project_root).resolve()
    if not root.is_dir():
        return [("FAIL", f"project root does not exist: {root}")]

    design = Path(design_path)
    design = (design if design.is_absolute() else root / design).resolve()
    if not design.is_file():
        return [("FAIL", f"design document does not exist: {design}")]

    text = design.read_text(encoding="utf-8", errors="replace")
    sections = _sections(text)
    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    if missing:
        results.append(("FAIL", f"missing required ## section(s): {', '.join(missing)}"))
    else:
        results.append(("PASS", "all required design sections exist"))

    for name in REQUIRED_SECTIONS:
        if name in sections and not any(line.strip() for line in sections[name]):
            results.append(("FAIL", f"section is empty: {name}"))

    tables: dict[str, list[dict[str, str]]] = {}
    for section, required_columns in TABLE_COLUMNS.items():
        if section not in sections:
            continue
        parsed = _table(sections[section])
        if parsed is None:
            results.append(("FAIL", f"missing Markdown table in section: {section}"))
            continue
        headers, rows = parsed
        missing_columns = [column for column in required_columns if column not in headers]
        if missing_columns:
            results.append(("FAIL", f"{section}: missing column(s): {', '.join(missing_columns)}"))
            continue
        if not rows:
            results.append(("FAIL", f"{section}: table has no rows"))
            continue
        tables[section] = rows

    requirements: dict[str, set[str]] = {}
    for row in tables.get("requirements", []):
        requirement_id = row["requirement id"].strip().upper()
        coverage = _tokens(row["required coverage"])
        if _placeholder(requirement_id) or _placeholder(row["requirement"]) or not coverage:
            results.append(("FAIL", "requirements: each row needs id, requirement, and required coverage"))
            continue
        if requirement_id in requirements:
            results.append(("FAIL", f"requirements: duplicate requirement id: {requirement_id}"))
        requirements[requirement_id] = coverage
    if requirements:
        results.append(("PASS", f"loaded {len(requirements)} normative requirement(s)"))

    runtime_paths: set[Path] = set()
    mapped_touchpoints = {requirement_id: 0 for requirement_id in requirements}
    for row in tables.get("touchpoint matrix", []):
        path_value = row["path"]
        action = _normal(row["action"])
        touchpoint_ids = _ids(row["requirement ids"])
        if not touchpoint_ids:
            results.append(("FAIL", f"touchpoint {path_value}: requirement ids are required"))
        for requirement_id in sorted(touchpoint_ids):
            if requirement_id not in requirements:
                results.append(("FAIL", f"touchpoint {path_value}: unknown requirement id: {requirement_id}"))
        if action not in ALLOWED_ACTIONS:
            results.append(("FAIL", f"touchpoint {path_value}: invalid action '{row['action']}'"))
        if _placeholder(row["symbol"]):
            results.append(("FAIL", f"touchpoint {path_value}: symbol is required"))
        if _placeholder(row["justification"]):
            results.append(("FAIL", f"touchpoint {path_value}: justification is required for action '{action}'"))
        resolved, error = _project_file(root, path_value)
        if error:
            results.append(("FAIL", f"touchpoint: {error}"))
        elif resolved:
            eligible = _is_runtime_source(resolved)
            symbol_exists = _has_symbol(resolved, row["symbol"])
            if not eligible:
                results.append(("FAIL", f"touchpoint {path_value}: path is not eligible runtime source"))
            if not symbol_exists:
                results.append(("FAIL", f"touchpoint {path_value}: symbol not found: {row['symbol']}"))
            if eligible and symbol_exists:
                runtime_paths.add(resolved)
                for requirement_id in touchpoint_ids & requirements.keys():
                    mapped_touchpoints[requirement_id] += 1

    for requirement_id, count in mapped_touchpoints.items():
        if count == 0:
            results.append(("FAIL", f"requirement {requirement_id}: no runtime touchpoint"))

    for path in sorted(runtime_paths):
        hits = _scan(path, PLACEHOLDER_PATTERNS)
        if hits:
            results.append(("FAIL", f"runtime touchpoint contains placeholder implementation: {path.relative_to(root)}"))
    if runtime_paths and not any(level == "FAIL" and "runtime touchpoint" in message for level, message in results):
        results.append(("PASS", f"{len(runtime_paths)} runtime touchpoint(s) contain no implementation placeholders"))

    readiness_rows = tables.get("runtime readiness", [])
    readiness = {_normal(row["concern"]): row for row in readiness_rows}
    missing_concerns = sorted(READINESS_CONCERNS - set(readiness))
    if missing_concerns:
        results.append(("FAIL", f"runtime readiness: missing concern(s): {', '.join(missing_concerns)}"))
    for concern, row in readiness.items():
        if _placeholder(row["decision"]) or _placeholder(row["verification"]):
            results.append(("FAIL", f"runtime readiness '{concern}' needs decision and verification"))
        evidence_path, error = _project_file(root, row["evidence path"])
        if error:
            results.append(("FAIL", f"runtime readiness '{concern}': {error}"))
        elif evidence_path:
            evidence_kind = _evidence_kind(evidence_path)
            allowed_kinds = READINESS_EVIDENCE_KINDS.get(concern, set())
            if evidence_kind not in allowed_kinds:
                expected = "/".join(sorted(allowed_kinds)) or "runtime/config"
                results.append(("FAIL", f"runtime readiness '{concern}': evidence path must be eligible {expected} source"))
            elif not _has_symbol(evidence_path, row["evidence symbol"]):
                results.append(("FAIL", f"runtime readiness '{concern}': evidence symbol not found: {row['evidence symbol']}"))
    local_text = " ".join(readiness.get("local mock", {}).values()).lower()
    if readiness and not ("deterministic" in local_text and ("local-only" in local_text or "local only" in local_text)):
        results.append(("FAIL", "runtime readiness: local mock must be deterministic and local-only"))
    production_text = " ".join(readiness.get("production isolation", {}).values()).lower()
    if readiness and not any(word in production_text for word in ("reject", "disabled", "blocked", "not registered", "cannot")):
        results.append(("FAIL", "runtime readiness: production isolation must explicitly block mock activation"))

    mapped_coverage: dict[str, set[str]] = {requirement_id: set() for requirement_id in requirements}
    categories: set[str] = set()
    test_paths: set[Path] = set()
    for row in tables.get("test coverage matrix", []):
        requirement_id = row["requirement id"].strip().upper()
        category = _normal(row["category"])
        state = _normal(row["initial state"])
        categories.add(category)
        resolved, error = _project_file(root, row["test path"])
        valid_test_evidence = False
        if error:
            results.append(("FAIL", f"test coverage: {error}"))
        elif resolved:
            if not _is_test_source(resolved):
                results.append(("FAIL", f"test coverage {requirement_id}: path is not eligible test source: {row['test path']}"))
            elif not _has_symbol(resolved, row["test name"]):
                results.append(("FAIL", f"test coverage {requirement_id}: test name not found: {row['test name']}"))
            else:
                valid_test_evidence = True
                test_paths.add(resolved)
        if _placeholder(row["test name"]) or not _tokens(row["coverage"]):
            results.append(("FAIL", f"test coverage {requirement_id}: test name and coverage are required"))
        if category not in {"readiness", "completion"}:
            results.append(("FAIL", f"test coverage {requirement_id}: invalid category '{row['category']}'"))
            continue
        expected_state = "green" if category == "readiness" else "red"
        if state != expected_state:
            results.append(("FAIL", f"test coverage {requirement_id}: {category} test must start {expected_state}"))
        if category == "completion":
            if requirement_id not in requirements:
                results.append(("FAIL", f"completion test maps unknown requirement id: {requirement_id}"))
            elif valid_test_evidence:
                mapped_coverage[requirement_id].update(_tokens(row["coverage"]))

    for category in ("readiness", "completion"):
        if category not in categories:
            results.append(("FAIL", f"test coverage matrix has no {category} tests"))

    for requirement_id, required in requirements.items():
        missing_coverage = sorted(required - mapped_coverage[requirement_id])
        if missing_coverage:
            results.append(("FAIL", f"requirement {requirement_id}: missing completion coverage: {', '.join(missing_coverage)}"))

    for path in sorted(test_paths):
        if _scan(path, SKIP_PATTERNS):
            results.append(("FAIL", f"test file contains skip/inconclusive marker: {path.relative_to(root)}"))

    if requirements and not any(level == "FAIL" and ("requirement " in message or "completion test" in message or "test coverage" in message) for level, message in results):
        results.append(("PASS", "all requirements map to completion-test coverage"))
    if categories == {"readiness", "completion"}:
        results.append(("PASS", "readiness and completion tests are classified"))

    return results


def report(results: list[tuple[str, str]]) -> tuple[str, int]:
    lines = ["=== OUTPUT CHECK: design-backbone ==="]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    failures = sum(level == "FAIL" for level, _ in results)
    passes = sum(level == "PASS" for level, _ in results)
    lines.extend(("", f"Result: {failures} FAIL, {passes} PASS"))
    return "\n".join(lines), failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify design-backbone output.")
    parser.add_argument("project_root", help="Project root containing referenced source and tests")
    parser.add_argument("--design", required=True, help="Backbone design document, relative to project root or absolute")
    args = parser.parse_args(argv)
    rendered, failures = report(evaluate(args.project_root, args.design))
    print(rendered)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
