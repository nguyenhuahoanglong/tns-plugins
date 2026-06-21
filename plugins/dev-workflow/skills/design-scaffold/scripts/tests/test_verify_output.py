#!/usr/bin/env python3
"""
Tests for verify_output.py — the design-scaffold output guardrail.

Runs under pytest (`python -m pytest scripts/tests/`) and standalone
(`python scripts/tests/test_verify_output.py`).
"""

import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_output as vo  # noqa: E402


def _write(dirpath, name, content):
    p = Path(dirpath) / name
    p.write_text(content, encoding="utf-8")
    return p


def test_clean_scaffold_passes():
    """A stubbed file with no logic produces no FAIL."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "Service.cs",
                "/// <summary>Posts a journal.</summary>\n"
                "public Task<Guid> PostAsync(Guid id)\n{\n"
                "    throw new NotImplementedException();\n}\n")
        _, fails = vo.report("design-scaffold", vo.evaluate(d))
        assert fails == 0


def test_implemented_file_fails():
    """A file with control-flow logic and no stub marker is flagged FAIL."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "Service.cs",
                "public int Sum(int[] xs)\n{\n"
                "    var total = 0;\n"
                "    foreach (var x in xs) { total += x; }\n"
                "    return total;\n}\n")
        results = vo.evaluate(d)
        assert any(level == "FAIL" for level, _ in results)


def test_mixed_body_warns():
    """Logic alongside a stub marker is a WARN, not a hard FAIL."""
    with tempfile.TemporaryDirectory() as d:
        _write(d, "service.py",
                "def run(self, items):\n"
                '    """Run."""\n'
                "    for i in items:\n"
                "        pass\n"
                "    raise NotImplementedError\n")
        results = vo.evaluate(d)
        assert any(level == "WARN" for level, _ in results)
        assert not any(level == "FAIL" for level, _ in results)


def test_missing_path_fails():
    results = vo.evaluate("does-not-exist-xyz")
    assert any(level == "FAIL" for level, _ in results)


def test_no_sources_warns():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "README.md", "# notes\n")
        results = vo.evaluate(d)
        assert any(level == "WARN" for level, _ in results)
        assert not any(level == "FAIL" for level, _ in results)


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
