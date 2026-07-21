#!/usr/bin/env python3
"""Install, check, or remove the Claude status-line bridge without review-time mutation."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.exists(): return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("settings must be a JSON object")
    return value


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write("\n"); temporary = Path(stream.name)
    temporary.replace(path)


def _backup_path(stable_bridge_path: Path) -> Path:
    return stable_bridge_path.with_suffix(stable_bridge_path.suffix + ".settings-backup.json")


def check_installation(settings_path: Path, stable_bridge_path: Path) -> dict[str, Any]:
    try: settings = _read_settings(settings_path)
    except (OSError, ValueError, json.JSONDecodeError) as error: return {"status": "blocked", "reasonCode": "invalid_settings", "detail": str(error)}
    command = settings.get("statusLine", {}).get("command") if isinstance(settings.get("statusLine"), dict) else None
    return {"status": "pass" if stable_bridge_path.is_file() and command and str(stable_bridge_path) in command else "drift", "bridgePath": str(stable_bridge_path), "configuredCommand": command}


def install_bridge(settings_path: Path, source_bridge_path: Path, stable_bridge_path: Path) -> dict[str, Any]:
    settings = _read_settings(settings_path)
    original_status_line = settings.get("statusLine")
    previous = original_status_line.get("command") if isinstance(original_status_line, dict) else None
    stable_bridge_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(stable_bridge_path)
    # A second install must retain the first pre-bridge command, not wrap itself.
    if stable_bridge_path.is_file() and previous and str(stable_bridge_path) in previous and backup_path.exists():
        saved = _read_settings(backup_path).get("statusLine")
        previous = saved.get("command") if isinstance(saved, dict) else None
    else:
        _write_atomic(backup_path, {"statusLine": original_status_line})
    shutil.copy2(source_bridge_path, stable_bridge_path)
    status_line = dict(original_status_line) if isinstance(original_status_line, dict) else {}
    status_line["command"] = f'python "{stable_bridge_path}"' + (f' --delegate-command {json.dumps(previous)}' if previous else "")
    settings["statusLine"] = status_line
    _write_atomic(settings_path, settings)
    return {"status": "pass", "previousCommand": previous, "bridgePath": str(stable_bridge_path)}


def uninstall_bridge(settings_path: Path, stable_bridge_path: Path) -> dict[str, Any]:
    settings = _read_settings(settings_path)
    command = settings.get("statusLine", {}).get("command") if isinstance(settings.get("statusLine"), dict) else ""
    backup = _backup_path(stable_bridge_path)
    if str(stable_bridge_path) in str(command) and backup.exists():
        previous = _read_settings(backup).get("statusLine")
        if previous is None: settings.pop("statusLine", None)
        else: settings["statusLine"] = previous
    _write_atomic(settings_path, settings)
    if stable_bridge_path.exists(): stable_bridge_path.unlink()
    if backup.exists(): backup.unlink()
    return {"status": "pass", "bridgePath": str(stable_bridge_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Claude status-line attestation setup outside review execution.")
    parser.add_argument("mode", choices=("check", "install", "uninstall")); parser.add_argument("--settings", type=Path, required=True); parser.add_argument("--bridge", type=Path, required=True); parser.add_argument("--source", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "check": result = check_installation(args.settings, args.bridge)
    elif args.mode == "install":
        if not args.source: parser.error("--source is required for install")
        result = install_bridge(args.settings, args.source, args.bridge)
    else: result = uninstall_bridge(args.settings, args.bridge)
    print(json.dumps(result, sort_keys=True)); return 0 if result["status"] == "pass" else 2


if __name__ == "__main__": raise SystemExit(main())
