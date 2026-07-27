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
     registry (FAIL on unknown IDs), approved pending cases remain visible without
     penalty, and test headers identify the exact registry and subject (FAIL).
     Registry rows require Status, Coverage / reason, and Covered by metadata;
     Known Quirk labels and uncovered-gap reasons must be explicit.

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
_REGISTRY_HEADER = re.compile(r"(?:test registry|test cases)\s*:\s*(\S+)", re.IGNORECASE)
_SUBJECT_METADATA = re.compile(
    r"^\s*(?://+\s*)?(?:subject|target)\s*:\s*\S+", re.IGNORECASE | re.MULTILINE
)
_KNOWN_QUIRK = re.compile(r"Known Quirk", re.IGNORECASE)


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


def _registry_rows(registry_text: str) -> list[dict[str, str]]:
    """Read TC rows using the registry's named columns, not fixed positions."""
    lines = registry_text.splitlines()
    header = next((line for line in lines if re.match(r"^\|.*\bID\b.*\|", line, re.IGNORECASE)), "")
    columns = [cell.strip().lower() for cell in header.strip().strip("|").split("|")]
    required = {"id", "status", "coverage / reason", "covered by"}
    if not required.issubset(columns):
        return []
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(columns) or not re.fullmatch(r"TC-\d{3,}", cells[columns.index("id")]):
            continue
        rows.append(dict(zip(columns, cells)))
    return rows


def _header_registry_path(text: str) -> str | None:
    """Return the registry identity declared near the top of an owned test file."""
    match = _REGISTRY_HEADER.search(text[:500])
    return match.group(1) if match else None


def _tc_has_known_quirk(text: str, tc_id: str) -> bool:
    """A per-test header must carry the label close to the referenced TC."""
    for match in re.finditer(re.escape(tc_id), text):
        window = text[max(0, match.start() - 250):match.end() + 250]
        if _KNOWN_QUIRK.search(window):
            return True
    return False


def _check_test_cases(files, blob, registry_path) -> list:
    """Traceability checks against the test-case registry (test-case-management.md)."""
    results = []
    rp = Path(registry_path)
    if not rp.exists():
        results.append(("FAIL", f"--test-cases registry not found: {rp}"))
        return results

    registry_text = rp.read_text(encoding="utf-8", errors="ignore")
    registry_ids = _registry_tc_ids(registry_text)
    if not registry_ids:
        results.append(("FAIL", f"no 'TC-NNN' table rows found in registry: {rp}"))
        return results

    referenced = set(_TC_ID.findall(blob))

    unknown = sorted(referenced - registry_ids)
    results.append(("FAIL" if unknown else "PASS",
                    f"tests reference TC id(s) missing from the registry: {', '.join(unknown)}"
                    if unknown else "all TC ids referenced in tests exist in the registry"))

    rows = _registry_rows(registry_text)
    if not rows:
        results.append(("FAIL", "registry lacks required ID, Status, Coverage / reason, or Covered by metadata"))
        return results

    uncovered = sorted(registry_ids - referenced)
    pending = {row["id"] for row in rows if row["status"].lower() == "pending"}
    actionable = [tc_id for tc_id in uncovered if tc_id not in pending]
    results.append(("WARN" if actionable else "PASS",
                    f"{len(actionable)} registry case(s) not referenced by any test: "
                    f"{', '.join(actionable[:8])}{' ...' if len(actionable) > 8 else ''}"
                    if actionable else "all non-pending registry cases are referenced by a test"))
    if pending:
        results.append(("PASS", "approved pending registry cases remain visible without a traceability penalty"))

    missing_reason = []
    for row in rows:
        coverage = row["coverage / reason"].strip()
        is_uncovered = coverage.lower().startswith("uncovered")
        has_reason = bool(re.match(r"^uncovered\s*:\s*\S+", coverage, re.IGNORECASE))
        if is_uncovered and not has_reason:
            missing_reason.append(row["id"])
    results.append(("FAIL" if missing_reason else "PASS",
                    f"uncovered registry case(s) lack an explicit reason: {', '.join(missing_reason)}"
                    if missing_reason else "all intentionally uncovered registry cases record a reason"))

    expected_identity = str(registry_path)
    bad_headers = []
    missing_subject = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        identity = _header_registry_path(text)
        if identity != expected_identity:
            bad_headers.append(f"{f.name} ({identity or 'missing'})")
        if not _SUBJECT_METADATA.search(text[:500]):
            missing_subject.append(f.name)
    results.append(("FAIL" if bad_headers else "PASS",
                    "test file(s) missing the exact registry identity: " + ", ".join(bad_headers)
                    if bad_headers else "all test files identify the exact registry path"))
    results.append(("FAIL" if missing_subject else "PASS",
                    "test file(s) missing Subject/Target header metadata: " + ", ".join(missing_subject)
                    if missing_subject else "all test files include Subject/Target header metadata"))

    quirk_ids = [row["id"] for row in rows if _KNOWN_QUIRK.search(row["coverage / reason"])]
    missing_quirk_headers = [tc_id for tc_id in quirk_ids if not _tc_has_known_quirk(blob, tc_id)]
    results.append(("FAIL" if missing_quirk_headers else "PASS",
                    "Known Quirk registry case(s) lack the matching test header label: "
                    + ", ".join(missing_quirk_headers)
                    if missing_quirk_headers else "Known Quirk registry labels are paired with test headers"))

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
            supplied_files = _collect_test_files(ep)
            output_files = set(files)
            existing_files = [f for f in supplied_files if f not in output_files]
            dups = sorted(_extract_test_names(blob) & _extract_test_names(_read_blob(existing_files)))
            if dups:
                shown = ", ".join(dups[:8]) + (" ..." if len(dups) > 8 else "")
                results.append(("WARN", f"{len(dups)} test name(s) duplicate existing tests "
                                        f"— update in place instead of adding: {shown}"))
            else:
                results.append(("PASS", "no test-name collisions with existing tests"))
            if output_files & set(supplied_files):
                results.append(("PASS", "generated tests reuse the supplied canonical owner"))
            else:
                results.append(("FAIL", "generated tests do not reuse the supplied canonical owner"))

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
