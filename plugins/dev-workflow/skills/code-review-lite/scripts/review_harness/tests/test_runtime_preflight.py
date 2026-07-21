"""Spec-first tests for DoD-1.1, DoD-1.2, and DoD-1.4.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_harness.runtime_preflight import (
    evaluate_runtime,
    evaluate_session,
    parse_model_id,
    resolve_codex_runtime,
)


@pytest.mark.parametrize(
    ("model_id", "expected_generation", "expected_tier"),
    [
        ("gpt-5.6-terra", (5, 6), "terra"),
        ("gpt-5.6-sol", (5, 6), "sol"),
        ("gpt-5.7-terra", (5, 7), "terra"),
    ],
)
def test_tc_001_parses_numeric_future_gpt_generations_semantically(
    model_id: str, expected_generation: tuple[int, int], expected_tier: str
) -> None:
    """TC-001 / DoD-1.1: future numeric versions remain policy-evaluable.

    Steps:
      1. Supply a trusted Codex GPT model identifier.
      2. Parse its numeric generation and tier.
      3. Verify the parsed result preserves both values without a fixed-version allowlist.
    """
    # Arrange
    # Act
    parsed = parse_model_id("codex", model_id)

    # Assert
    assert parsed["modelId"] == model_id
    assert tuple(parsed["generation"]) == expected_generation
    assert parsed["tier"] == expected_tier


@pytest.mark.parametrize(
    ("model_id", "effort"),
    [
        ("gpt-5.6-terra", "medium"),
        ("gpt-5.6-sol", "high"),
        ("gpt-5.7-terra", "medium"),
    ],
)
def test_tc_002_accepts_minimum_or_higher_eligible_codex_runtime(
    model_id: str, effort: str
) -> None:
    """TC-002 / DoD-1.1: eligible runtime evidence passes preflight policy.

    Steps:
      1. Supply a supported Codex model and its approved effort level.
      2. Evaluate the runtime policy.
      3. Verify the returned attestation passes and records exact model and effort.
    """
    # Arrange
    # Act
    result = evaluate_runtime("codex", model_id, effort)

    # Assert
    assert result["status"] == "pass"
    assert result["modelId"] == model_id
    assert result["effort"] == effort


@pytest.mark.parametrize(
    ("model_id", "effort", "reason_code"),
    [
        ("gpt-5.6-luna", "high", "tier_below_minimum"),
        ("gpt-5.6-terra", "low", "effort_below_minimum"),
        ("gpt-5.6-unknown", "high", "unknown_tier"),
        ("", "medium", "missing_runtime_evidence"),
    ],
)
def test_tc_003_hard_stops_untrusted_or_underpowered_runtime(
    model_id: str, effort: str, reason_code: str
) -> None:
    """TC-003 / DoD-1.1: insufficient runtime evidence cannot start a review.

    Steps:
      1. Supply a below-minimum or incomplete runtime record.
      2. Evaluate the runtime policy.
      3. Verify preflight is blocked with a stable reason code.
    """
    # Arrange
    # Act
    result = evaluate_runtime("codex", model_id, effort)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == reason_code


def test_tc_004_selects_only_the_rollout_matching_requested_thread(tmp_path: Path) -> None:
    """TC-004 / DoD-1.2: select runtime evidence by exact thread UUID.

    Steps:
      1. Store two rollout records with different thread identifiers.
      2. Resolve runtime evidence for one requested thread.
      3. Verify only that thread's rollout is returned.
    """
    # Arrange
    (tmp_path / "other.json").write_text(json.dumps({"threadId": "other", "modelId": "gpt-5.6-luna", "effort": "low"}))
    (tmp_path / "requested.json").write_text(json.dumps({"threadId": "thread-123", "modelId": "gpt-5.7-terra", "effort": "medium"}))

    # Act
    result = resolve_codex_runtime("thread-123", tmp_path)

    # Assert
    assert result["status"] == "pass"
    assert result["sessionId"] == "thread-123"
    assert result["modelId"] == "gpt-5.7-terra"
    assert result["effort"] == "medium"


def test_tc_005_blocks_conflicting_duplicate_current_runtime_fields(tmp_path: Path) -> None:
    """TC-005 / DoD-1.2: conflicting same-record runtime metadata is rejected.

    Steps:
      1. Store one requested rollout with conflicting duplicate model fields.
      2. Resolve the requested thread's runtime evidence.
      3. Verify the attestation is blocked rather than choosing one field silently.
    """
    # Arrange
    (tmp_path / "conflict.json").write_text(
        json.dumps({"threadId": "thread-123", "modelId": "gpt-5.6-terra", "model": "gpt-5.6-luna", "effort": "medium"})
    )

    # Act
    result = resolve_codex_runtime("thread-123", tmp_path)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "conflicting_runtime_evidence"


def test_tc_006_requires_confirmation_for_existing_session_then_records_override(tmp_path: Path) -> None:
    """TC-006 / DoD-1.4: existing task override is explicit and auditable.

    Steps:
      1. Provide a transcript containing a prior user task.
      2. Evaluate it without confirmation and verify it needs confirmation.
      3. Re-evaluate with explicit override and verify pass plus recorded override.
    """
    # Arrange
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"role":"user","content":"Review this pull request"}\n')

    # Act
    without_override = evaluate_session(transcript)
    with_override = evaluate_session(transcript, allow_existing_session=True)

    # Assert
    assert without_override["status"] == "confirmation-required"
    assert with_override["status"] == "pass"
    assert with_override["overrideRecorded"] is True


def test_tc_007_allows_fresh_session_without_override(tmp_path: Path) -> None:
    """TC-007 / DoD-1.4: a fresh task starts without manual confirmation.

    Steps:
      1. Provide an empty transcript.
      2. Evaluate the session gate.
      3. Verify the session is classified fresh and passes without an override.
    """
    # Arrange
    transcript = tmp_path / "fresh.jsonl"
    transcript.write_text("")

    # Act
    result = evaluate_session(transcript)

    # Assert
    assert result["status"] == "pass"
    assert result["sessionStatus"] == "fresh"
    assert result["overrideRecorded"] is False
