"""Spec-first live-shape regressions for Claude runtime attestation.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 live-contract audit.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from review_harness.claude_statusline_bridge import sanitize_payload, write_attestation
from review_harness.runtime_preflight import resolve_claude_runtime


def _official_payload(cwd: Path, transcript: Path, *, session_id: str = "session-1") -> dict[str, object]:
    return {
        "session_id": session_id,
        "model": {"id": "claude-sonnet-5", "display_name": "Sonnet 5"},
        "effort": {"level": "medium"},
        "thinking": {"enabled": True},
        "workspace": {"current_dir": str(cwd)},
        "transcript_path": str(transcript),
        "transcript_contents": "must never be persisted",
        "prompt": "must never be persisted",
        "authorization": "Bearer must-never-be-persisted",
        "cost": {"total_cost_usd": 99.99},
    }


def _write_transcript(
    path: Path,
    cwd: Path,
    *,
    session_id: str = "session-1",
    model_id: str = "claude-sonnet-5",
    effort: str = "medium",
) -> None:
    record = {
        "type": "assistant",
        "sessionId": session_id,
        "cwd": str(cwd),
        "message": {
            "role": "assistant",
            "model": model_id,
            "effort": effort,
            "content": [{"type": "text", "text": "private transcript content"}],
        },
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def _normalized_attestation(cwd: Path, transcript: Path, *, session_id: str = "session-1") -> dict[str, object]:
    return {
        "host": "claude",
        "sessionId": session_id,
        "modelId": "claude-sonnet-5",
        "effort": "medium",
        "thinkingEnabled": True,
        "cwd": str(cwd),
        "transcriptPath": str(transcript),
    }


def test_tc_021_normalizes_official_claude_payload_without_content_fields(tmp_path: Path) -> None:
    """TC-021 / DoD-1.3: official nested status data becomes privacy-safe evidence.

    Steps:
      1. Provide the official nested Claude status-line payload shape.
      2. Sanitize it for cache persistence.
      3. Verify runtime and cross-check metadata remain while unrelated/content fields do not.
    """
    # Arrange
    transcript = tmp_path / "transcript.jsonl"
    payload = _official_payload(tmp_path, transcript)

    # Act
    sanitized = sanitize_payload(payload)

    # Assert
    assert sanitized == _normalized_attestation(tmp_path, transcript)
    assert "transcript_contents" not in sanitized
    assert "prompt" not in sanitized
    assert "authorization" not in sanitized
    assert "cost" not in sanitized
    assert "display_name" not in sanitized


def test_tc_022_resolves_same_session_cwd_and_transcript_runtime_evidence(tmp_path: Path) -> None:
    """TC-022 / DoD-1.3: status cache passes only after live transcript cross-checks agree.

    Steps:
      1. Store matching official status-line evidence and transcript metadata.
      2. Resolve Claude runtime evidence for the current working directory.
      3. Verify exact model, effort, session, directory, and transcript checks pass.
    """
    # Arrange
    attestation_root = tmp_path / "attestations"
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, tmp_path)
    write_attestation(_official_payload(tmp_path, transcript), attestation_root)

    # Act
    result = resolve_claude_runtime(attestation_root, tmp_path)

    # Assert
    assert result["status"] == "pass"
    assert result["sessionId"] == "session-1"
    assert result["modelId"] == "claude-sonnet-5"
    assert result["effort"] == "medium"
    assert set(result["crossChecks"]) >= {"sessionId", "cwd", "transcript-model", "transcript-effort"}


def test_tc_023_rejects_stale_claude_attestation(tmp_path: Path) -> None:
    """TC-023 / DoD-1.1: stale Claude status evidence fails closed.

    Steps:
      1. Store a valid normalized attestation with an old modification time.
      2. Resolve it with a short freshness window.
      3. Verify stale evidence is blocked with its stable reason code.
    """
    # Arrange
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, tmp_path)
    record = attestation_root / "session-1.json"
    record.write_text(json.dumps(_normalized_attestation(tmp_path, transcript)), encoding="utf-8")
    old = time.time() - 600
    os.utime(record, (old, old))

    # Act
    result = resolve_claude_runtime(attestation_root, tmp_path, max_age_seconds=120)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "stale_runtime_evidence"


def test_tc_024_rejects_claude_attestation_for_different_working_directory(tmp_path: Path) -> None:
    """TC-024 / DoD-1.3: another workspace's attestation cannot authorize this review.

    Steps:
      1. Store fresh evidence bound to a different working directory.
      2. Resolve evidence for the current directory.
      3. Verify the directory mismatch is blocked.
    """
    # Arrange
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, tmp_path / "other")
    (attestation_root / "session-1.json").write_text(
        json.dumps(_normalized_attestation(tmp_path / "other", transcript)), encoding="utf-8"
    )

    # Act
    result = resolve_claude_runtime(attestation_root, tmp_path)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "cwd_mismatch"


@pytest.mark.parametrize(
    ("transcript_model", "transcript_effort", "reason_code"),
    [
        ("claude-opus-5", "medium", "transcript_model_mismatch"),
        ("claude-sonnet-5", "high", "transcript_effort_mismatch"),
    ],
)
def test_tc_025_rejects_claude_transcript_runtime_disagreement(
    tmp_path: Path, transcript_model: str, transcript_effort: str, reason_code: str
) -> None:
    """TC-025 / DoD-1.3: transcript runtime metadata must agree with status evidence.

    Steps:
      1. Store fresh status evidence and a same-session transcript.
      2. Make transcript model or effort disagree with the attestation.
      3. Verify the mismatch is blocked with a precise reason code.
    """
    # Arrange
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, tmp_path, model_id=transcript_model, effort=transcript_effort)
    (attestation_root / "session-1.json").write_text(
        json.dumps(_normalized_attestation(tmp_path, transcript)), encoding="utf-8"
    )

    # Act
    result = resolve_claude_runtime(attestation_root, tmp_path)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == reason_code


def test_tc_026_rejects_ambiguous_equally_current_claude_sessions(tmp_path: Path) -> None:
    """TC-026 / DoD-1.3: equally current session records cannot be selected arbitrarily.

    Steps:
      1. Store two fresh, equally current attestations for the same workspace.
      2. Resolve Claude runtime evidence.
      3. Verify resolution blocks the ambiguous session choice.
    """
    # Arrange
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    transcript_one = tmp_path / "one.jsonl"
    transcript_two = tmp_path / "two.jsonl"
    _write_transcript(transcript_one, tmp_path, session_id="session-1")
    _write_transcript(transcript_two, tmp_path, session_id="session-2")
    first = attestation_root / "session-1.json"
    second = attestation_root / "session-2.json"
    first.write_text(json.dumps(_normalized_attestation(tmp_path, transcript_one, session_id="session-1")), encoding="utf-8")
    second.write_text(json.dumps(_normalized_attestation(tmp_path, transcript_two, session_id="session-2")), encoding="utf-8")
    same_time = time.time()
    os.utime(first, (same_time, same_time))
    os.utime(second, (same_time, same_time))

    # Act
    result = resolve_claude_runtime(attestation_root, tmp_path)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "ambiguous_runtime_evidence"
