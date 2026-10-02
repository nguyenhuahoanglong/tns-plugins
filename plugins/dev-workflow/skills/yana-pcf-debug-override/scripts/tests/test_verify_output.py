#!/usr/bin/env python3
"""Tests for skill guardrail."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_output as verifier  # noqa: E402


class VerifyOutputTests(unittest.TestCase):
    def test_missing_root_fails(self) -> None:
        results = verifier.evaluate("does-not-exist")
        self.assertIn(("FAIL", "skill root exists: " + str(Path("does-not-exist").resolve())), results)

    def test_real_skill_passes(self) -> None:
        root = SCRIPTS_DIR.parent
        _, failures = verifier.report(verifier.evaluate(root))
        self.assertEqual(failures, 0)


if __name__ == "__main__":
    unittest.main()
