"""Spec-first tests for DoD-1.3 Claude status-line attestation behavior.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from review_harness.claude_statusline_bridge import (
    forward_statusline,
    sanitize_payload,
    write_attestation,
)


def test_tc_008_sanitizes_claude_payload_to_approved_attestation_fields() -> None:
    """TC-008 / DoD-1.3: cache contains only permitted runtime attestation data.

    Steps:
      1. Provide a status-line payload with trusted and unrelated fields.
      2. Sanitize the payload for persistence.
      3. Verify only approved attestation fields remain.
    """
    # Arrange
    payload = {
        "sessionId": "session-1",
        "modelId": "claude-sonnet-5",
        "effort": "medium",
        "thinkingEnabled": True,
        "cwd": "C:/private/repo",
        "transcriptPath": "C:/private/transcript.jsonl",
        "authorization": "must-not-persist",
    }

    # Act
    sanitized = sanitize_payload(payload)

    # Assert
    assert sanitized == {
        "host": "claude",
        "sessionId": "session-1",
        "modelId": "claude-sonnet-5",
        "effort": "medium",
        "thinkingEnabled": True,
    }


def test_tc_009_writes_complete_sanitized_attestation_without_temp_artifacts(tmp_path: Path) -> None:
    """TC-009 / DoD-1.3: cache write is atomic and never leaves partial files.

    Steps:
      1. Provide an approved runtime payload and empty cache directory.
      2. Persist its attestation.
      3. Verify one complete sanitized JSON record exists and no temporary record remains.
    """
    # Arrange
    payload = {"sessionId": "session-1", "modelId": "claude-sonnet-5", "effort": "medium", "thinkingEnabled": True, "extra": "drop"}

    # Act
    cache_path = write_attestation(payload, tmp_path)

    # Assert
    assert cache_path.is_file()
    assert json.loads(cache_path.read_text()) == sanitize_payload(payload)
    assert list(tmp_path.glob("*.tmp")) == []


def test_tc_010_forwards_original_payload_and_preserves_delegate_result() -> None:
    """TC-010 / DoD-1.3: the wrapper is transparent to an existing status-line command.

    Steps:
      1. Provide original status-line bytes and a command that echoes standard input.
      2. Forward the payload through the bridge.
      3. Verify delegate exit code and output are returned unchanged.
    """
    # Arrange
    original = b'{"modelId":"claude-sonnet-5","private":"retain-for-delegate"}'
    command = f'"{sys.executable}" -c "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"'

    # Act
    exit_code, stdout, stderr = forward_statusline(original, command)

    # Assert
    assert exit_code == 0
    assert stdout == original
    assert stderr == b""
