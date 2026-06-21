#!/usr/bin/env python3
"""
Tests for verify_output.py (scaffold for the unit-testing skill).

Passes out of the box; extend it as you add real checks to evaluate(). Runs under
pytest (`python -m pytest scripts/tests/`) and standalone
(`python scripts/tests/test_verify_output.py`).
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_output as vo  # noqa: E402


def test_evaluate_returns_results():
    results = vo.evaluate(".")
    assert isinstance(results, list) and results, "evaluate() should return at least one result"


def test_no_unimplemented_failures():
    # Before any checks are implemented there are no FAILs (only a WARN nudge),
    # so the guardrail exits 0. As you add checks, assert their behaviour here.
    _, fails = vo.report("unit-testing", vo.evaluate("."))
    assert fails == 0


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
