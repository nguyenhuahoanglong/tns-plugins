"""Spec-first test for DoD-1.7 shared Pro-to-Lite harness synchronization.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[7]
SYNC_SCRIPT = REPO_ROOT / "scripts" / "pipeline" / "Sync-CodeReviewSharedAssets.ps1"


def test_tc_016_shared_sync_check_mode_verifies_pro_and_lite_harness_parity() -> None:
    """TC-016 / DoD-1.7: sync check validates both shipped harness copies.

    Steps:
      1. Locate the canonical shared-sync script.
      2. Run it in non-mutating Check mode.
      3. Verify a synchronized Pro/Lite harness exits successfully and reports check mode.
    """
    # Arrange
    assert SYNC_SCRIPT.is_file(), "shared-sync script must be shipped at scripts/pipeline/Sync-CodeReviewSharedAssets.ps1"

    # Act
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(SYNC_SCRIPT), "-Mode", "Check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "CHECK" in (completed.stdout + completed.stderr).upper()
