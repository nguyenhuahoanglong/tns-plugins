#!/usr/bin/env python3
"""
Output guardrail for the unit-testing skill.

Run as the final step to verify GENERATED TESTS meet the deterministic acceptance
criteria before declaring the task done. Subjective quality (is this the *right*
test?) is for human/LLM review — this only catches mechanical defects.

Checks (mirror evals/evals.json expectations):
  1. Output path exists and contains recognizable test files.
  2. Tests contain real assertions (not empty stubs).
  3. Test names are descriptive (not Test1/TODO placeholders).
  4. A requirement/behavior -> test mapping is referenced (WARN if absent —
     it may live in the QA report rather than the test file).
  5. (optional, --existing) Generated test names don't duplicate existing tests
     — so the suite is maintained in place instead of accreting duplicates.
  6. (optional, --test-cases) Traceability against the test-case registry
     ({design-doc}.test-cases.md): every TC-NNN referenced in tests exists in the
     registry (FAIL on unknown IDs), every registry case has a referencing test
     (WARN if pending), and test files cite the registry in a header (WARN).

Usage:
    verify_output.py <test-file-or-dir> [--existing <existing-tests-dir>]
                     [--test-cases <registry.md>]

Exit codes: 0 = no FAIL, 1 = at least one FAIL.
"""

import argparse
import re
import sys
from pathlib import Path

_TEST_GLOBS = ("*.test.*", "*.spec.*", "*Test*.cs", "*Tests*.cs", "*_test.py")
_ASSERTION_PATTERNS = (
    r"\.Should\(", r"Assert\.", r"\bexpect\(", r"\.ShouldBe", r"toMatch", r"toEqual",
    r"toBe\(", r"Verify\(", r"\.Received\(",
)
_TEST_DECL_PATTERNS = (
    r"\[Fact\]", r"\[Theory\]",          # xUnit
    r"\bit\(", r"\btest\(",               # JS/TS
)
_PLACEHOLDER_NAMES = re.compile(
    r"\b(Test1|TestMethod1|MyTest|it\(['\"]\s*todo|todo|placeholder|xunit\d)\b",
    re.IGNORECASE,
)
_MAPPING_HINTS = re.compile(
    r"(REQ-\d|AC-\d|TC-\d|requirement|characterization|acceptance criteri)", re.IGNORECASE
)
_TC_ID = re.compile(r"\bTC-\d{3,}\b")
_REGISTRY_HEADER_HINT = re.compile(r"test.cases", re.IGNORECASE)


def _collect_test_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for g in _TEST_GLOBS:
        files.extend(path.rglob(g))
    return sorted(set(files))


def _read_blob(files) -> str:
    blob = ""
    for f in files:
        try:
            blob += f.read_text(encoding="utf-8", errors="ignore") + "\n"
        except OSError:
            pass
    return blob


def _extract_test_names(text: str) -> set[str]:
    """Best-effort test-name extraction across C# (xUnit) and JS/TS (it/test)."""
    names: set[str] = set()
    # JS/TS: it('name', ...) / test("name", ...)
    for m in re.finditer(r"\b(?:it|test)\s*\(\s*['\"`]([^'\"`]+)", text):
        names.add(m.group(1).strip())
    # C#: method name following a [Fact]/[Theory] attribute
    for m in re.finditer(r"\[(?:Fact|Theory)\b", text):
        window = text[m.end():m.end() + 300]
        mm = re.search(
            r"\b(?:public|internal|private|protected)\s+(?:async\s+)?[\w<>\[\],.]+\s+(\w+)\s*\(",
            window,
        )
        if mm:
            names.add(mm.group(1))
    return names


def _registry_tc_ids(registry_text: str) -> set[str]:
    """TC IDs declared as registry rows: markdown table lines like '| TC-001 | ...'."""
    ids: set[str] = set()
    for line in registry_text.splitlines():
        m = re.match(r"^\|\s*(TC-\d{3,})\s*\|", line.strip())
        if m:
            ids.add(m.group(1))
    return ids


def _check_test_cases(files, blob, registry_path) -> list:
    """Traceability checks against the test-case registry (test-case-management.md)."""
    results = []
    rp = Path(registry_path)
    if not rp.exists():
        results.append(("FAIL", f"--test-cases registry not found: {rp}"))
        return results

    registry_ids = _registry_tc_ids(rp.read_text(encoding="utf-8", errors="ignore"))
    if not registry_ids:
        results.append(("FAIL", f"no 'TC-NNN' table rows found in registry: {rp}"))
        return results

    referenced = set(_TC_ID.findall(blob))

    unknown = sorted(referenced - registry_ids)
    results.append(("FAIL" if unknown else "PASS",
                    f"tests reference TC id(s) missing from the registry: {', '.join(unknown)}"
                    if unknown else "all TC ids referenced in tests exist in the registry"))

    uncovered = sorted(registry_ids - referenced)
    results.append(("WARN" if uncovered else "PASS",
                    f"{len(uncovered)} registry case(s) not referenced by any test "
                    f"(pending or a gap): {', '.join(uncovered[:8])}"
                    f"{' ...' if len(uncovered) > 8 else ''}"
                    if uncovered else "every registry test case is referenced by a test"))

    missing_header = [f.name for f in files
                      if not _REGISTRY_HEADER_HINT.search(
                          f.read_text(encoding="utf-8", errors="ignore")[:500])]
    results.append(("WARN" if missing_header else "PASS",
                    "test file(s) missing the registry header comment "
                    f"('Test cases: ...'): {', '.join(missing_header[:8])}"
                    if missing_header else "all test files cite the test-case registry"))

    return results


def evaluate(output_path, existing_path=None, test_cases_path=None):
    results = []
    p = Path(output_path)

    if not p.exists():
        results.append(("FAIL", f"output path does not exist: {p}"))
        return results

    files = _collect_test_files(p)
    if not files:
        results.append(("FAIL", f"no test files found under {p} "
                                "(expected *.test.*, *.spec.*, *Test*.cs, ...)"))
        return results
    results.append(("PASS", f"{len(files)} test file(s) found"))

    blob = _read_blob(files)

    has_tests = any(re.search(pat, blob) for pat in _TEST_DECL_PATTERNS)
    results.append(("PASS" if has_tests else "FAIL",
                    "test declarations present ([Fact]/[Theory]/it/test)"
                    if has_tests else "no test declarations found"))

    has_assert = any(re.search(pat, blob) for pat in _ASSERTION_PATTERNS)
    results.append(("PASS" if has_assert else "FAIL",
                    "assertions present" if has_assert
                    else "no assertions found — tests must assert behavior"))

    placeholder = _PLACEHOLDER_NAMES.search(blob)
    results.append(("WARN" if placeholder else "PASS",
                    f"placeholder/TODO test name detected: {placeholder.group(0)!r}"
                    if placeholder else "no placeholder test names"))

    has_mapping = bool(_MAPPING_HINTS.search(blob))
    results.append(("PASS" if has_mapping else "WARN",
                    "requirement/behavior mapping referenced"
                    if has_mapping
                    else "no requirement mapping in tests — ensure it exists in the QA report"))

    # Maintenance check (Step 2): warn on generated test names that collide with
    # tests that already exist, so we update in place instead of duplicating.
    if existing_path:
        ep = Path(existing_path)
        if not ep.exists():
            results.append(("WARN", f"--existing path not found, skipped dup check: {ep}"))
        else:
            existing_files = [f for f in _collect_test_files(ep) if f not in set(files)]
            dups = sorted(_extract_test_names(blob) & _extract_test_names(_read_blob(existing_files)))
            if dups:
                shown = ", ".join(dups[:8]) + (" ..." if len(dups) > 8 else "")
                results.append(("WARN", f"{len(dups)} test name(s) duplicate existing tests "
                                        f"— update in place instead of adding: {shown}"))
            else:
                results.append(("PASS", "no test-name collisions with existing tests"))

    # Traceability check (Step 7): tests <-> test-case registry.
    if test_cases_path:
        results.extend(_check_test_cases(files, blob, test_cases_path))

    return results


def report(skill_name, results):
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
    parser = argparse.ArgumentParser(description="Verify unit-testing output.")
    parser.add_argument("output_path", nargs="?", default=".",
                        help="Path to the generated test file or directory")
    parser.add_argument("--existing", default=None,
                        help="Path to pre-existing tests; warns on duplicate test names")
    parser.add_argument("--test-cases", default=None,
                        help="Path to the {design-doc}.test-cases.md registry; "
                             "verifies TC-id traceability between tests and registry")
    args = parser.parse_args(argv)

    results = evaluate(args.output_path, args.existing, args.test_cases)
    text, fails = report("unit-testing", results)
    print(text)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
