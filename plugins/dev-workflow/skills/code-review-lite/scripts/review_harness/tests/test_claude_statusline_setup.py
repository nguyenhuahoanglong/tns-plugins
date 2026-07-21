"""Spec-first setup lifecycle regressions for DoD-1.3.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 live-contract audit.
"""

from __future__ import annotations

import json
from pathlib import Path

from review_harness.claude_statusline_setup import check_installation, install_bridge, uninstall_bridge


def test_tc_034_install_and_uninstall_preserve_existing_statusline_and_settings(tmp_path: Path) -> None:
    """TC-034 / DoD-1.3: setup delegates to and restores the prior status-line command.

    Steps:
      1. Install the bridge over settings containing an existing status-line command.
      2. Verify check mode passes and the original command is backed up for delegation.
      3. Uninstall and verify all original settings are restored exactly.
    """
    # Arrange
    settings_path = tmp_path / "settings.json"
    source_bridge = tmp_path / "source_bridge.py"
    stable_bridge = tmp_path / "stable" / "bridge.py"
    original = {
        "theme": "dark",
        "statusLine": {"type": "command", "command": "existing-status --compact", "padding": 1},
    }
    settings_path.write_text(json.dumps(original), encoding="utf-8")
    source_bridge.write_text("print('bridge')\n", encoding="utf-8")

    # Act
    installed = install_bridge(settings_path, source_bridge, stable_bridge)
    checked = check_installation(settings_path, stable_bridge)
    configured = json.loads(settings_path.read_text(encoding="utf-8"))
    backup_path = stable_bridge.with_suffix(stable_bridge.suffix + ".settings-backup.json")
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    removed = uninstall_bridge(settings_path, stable_bridge)

    # Assert
    assert installed["status"] == "pass"
    assert checked["status"] == "pass"
    assert "existing-status --compact" in configured["statusLine"]["command"]
    assert backup == {"statusLine": original["statusLine"]}
    assert removed["status"] == "pass"
    assert json.loads(settings_path.read_text(encoding="utf-8")) == original
    assert not stable_bridge.exists()
    assert not backup_path.exists()


def test_tc_035_setup_lifecycle_is_idempotent(tmp_path: Path) -> None:
    """TC-035 / DoD-1.3: repeated setup operations preserve one stable wrapper lifecycle.

    Steps:
      1. Install and check the same bridge twice.
      2. Verify the wrapper and original delegate are each configured once.
      3. Uninstall twice and verify the original settings remain restored.
    """
    # Arrange
    settings_path = tmp_path / "settings.json"
    source_bridge = tmp_path / "source_bridge.py"
    stable_bridge = tmp_path / "stable" / "bridge.py"
    original = {"statusLine": {"type": "command", "command": "existing-status --compact"}, "theme": "dark"}
    settings_path.write_text(json.dumps(original), encoding="utf-8")
    source_bridge.write_text("print('bridge')\n", encoding="utf-8")

    # Act
    first_install = install_bridge(settings_path, source_bridge, stable_bridge)
    second_install = install_bridge(settings_path, source_bridge, stable_bridge)
    second_check = check_installation(settings_path, stable_bridge)
    configured_command = json.loads(settings_path.read_text(encoding="utf-8"))["statusLine"]["command"]
    first_uninstall = uninstall_bridge(settings_path, stable_bridge)
    second_uninstall = uninstall_bridge(settings_path, stable_bridge)

    # Assert
    assert first_install["status"] == "pass"
    assert second_install["status"] == "pass"
    assert second_check["status"] == "pass"
    assert configured_command.count(str(stable_bridge)) == 1
    assert configured_command.count("existing-status --compact") == 1
    assert first_uninstall["status"] == "pass"
    assert second_uninstall["status"] == "pass"
    assert json.loads(settings_path.read_text(encoding="utf-8")) == original
