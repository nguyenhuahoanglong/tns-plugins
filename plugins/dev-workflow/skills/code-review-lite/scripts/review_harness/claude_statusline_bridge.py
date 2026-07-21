#!/usr/bin/env python3
"""Capture Claude status-line runtime payload while transparently delegating."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

APPROVED_FIELDS = ("host", "sessionId", "modelId", "effort", "thinkingEnabled", "cwd", "transcriptPath")


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the sole fields allowed to persist outside the status-line process."""
    # Official Claude status-line objects are nested.  Retain only attestation
    # fields necessary for the later session/cwd/transcript cross-check.
    official = isinstance(payload.get("model"), dict)
    result = {"host": "claude", "sessionId": payload.get("session_id") if official else payload.get("sessionId"),
              "modelId": payload.get("model", {}).get("id") if official else payload.get("modelId"),
              "effort": payload.get("effort", {}).get("level") if official else payload.get("effort"),
              "thinkingEnabled": payload.get("thinking", {}).get("enabled") if official else payload.get("thinkingEnabled")}
    if official:
        result.update({"cwd": payload.get("workspace", {}).get("current_dir"), "transcriptPath": payload.get("transcript_path")})
    return result


def write_attestation(payload: dict[str, Any], attestation_root: Path) -> Path:
    """Atomically persist approved metadata, including cwd/transcript paths for cross-checks, never their content, prompts, or auth."""
    value = sanitize_payload(payload)
    attestation_root.mkdir(parents=True, exist_ok=True)
    session_id = str(value.get("sessionId") or "unknown")
    safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in session_id)
    target = attestation_root / f"{safe_name}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{safe_name}-", suffix=".tmp", dir=str(attestation_root))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(target)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()
    return target


def forward_statusline(payload_bytes: bytes, delegate_command: str | None) -> tuple[int, bytes, bytes]:
    """Pass raw bytes to the previous command and preserve all observable results."""
    if not delegate_command:
        return 0, b"", b""
    completed = subprocess.run(delegate_command, shell=True, input=payload_bytes, capture_output=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Privacy-safe Claude status-line attestation bridge.")
    parser.add_argument("--attestation-root", type=Path, default=Path(os.environ.get("CLAUDE_ATTESTATION_ROOT", Path.home() / ".claude" / "review-attestations")))
    parser.add_argument("--delegate-command", default=os.environ.get("CODE_REVIEW_STATUSLINE_DELEGATE"))
    args = parser.parse_args(argv)
    payload_bytes = sys.stdin.buffer.read()
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("status-line payload must be an object")
        write_attestation(payload, args.attestation_root)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        print(f"status-line attestation error: {error}", file=sys.stderr)
        return 2
    code, stdout, stderr = forward_statusline(payload_bytes, args.delegate_command)
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
