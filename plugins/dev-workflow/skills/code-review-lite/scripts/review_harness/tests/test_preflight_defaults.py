"""Spec-first preflight routing and persistence regressions.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 final live-contract audit.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from review_harness import runtime_preflight


def _passing_runtime(host: str, session_id: str) -> dict[str, Any]:
    model_id = "gpt-5.6-sol" if host == "codex" else "claude-sonnet-5"
    return {
        "status": "pass",
        "host": host,
        "sessionId": session_id,
        "modelId": model_id,
        "effort": "high",
        "crossChecks": [],
    }


def test_tc_036_codex_preflight_defaults_to_home_sessions_and_uses_own_rollout_as_session_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-036 / DoD-1.2: Codex uses its default rollout as session evidence.

    Steps:
      1. Set a Codex thread while omitting the sessions-root environment variable.
      2. Run preflight from an unrelated current working directory.
      3. Verify it discovers the rollout under ~/.codex/sessions and records a fresh session.
    """
    # Arrange
    home = tmp_path / "home"
    cwd = tmp_path / "workspace"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODEX_SESSIONS_ROOT", raising=False)
    monkeypatch.delenv("CODE_REVIEW_HOST", raising=False)
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    sessions_root = home / ".codex" / "sessions"
    sessions_root.mkdir(parents=True)
    (sessions_root / "thread-123.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"type": "session_meta", "payload": {"id": "thread-123"}},
                {
                    "type": "turn_context",
                    "payload": {"model": "gpt-5.6-sol", "effort": "high"},
                },
                {"role": "user", "content": "Review the change"},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    # Act
    result = runtime_preflight.run_preflight(host="codex")

    # Assert
    assert result["status"] == "pass"
    assert result["sessionStatus"] == "fresh"
    assert result["overrideRecorded"] is False


def test_tc_037_preflight_blocks_a_passing_runtime_when_no_session_evidence_is_discoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-037 / DoD-1.3: runtime approval alone cannot approve a review.

    Steps:
      1. Supply a runtime resolver which passes policy but has no discoverable session.
      2. Omit any explicit review transcript.
      3. Verify preflight fails closed with missing-session evidence.
    """
    # Arrange
    monkeypatch.setattr(
        runtime_preflight,
        "resolve_codex_runtime",
        lambda thread_id, sessions_root: _passing_runtime("codex", thread_id),
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODE_REVIEW_HOST", raising=False)
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    # Act
    result = runtime_preflight.run_preflight(host="codex")

    # Assert
    assert result["status"] == "blocked"
    assert result["reasonCode"] == "missing_session_evidence"


def test_tc_040_codex_existing_rollout_session_requires_confirmation_without_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-040 / DoD-1.3: Codex discovers its own existing rollout session.

    Steps:
      1. Store an exact Codex rollout with prior user and assistant activity.
      2. Run preflight without CODE_REVIEW_TRANSCRIPT or an override.
      3. Verify the existing session requires confirmation.
    """
    home = tmp_path / "home"
    sessions_root = home / ".codex" / "sessions"
    sessions_root.mkdir(parents=True)
    (sessions_root / "thread-123.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"type": "session_meta", "payload": {"id": "thread-123"}},
                {"type": "turn_context", "payload": {"model": "gpt-5.6-sol", "effort": "high"}},
                {"role": "user", "content": "Earlier request"},
                {"role": "assistant", "content": "Earlier reply"},
                {"role": "user", "content": "Review now"},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    result = runtime_preflight.run_preflight(host="codex")

    assert result["status"] == "confirmation-required"
    assert result["sessionStatus"] == "existing"
    assert result["overrideRecorded"] is False


def test_tc_041_codex_existing_rollout_session_records_an_explicit_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-041 / DoD-1.3: explicit confirmation permits a discovered existing session.

    Steps:
      1. Store an exact Codex rollout with prior user and assistant activity.
      2. Run preflight with the existing-session override and no transcript environment variable.
      3. Verify the result is an approved existing session with the override recorded.
    """
    home = tmp_path / "home"
    sessions_root = home / ".codex" / "sessions"
    sessions_root.mkdir(parents=True)
    (sessions_root / "thread-123.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"type": "session_meta", "payload": {"id": "thread-123"}},
                {"type": "turn_context", "payload": {"model": "gpt-5.6-sol", "effort": "high"}},
                {"role": "user", "content": "Earlier request"},
                {"role": "assistant", "content": "Earlier reply"},
                {"role": "user", "content": "Review now"},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    result = runtime_preflight.run_preflight(host="codex", allow_existing_session=True)

    assert result["status"] == "pass"
    assert result["sessionStatus"] == "existing"
    assert result["overrideRecorded"] is True


def test_tc_042_claude_preflight_requires_a_trusted_attestation_transcript_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-042 / DoD-1.3: a Claude attestation without its trusted transcript is insufficient.

    Steps:
      1. Store a current, policy-compliant Claude attestation without transcriptPath.
      2. Run Claude preflight without CODE_REVIEW_TRANSCRIPT.
      3. Verify it fails closed with missing-session evidence.
    """
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    (attestation_root / "current.json").write_text(
        json.dumps(
            {
                "host": "claude",
                "sessionId": "session-1",
                "modelId": "claude-sonnet-5",
                "effort": "high",
                "cwd": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_ATTESTATION_ROOT", str(attestation_root))
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    result = runtime_preflight.run_preflight(host="claude")

    assert result["status"] == "blocked"
    assert result["reasonCode"] == "missing_session_evidence"


def test_tc_046_claude_preflight_requires_an_attested_same_session_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-046 / DoD-1.3: a Claude attestation must include the reviewed workspace.

    Steps:
      1. Store a current, policy-compliant Claude attestation without cwd.
      2. Run Claude preflight without an external transcript override.
      3. Verify it fails closed because the same-session workspace was not attested.
    """
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "session-1",
                "cwd": str(tmp_path),
                "message": {"role": "assistant", "model": "claude-sonnet-5", "effort": "high"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (attestation_root / "current.json").write_text(
        json.dumps(
            {
                "host": "claude",
                "sessionId": "session-1",
                "modelId": "claude-sonnet-5",
                "effort": "high",
                "transcriptPath": str(transcript),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_ATTESTATION_ROOT", str(attestation_root))
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    result = runtime_preflight.run_preflight(host="claude")

    assert result["status"] == "blocked"
    assert result["reasonCode"] == "missing_session_evidence"


def test_tc_050_claude_preflight_binds_session_evaluation_to_the_selected_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-050 / DoD-1.3: an attestation race cannot switch session evidence.

    Steps:
      1. Select an attestation whose exact transcript contains an existing review session.
      2. Make another attestation with a fresh transcript become latest after runtime resolution.
      3. Verify preflight still requires confirmation, then records an explicit override for the
         originally selected session.
    """
    attestation_root = tmp_path / "attestations"
    attestation_root.mkdir()
    existing_transcript = tmp_path / "session-1.jsonl"
    fresh_transcript = tmp_path / "session-2.jsonl"

    existing_transcript.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"message": {"role": "user", "content": "Earlier request"}},
                {
                    "type": "assistant",
                    "sessionId": "session-1",
                    "cwd": str(tmp_path),
                    "message": {"role": "assistant", "model": "claude-sonnet-5", "effort": "high"},
                },
                {"message": {"role": "user", "content": "Review now"}},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    fresh_transcript.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"message": {"role": "user", "content": "Review now"}},
                {
                    "type": "assistant",
                    "sessionId": "session-2",
                    "cwd": str(tmp_path),
                    "message": {"role": "assistant", "model": "claude-opus-5", "effort": "high"},
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    selected_attestation = attestation_root / "session-1.json"
    concurrent_attestation = attestation_root / "session-2.json"
    selected_attestation.write_text(
        json.dumps(
            {
                "host": "claude",
                "sessionId": "session-1",
                "modelId": "claude-sonnet-5",
                "effort": "high",
                "cwd": str(tmp_path),
                "transcriptPath": str(existing_transcript),
            }
        ),
        encoding="utf-8",
    )
    concurrent_attestation.write_text(
        json.dumps(
            {
                "host": "claude",
                "sessionId": "session-2",
                "modelId": "claude-opus-5",
                "effort": "high",
                "cwd": str(tmp_path),
                "transcriptPath": str(fresh_transcript),
            }
        ),
        encoding="utf-8",
    )

    original_resolve = runtime_preflight.resolve_claude_runtime
    current_time = time.time()

    def resolve_then_publish_newer_attestation(root: Path, cwd: Path) -> dict[str, Any]:
        resolved = original_resolve(root, cwd)
        os.utime(concurrent_attestation, (current_time + 20, current_time + 20))
        return resolved

    def run_with_race(*, allow_existing_session: bool) -> dict[str, Any]:
        os.utime(concurrent_attestation, (current_time, current_time))
        os.utime(selected_attestation, (current_time + 10, current_time + 10))
        return runtime_preflight.run_preflight(
            host="claude", allow_existing_session=allow_existing_session
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_ATTESTATION_ROOT", str(attestation_root))
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)
    monkeypatch.setattr(
        runtime_preflight, "resolve_claude_runtime", resolve_then_publish_newer_attestation
    )

    without_override = run_with_race(allow_existing_session=False)
    with_override = run_with_race(allow_existing_session=True)

    assert without_override["status"] == "confirmation-required"
    assert without_override["sessionId"] == "session-1"
    assert without_override["modelId"] == "claude-sonnet-5"
    assert without_override["sessionStatus"] == "existing"
    assert without_override["overrideRecorded"] is False
    assert with_override["status"] == "pass"
    assert with_override["sessionId"] == "session-1"
    assert with_override["modelId"] == "claude-sonnet-5"
    assert with_override["sessionStatus"] == "existing"
    assert with_override["overrideRecorded"] is True


def test_tc_051_codex_preflight_prefers_the_bound_rollout_over_an_unrelated_env_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-051 / DoD-1.3: an environment transcript cannot replace a bound Codex rollout.

    Steps:
      1. Resolve a Codex thread whose exact rollout contains an existing review session.
      2. Point CODE_REVIEW_TRANSCRIPT to an unrelated fresh session.
      3. Verify the bound rollout still requires confirmation, then records its explicit override.
    """
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    bound_rollout = sessions_root / "thread-123.jsonl"
    unrelated_transcript = tmp_path / "unrelated-fresh.jsonl"

    bound_rollout.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"type": "session_meta", "payload": {"id": "thread-123"}},
                {
                    "type": "turn_context",
                    "timestamp": "2026-07-21T10:00:00Z",
                    "payload": {"model": "gpt-5.6-sol", "effort": "high"},
                },
                {"message": {"role": "user", "content": "Earlier request"}},
                {"message": {"role": "assistant", "content": "Earlier reply"}},
                {"message": {"role": "user", "content": "Review now"}},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    unrelated_transcript.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"message": {"role": "user", "content": "Unrelated new review"}},
                {"message": {"role": "assistant", "content": "Starting"}},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.setenv("CODEX_SESSIONS_ROOT", str(sessions_root))
    monkeypatch.setenv("CODE_REVIEW_TRANSCRIPT", str(unrelated_transcript))

    without_override = runtime_preflight.run_preflight(host="codex")
    with_override = runtime_preflight.run_preflight(host="codex", allow_existing_session=True)

    assert without_override["status"] == "confirmation-required"
    assert without_override["sessionId"] == "thread-123"
    assert without_override["sessionStatus"] == "existing"
    assert without_override["overrideRecorded"] is False
    assert with_override["status"] == "pass"
    assert with_override["sessionId"] == "thread-123"
    assert with_override["sessionStatus"] == "existing"
    assert with_override["overrideRecorded"] is True


def test_tc_038_preflight_output_uses_atomic_same_directory_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-038 / DoD-1.1: persisted preflight evidence is complete or unchanged.

    Steps:
      1. Resolve a valid runtime while recording file writes and replacements.
      2. Persist the preflight result to a nested output path.
      3. Verify a sibling temporary file replaced the target and no temporary file remains.
    """
    # Arrange
    output_path = tmp_path / "evidence" / "preflight.json"
    direct_writes: list[Path] = []
    replacements: list[tuple[Path, Path]] = []
    original_write_text = Path.write_text
    original_replace = Path.replace

    def track_write_text(path: Path, *args: object, **kwargs: object) -> int:
        if path == output_path:
            direct_writes.append(path)
        return original_write_text(path, *args, **kwargs)

    def track_replace(path: Path, target: Path) -> Path:
        replacements.append((path, Path(target)))
        return original_replace(path, target)

    monkeypatch.setattr(
        runtime_preflight,
        "resolve_codex_runtime",
        lambda thread_id, sessions_root: _passing_runtime("codex", thread_id),
    )
    monkeypatch.setattr(Path, "write_text", track_write_text)
    monkeypatch.setattr(Path, "replace", track_replace)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODE_REVIEW_HOST", raising=False)
    monkeypatch.delenv("CODE_REVIEW_TRANSCRIPT", raising=False)

    # Act
    result = runtime_preflight.run_preflight(host="codex", output_path=output_path)

    # Assert
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert direct_writes == []
    assert len(replacements) == 1
    temporary, target = replacements[0]
    assert target == output_path
    assert temporary.parent == output_path.parent
    assert temporary.name.endswith(".tmp")
    assert list(output_path.parent.glob("*.tmp")) == []


@pytest.mark.parametrize(
    ("model_id", "expected_generation", "expected_tier"),
    [
        ("claude-opus-5-1", [5, 1], "opus"),
        ("claude-sonnet-5-0", [5, 0], "sonnet"),
        ("claude-sonnet-5", [5], "sonnet"),
        ("claude-opus-5.1", [5, 1], "opus"),
    ],
)
def test_tc_039_parses_real_claude_hyphen_generation_ids(
    model_id: str, expected_generation: list[int], expected_tier: str
) -> None:
    """TC-039 / DoD-1.1: Claude base, hyphen, and retained dot generations are eligible.

    Steps:
      1. Supply a trusted Claude model identifier in a supported generation style.
      2. Parse and evaluate the model with medium effort.
      3. Verify its tier/generation are semantic and the runtime passes policy.
    """
    # Arrange / Act
    parsed = runtime_preflight.parse_model_id("claude", model_id)
    result = runtime_preflight.evaluate_runtime("claude", model_id, "medium")

    # Assert
    assert parsed["generation"] == expected_generation
    assert parsed["tier"] == expected_tier
    assert result["status"] == "pass"
