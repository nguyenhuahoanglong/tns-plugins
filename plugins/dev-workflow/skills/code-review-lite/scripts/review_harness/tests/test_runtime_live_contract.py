"""Spec-first live-shape regressions for DoD-1.2 and DoD-1.4.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 live-contract audit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_harness.runtime_preflight import evaluate_session, resolve_codex_runtime


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _turn_context(timestamp: str, model: str, effort: str) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "type": "turn_context",
        "payload": {
            "model": model,
            "effort": effort,
            "collaboration_mode": {
                "model": model,
                "reasoning_effort": effort,
            },
        },
    }


def test_tc_017_selects_latest_turn_context_from_exact_codex_rollout(tmp_path: Path) -> None:
    """TC-017 / DoD-1.2: exact session metadata owns all turns in one rollout.

    Steps:
      1. Store one unrelated rollout and one requested rollout in real JSONL envelopes.
      2. Put an old GPT 5.5 turn before the current GPT 5.6 Sol/high turn.
      3. Verify resolution selects the requested file and its latest turn context.
    """
    # Arrange
    _write_jsonl(
        tmp_path / "other-session.jsonl",
        [
            {"timestamp": "2026-07-21T01:00:00Z", "type": "session_meta", "payload": {"id": "thread-other"}},
            _turn_context("2026-07-21T01:01:00Z", "gpt-5.7-terra", "medium"),
        ],
    )
    _write_jsonl(
        tmp_path / "requested-session.jsonl",
        [
            {"timestamp": "2026-07-21T02:00:00Z", "type": "session_meta", "payload": {"id": "thread-target"}},
            _turn_context("2026-07-21T02:01:00Z", "gpt-5.5", "medium"),
            _turn_context("2026-07-21T02:02:00Z", "gpt-5.6-sol", "high"),
        ],
    )

    # Act
    result = resolve_codex_runtime("thread-target", tmp_path)

    # Assert
    assert result["status"] == "pass"
    assert result["sessionId"] == "thread-target"
    assert result["modelId"] == "gpt-5.6-sol"
    assert result["effort"] == "high"
    assert "latest-turn-context" in result["crossChecks"]


@pytest.mark.parametrize(
    "latest_payload",
    [
        {
            "model": "gpt-5.6-sol",
            "effort": "high",
            "collaboration_mode": {"model": "gpt-5.6-terra", "reasoning_effort": "high"},
        },
        {
            "model": "gpt-5.6-sol",
            "effort": "high",
            "collaboration_mode": {"model": "gpt-5.6-sol", "reasoning_effort": "medium"},
        },
    ],
)
def test_tc_018_rejects_codex_turn_context_runtime_disagreement(
    tmp_path: Path, latest_payload: dict[str, object]
) -> None:
    """TC-018 / DoD-1.2: duplicate current-runtime fields must agree.

    Steps:
      1. Store a requested rollout with one current turn context.
      2. Make its top-level model or effort disagree with collaboration-mode metadata.
      3. Verify runtime resolution blocks the conflicting evidence.
    """
    # Arrange
    _write_jsonl(
        tmp_path / "conflicting-session.jsonl",
        [
            {"timestamp": "2026-07-21T03:00:00Z", "type": "session_meta", "payload": {"id": "thread-target"}},
            {"timestamp": "2026-07-21T03:01:00Z", "type": "turn_context", "payload": latest_payload},
        ],
    )

    # Act
    result = resolve_codex_runtime("thread-target", tmp_path)

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "conflicting_runtime_evidence"


def test_tc_021_reads_only_exact_rollout_filename_candidate_for_live_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-021 / DoD-1.2: exact rollout filename avoids unrelated session reads.

    Steps:
      1. Store the live thread in its canonical rollout filename and add unrelated JSONL files.
      2. Make any read of an unrelated file fail immediately.
      3. Verify the resolver reads the exact rollout candidate and returns its current runtime.
    """
    # Arrange
    thread_id = "4a1e0ab5-5da9-457d-9a14-1aef12b04a3c"
    rollout = tmp_path / f"rollout-2026-07-21T02-00-00-{thread_id}.jsonl"
    unrelated = tmp_path / "rollout-2026-07-21T01-00-00-3a0ae993-9c24-440c-b09b-6f61705ec5e9.jsonl"
    _write_jsonl(
        rollout,
        [
            {"type": "session_meta", "payload": {"id": thread_id}},
            _turn_context("2026-07-21T02:01:00Z", "gpt-5.6-sol", "high"),
        ],
    )
    _write_jsonl(unrelated, [{"not": "a record the live preflight may read"}])

    original_read_text = Path.read_text

    def read_text_only_for_matching_rollout(path: Path, *args: object, **kwargs: object) -> str:
        if path == unrelated:
            raise AssertionError("live lookup read an unrelated rollout despite an exact filename match")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text_only_for_matching_rollout)

    # Act
    result = resolve_codex_runtime(thread_id, tmp_path)

    # Assert
    assert result["status"] == "pass"
    assert result["sessionId"] == thread_id
    assert result["modelId"] == "gpt-5.6-sol"
    assert result["effort"] == "high"


def test_tc_022_allows_collaboration_mode_without_optional_runtime_duplicates(tmp_path: Path) -> None:
    """TC-022 / DoD-1.2: optional collaboration metadata must not conflict by omission.

    Steps:
      1. Store a requested rollout whose turn has valid top-level runtime evidence.
      2. Include non-empty collaboration metadata without model or reasoning-effort duplicates.
      3. Verify resolution accepts the top-level current runtime.
    """
    # Arrange
    _write_jsonl(
        tmp_path / "rollout-2026-07-21T03-00-00-thread-target.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "thread-target"}},
            {
                "timestamp": "2026-07-21T03:01:00Z",
                "type": "turn_context",
                "payload": {
                    "model": "gpt-5.6-sol",
                    "effort": "xhigh",
                    "collaboration_mode": {"team_size": 3},
                },
            },
        ],
    )

    # Act
    result = resolve_codex_runtime("thread-target", tmp_path)

    # Assert
    assert result["status"] == "pass"
    assert result["modelId"] == "gpt-5.6-sol"
    assert result["effort"] == "xhigh"


def test_tc_023_recognizes_prior_nested_response_item_messages_as_existing_session(tmp_path: Path) -> None:
    """TC-023 / DoD-1.4: nested response-item messages participate in session history.

    Steps:
      1. Store a prior nested user/assistant exchange and a current nested user request.
      2. Evaluate the transcript without an override.
      3. Verify confirmation is required, then verify an explicit override is recorded.
    """
    # Arrange
    transcript = tmp_path / "nested-response-items.jsonl"
    _write_jsonl(
        transcript,
        [
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "user", "content": [{"type": "text", "text": "Explain this repository"}]},
            },
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": [{"type": "text", "text": "Repository explained."}]},
            },
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "user", "content": [{"type": "text", "text": "Review this pull request"}]},
            },
        ],
    )

    # Act
    without_override = evaluate_session(transcript)
    with_override = evaluate_session(transcript, allow_existing_session=True)

    # Assert
    assert without_override == {
        "status": "confirmation-required",
        "sessionStatus": "existing",
        "overrideRecorded": False,
    }
    assert with_override == {"status": "pass", "sessionStatus": "existing", "overrideRecorded": True}


def test_tc_019_treats_only_current_real_transcript_request_as_fresh(tmp_path: Path) -> None:
    """TC-019 / DoD-1.4: the current request alone is not prior task history.

    Steps:
      1. Store one real transcript user envelope for the current review request.
      2. Evaluate the session gate without an override.
      3. Verify the task is fresh and passes.
    """
    # Arrange
    transcript = tmp_path / "fresh.jsonl"
    _write_jsonl(
        transcript,
        [
            {
                "type": "user",
                "sessionId": "session-1",
                "message": {"role": "user", "content": [{"type": "text", "text": "Review this pull request"}]},
            }
        ],
    )

    # Act
    result = evaluate_session(transcript)

    # Assert
    assert result == {"status": "pass", "sessionStatus": "fresh", "overrideRecorded": False}


def test_tc_020_requires_and_records_override_for_prior_completed_exchange(tmp_path: Path) -> None:
    """TC-020 / DoD-1.4: completed prior work makes the current request existing-task work.

    Steps:
      1. Store a prior user/assistant exchange followed by the current review request.
      2. Evaluate without and with explicit confirmation.
      3. Verify confirmation is required first and the override is recorded after approval.
    """
    # Arrange
    transcript = tmp_path / "existing.jsonl"
    _write_jsonl(
        transcript,
        [
            {"type": "user", "message": {"role": "user", "content": "Explain this repository"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "Repository explained."}},
            {"type": "user", "message": {"role": "user", "content": "Review this pull request"}},
        ],
    )

    # Act
    without_override = evaluate_session(transcript)
    with_override = evaluate_session(transcript, allow_existing_session=True)

    # Assert
    assert without_override == {
        "status": "confirmation-required",
        "sessionStatus": "existing",
        "overrideRecorded": False,
    }
    assert with_override == {"status": "pass", "sessionStatus": "existing", "overrideRecorded": True}
