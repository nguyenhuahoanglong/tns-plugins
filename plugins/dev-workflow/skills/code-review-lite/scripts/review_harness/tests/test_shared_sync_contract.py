"""Spec-first test for DoD-1.7 shared Pro-to-Lite harness synchronization.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[7]
SKILLS_ROOT = Path(__file__).resolve().parents[4]
SYNC_SCRIPT = REPO_ROOT / "scripts" / "pipeline" / "Sync-CodeReviewSharedAssets.ps1"


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
        and path.suffix != ".pyc"
    }


def test_tc_016_shared_sync_check_mode_verifies_pro_and_lite_harness_parity() -> None:
    """TC-016 / DoD-1.7: sync check validates both shipped harness copies.

    Steps:
      1. Locate the canonical shared-sync script.
      2. Run it in non-mutating Check mode.
      3. Verify a synchronized Pro/Lite harness exits successfully and reports check mode.
    """
    if not SYNC_SCRIPT.is_file():
        pro = SKILLS_ROOT / "code-review-pro" / "scripts" / "review_harness"
        lite = SKILLS_ROOT / "code-review-lite" / "scripts" / "review_harness"
        assert pro.is_dir() and lite.is_dir(), "packaged Pro/Lite harnesses must both exist"
        assert _snapshot(pro) == _snapshot(lite), "packaged Pro/Lite harnesses must be byte-identical"
        return

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(SYNC_SCRIPT), "-Mode", "Check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "CHECK" in (completed.stdout + completed.stderr).upper()
