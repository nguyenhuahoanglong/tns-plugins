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

_REGISTRY = """| ID | Title | Status | Coverage / reason | Covered by |
|----|-------|--------|-------------------|------------|
| TC-001 | Accept order within limit | Implemented | Covered | OrderTests.cs |
| TC-002 | Reject expired credit | Pending | Uncovered: external fixture unavailable | *(not yet implemented)* |
"""

_TEST_FILE = """// Test registry: order-validation.test-cases.md
// Subject: OrderService
/// <summary>
/// TC-001: Accept order within limit
/// </summary>
[Fact]
[Trait("TestCase", "TC-001")]
public void Should_AcceptOrder_When_WithinLimit() { Assert.True(true); }
"""


def _test_file_for(registry_path):
    return _TEST_FILE.replace("order-validation.test-cases.md", str(registry_path))


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
        reg = d / "order-validation.test-cases.md"
        (d / "OrderTests.cs").write_text(_test_file_for(reg), encoding="utf-8")
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        levels = [lvl for lvl, _ in results]
        assert "FAIL" not in levels
        assert any(lvl == "PASS" and "approved pending" in msg for lvl, msg in results)


def test_test_cases_check_fails_on_unknown_tc_id():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        reg = d / "order-validation.test-cases.md"
        (d / "OrderTests.cs").write_text(
            _test_file_for(reg).replace("TC-001", "TC-777"), encoding="utf-8")
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        assert any(lvl == "FAIL" and "TC-777" in msg for lvl, msg in results)


def test_test_cases_check_warns_on_missing_registry_header():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        reg = d / "order-validation.test-cases.md"
        body = _TEST_FILE.replace(
            "// Test registry: order-validation.test-cases.md\n", "")
        (d / "OrderTests.cs").write_text(body, encoding="utf-8")
        reg.write_text(_REGISTRY, encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs", test_cases_path=reg)
        assert any(lvl == "FAIL" and "exact registry identity" in msg for lvl, msg in results)


def test_test_cases_check_fails_on_missing_registry_file():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OrderTests.cs").write_text(_test_file_for(d / "does-not-exist.md"), encoding="utf-8")
        results = vo.evaluate(d / "OrderTests.cs",
                              test_cases_path=d / "does-not-exist.md")
        assert any(lvl == "FAIL" and "registry not found" in msg for lvl, msg in results)


def test_registry_guardrails_pass_for_compliant_known_quirk_and_owner():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        test_file = d / "OrderTests.cs"
        reg = d / "order-validation.test-cases.md"
        test_file.write_text(_test_file_for(reg).replace(
            "TC-002 | Reject expired credit | Pending | Uncovered: external fixture unavailable | *(not yet implemented)*",
            "TC-002 | Rounds odd cents down | Implemented | Known Quirk: current result pinned | OrderTests.cs").replace(
                "/// TC-001: Accept order within limit",
                "/// TC-001: Accept order within limit\n/// TC-002: Rounds odd cents down").replace(
                "[Fact]", "/// Known Quirk: pins the current result; correctness is not asserted.\n[Fact]"), encoding="utf-8")
        reg.write_text(_REGISTRY.replace(
            "TC-002 | Reject expired credit | Pending | Uncovered: external fixture unavailable | *(not yet implemented)*",
            "TC-002 | Rounds odd cents down | Implemented | Known Quirk: current result pinned | OrderTests.cs"), encoding="utf-8")
        results = vo.evaluate(test_file, existing_path=test_file, test_cases_path=reg)
        assert not [item for item in results if item[0] == "FAIL"]


def test_registry_guardrails_fail_for_missing_metadata_reason_and_quirk_header():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        test_file = d / "OrderTests.cs"
        reg = d / "order-validation.test-cases.md"
        test_file.write_text(_test_file_for(reg), encoding="utf-8")
        reg.write_text("""| ID | Title | Status | Coverage / reason | Covered by |
|----|-------|--------|-------------------|------------|
| TC-001 | Accept | Implemented | Uncovered | OrderTests.cs |
| TC-002 | Quirk | Implemented | Known Quirk: pinned result | OrderTests.cs |
""", encoding="utf-8")
        results = vo.evaluate(test_file, test_cases_path=reg)
        messages = "\n".join(message for _, message in results)
        assert "uncovered registry case(s) lack an explicit reason: TC-001" in messages
        assert "Known Quirk registry case(s) lack the matching test header label: TC-002" in messages


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
