#!/usr/bin/env python3
"""
Tests for verify_output.py (scaffold for the unit-testing skill).

Passes out of the box; extend it as you add real checks to evaluate(). Runs under
pytest (`python -m pytest scripts/tests/`) and standalone
(`python scripts/tests/test_verify_output.py`).
"""

import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_output as vo  # noqa: E402

_REGISTRY = """---
source-design: .docs/order-validation.md
---
| ID | Title | Type | Design ref | Covered by |
|----|-------|------|-----------|------------|
| TC-001 | Accept order within limit | happy | 3.1 | OrderTests.cs |
| TC-002 | Reject expired credit | error | 3.2 | *(not yet implemented)* |
"""

_TEST_FILE = """// Test cases: .docs/order-validation.test-cases.md
/// <summary>
/// TC-001: Accept order within limit
/// </summary>
[Fact]
[Trait("TestCase", "TC-001")]
public void Should_AcceptOrder_When_WithinLimit() { Assert.True(true); }
"""


def test_evaluate_returns_results():
    results = vo.evaluate(".")
    assert isinstance(results, list) and results, "evaluate() should return at least one result"


def test_valid_test_file_has_no_failures():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "OrderTests.cs"
        f.write_text(_TEST_FILE, encoding="utf-8")
        _, fails = vo.report("unit-testing", vo.evaluate(f))
        assert fails == 0


def test_registry_tc_ids_parses_table_rows_only():
    ids = vo._registry_tc_ids(_REGISTRY + "\nprose mentioning TC-099 outside the table\n")
    assert ids == {"TC-001", "TC-002"}


def test_test_cases_check_passes_and_warns_on_uncovered():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OrderTests.cs").write_text(_TEST_FILE, encoding="utf-8")
        reg = d / "order-validation.test-cases.md"
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        levels = [lvl for lvl, _ in results]
        assert "FAIL" not in levels
        # TC-002 is in the registry but not referenced -> WARN
        assert any(lvl == "WARN" and "TC-002" in msg for lvl, msg in results)


def test_test_cases_check_fails_on_unknown_tc_id():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OrderTests.cs").write_text(
            _TEST_FILE.replace("TC-001", "TC-777"), encoding="utf-8")
        reg = d / "order-validation.test-cases.md"
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        assert any(lvl == "FAIL" and "TC-777" in msg for lvl, msg in results)


def test_test_cases_check_warns_on_missing_registry_header():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        body = _TEST_FILE.replace(
            "// Test cases: .docs/order-validation.test-cases.md\n", "")
        (d / "OrderTests.cs").write_text(body, encoding="utf-8")
        reg = d / "order-validation.test-cases.md"
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        assert any(lvl == "WARN" and "registry header" in msg for lvl, msg in results)


def test_test_cases_check_fails_on_missing_registry_file():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OrderTests.cs").write_text(_TEST_FILE, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs",
                              test_cases_path=d / "does-not-exist.md")
        assert any(lvl == "FAIL" and "registry not found" in msg for lvl, msg in results)


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
