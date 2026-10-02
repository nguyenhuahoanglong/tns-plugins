#!/usr/bin/env python3
"""Persist non-secret PCF preferences and scoped first-run prerequisite receipts.

No installation, authentication, browser launch, Git commit or deployment occurs.
Status is cheap: it reads preferences/receipts and checks cached executable paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

BEGIN = "<!-- yana-pcf-config:start -->"
END = "<!-- yana-pcf-config:end -->"
FIELDS = {
    "personal_variant", "deploy_environment_url", "default_control",
    "browser_profile", "overrides_directory", "release_sources",
}
DEFAULT_ENV = "https://yanaintegrationdevqa.crm5.dynamics.com"
SCHEMA = 1
RUNTIMES = {
    "deploy": {"python", "git", "node", "npm", "dotnet", "pac", "az", "powershell"},
    "override": {"python", "git", "node", "npm"},
}
SCOPE_FIELDS = {
    "deploy": {"personal_variant", "deploy_environment_url", "release_sources", "default_control"},
    "override": {"browser_profile", "overrides_directory", "default_control"},
}


class SetupError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def repo_root(repo: Path | str) -> Path:
    root = Path(repo).resolve()
    result = git(root, "rev-parse", "--show-toplevel")
    if result.returncode or Path(result.stdout.strip()).resolve() != root:
        raise SetupError("Use the checkout root, not a workspace subdirectory.")
    return root


def validate(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) - FIELDS:
        raise SetupError("PCF config contains unsupported fields; store no secrets here.")
    for key, value in config.items():
        if key == "release_sources":
            if not isinstance(value, dict) or any(
                not isinstance(k, str) or not k or not isinstance(v, str)
                or not re.fullmatch(r"(?:origin/)?\d+\.\d+\.\d+", v)
                for k, v in value.items()
            ):
                raise SetupError("release_sources must map work branches to confirmed X.Y.Z release branches.")
            continue
        if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
            raise SetupError(f"Invalid PCF config field: {key}")
        if key == "personal_variant" and (
            not re.fullmatch(r"[A-Za-z0-9]+", value)
            or value.casefold() in {"base", "prod", "production", "preview", "rc", "hotfix"}
        ):
            raise SetupError("Personal variant must be alphanumeric and not a reserved shared identity.")
        if key == "default_control" and value not in {"YanaGrid", "YanaQuickView"}:
            raise SetupError("default_control must be YanaGrid or YanaQuickView.")
        if key == "deploy_environment_url":
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in {"", "/"} or parsed.port not in {None, 443}):
                raise SetupError("Deploy environment must be an HTTPS org origin without credentials or query.")
        if key in {"browser_profile", "overrides_directory"} and not Path(value).is_absolute():
            raise SetupError(f"{key} must be an absolute path.")
    return dict(config)


def load_config(repo: Path | str) -> dict:
    """Read only the managed block; legacy prose remains for the agent to interpret."""
    path = Path(repo) / "AGENTS.local.md"
    if not path.exists():
        return {}
    if path.is_symlink():
        raise SetupError("AGENTS.local.md must not be a symlink.")
    content = path.read_text(encoding="utf-8-sig")
    if BEGIN not in content and END not in content:
        return {}
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise SetupError("PCF config markers are malformed or duplicated; preserve file and repair the block.")
    block = content.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    match = re.fullmatch(r"```(?:pcf-config|json)\s*\n(.*?)\n```", block, flags=re.S)
    if not match:
        raise SetupError("Expected one fenced pcf-config JSON object between PCF markers.")
    try:
        return validate(json.loads(match.group(1)))
    except (ValueError, TypeError) as exc:
        raise SetupError("PCF configuration JSON is invalid.") from exc


def atomic_write(path: Path, data: bytes, previous: bytes | None) -> None:
    if path.is_symlink():
        raise SetupError("Refusing to replace a symlink.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".pcf-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        current = path.read_bytes() if path.exists() else None
        if current != previous:
            raise SetupError("Configuration changed during update; reread before retrying.")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save_config(repo: Path | str, updates: dict, apply: bool = False) -> dict:
    root = repo_root(repo)
    current = load_config(root)
    merged = validate({**current, **updates})
    path = root / "AGENTS.local.md"
    if git(root, "ls-files", "--error-unmatch", "--", "AGENTS.local.md").returncode == 0:
        raise SetupError("AGENTS.local.md is tracked; do not store personal preferences there.")
    if git(root, "check-ignore", "-q", "--", "AGENTS.local.md").returncode != 0:
        raise SetupError("AGENTS.local.md must already be ignored (use checkout-local Git exclude if needed).")
    if not apply:
        return merged
    old = path.read_bytes() if path.exists() else None
    content = old.decode("utf-8-sig") if old else ""
    newline = "\r\n" if "\r\n" in content else "\n"
    block = BEGIN + "\n```pcf-config\n" + json.dumps(merged, indent=2, ensure_ascii=False) + "\n```\n" + END
    block = block.replace("\n", newline)
    if BEGIN in content:
        start, stop = content.index(BEGIN), content.index(END) + len(END)
        content = content[:start] + block + content[stop:]
    else:
        content += (newline if not content or content.endswith(newline) else newline * 2) + block + newline
    payload = content.encode("utf-8")
    if old and old.startswith(b"\xef\xbb\xbf"):
        payload = b"\xef\xbb\xbf" + payload
    atomic_write(path, payload, old)
    return merged


def state_path(repo: Path, state_root: Path | None = None) -> Path:
    if state_root is None:
        appdata = os.environ.get("LOCALAPPDATA")
        if not appdata:
            raise SetupError("LOCALAPPDATA is unavailable; supply --state-root explicitly.")
        state_root = Path(appdata) / "YanaPcfDebug" / "setup"
    key = hashlib.sha256(os.path.normcase(str(repo.resolve())).encode()).hexdigest()[:20]
    return state_root / key / "setup.json"


def config_fingerprint(config: dict, scope: str) -> str:
    keys = ("deploy_environment_url",) if scope == "deploy" else ("browser_profile", "overrides_directory")
    return hashlib.sha256(json.dumps({k: config.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": SCHEMA, "scopes": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema_version") != SCHEMA or not isinstance(state.get("scopes"), dict):
            raise ValueError()
        for scope, receipt in state["scopes"].items():
            if (scope not in {"deploy", "override"} or not isinstance(receipt, dict)
                    or not isinstance(receipt.get("config_fingerprint"), str)
                    or not isinstance(receipt.get("runtimes"), dict)
                    or not all(isinstance(k, str) and isinstance(v, str) and v
                               for k, v in receipt["runtimes"].items())):
                raise ValueError()
        return state
    except (ValueError, TypeError, AttributeError) as exc:
        raise SetupError("Setup receipt is invalid; repair that receipt without clearing browser state.") from exc


def status(repo: Path, scope: str, state_root: Path | None = None) -> dict:
    config = load_config(repo)
    required = ("deploy_environment_url",) if scope == "deploy" else ("browser_profile", "overrides_directory")
    missing = [field for field in required if not config.get(field)]
    receipt = read_state(state_path(repo, state_root))["scopes"].get(scope, {})
    stale = receipt.get("config_fingerprint") != config_fingerprint(config, scope)
    runtimes = receipt.get("runtimes", {})
    valid = RUNTIMES[scope].issubset(runtimes) and all(Path(p).is_absolute() and Path(p).is_file() for p in runtimes.values())
    result = {
        "status": "CONFIGURED" if not missing and not stale and valid else "NEEDS_SETUP",
        "scope": scope, "missing_config": missing,
        "legacy_preferences_present": (repo / "AGENTS.local.md").exists() and not config,
        "config": config, "runtimes": runtimes,
        "limit": "CONFIGURED records setup only; verify live org or loaded browser assets per operation.",
    }
    if scope == "deploy":
        result["personal_variant_missing"] = not bool(config.get("personal_variant"))
    return result


def probe_runtimes(scope: str) -> dict:
    if "windowsapps" in str(Path(sys.executable)).casefold() or sys.version_info < (3, 10):
        raise SetupError("Use native Python 3.10+, not Microsoft Store Python.")
    names = ["git", "node", "npm"] + (["dotnet", "pac", "az", "powershell"] if scope == "deploy" else [])
    paths = {"python": sys.executable}
    missing = []
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            paths[name] = resolved
        else:
            missing.append(name)
    if missing:
        raise SetupError("Missing prerequisites: " + ", ".join(missing) + ". Guide installation; do not install silently.")
    result = subprocess.run([paths["node"], "--version"], capture_output=True, text=True)
    match = re.match(r"v?(\d+)\.", result.stdout.strip())
    if result.returncode or not match or int(match.group(1)) < (22 if scope == "override" else 18):
        raise SetupError("Node version does not meet this workflow (override collector requires Node 22+).")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "init"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--scope", choices=("deploy", "override"), required=True)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--apply", action="store_true", help="Persist supplied preferences and successful prerequisite receipt.")
    parser.add_argument("--recheck-tools", action="store_true", help="Probe versions again after a runtime failure or requirement change.")
    for name in sorted(FIELDS - {"release_sources"}):
        parser.add_argument("--" + name.replace("_", "-"))
    parser.add_argument("--release-source", nargs=2, metavar=("WORK_BRANCH", "RELEASE_BRANCH"))
    args = parser.parse_args(argv)
    try:
        root = repo_root(args.repo)
        if args.mode == "status":
            result = status(root, args.scope, args.state_root)
        else:
            updates = {k: getattr(args, k) for k in FIELDS - {"release_sources"} if getattr(args, k)}
            if args.release_source:
                updates["release_sources"] = {**load_config(root).get("release_sources", {}), args.release_source[0]: args.release_source[1]}
            if set(updates) - SCOPE_FIELDS[args.scope]:
                raise SetupError("Supplied preferences belong to another setup scope; use that scope explicitly.")
            existing = load_config(root)
            if not existing.get("default_control") and "default_control" not in updates:
                updates["default_control"] = "YanaGrid"
            if args.scope == "deploy" and not existing.get("deploy_environment_url") and "deploy_environment_url" not in updates:
                updates["deploy_environment_url"] = DEFAULT_ENV
            preview = save_config(root, updates, apply=False)
            if not args.apply:
                result = {"status": "PREVIEW", "scope": args.scope, "config": preview}
            else:
                required = ("deploy_environment_url",) if args.scope == "deploy" else ("browser_profile", "overrides_directory")
                if any(not preview.get(k) for k in required):
                    raise SetupError("Supply missing scope preferences before completing init.")
                path = state_path(root, args.state_root)
                old = path.read_bytes() if path.exists() else None
                state = read_state(path)
                cached = state["scopes"].get(args.scope, {}).get("runtimes", {})
                if (RUNTIMES[args.scope].issubset(cached) and not args.recheck_tools
                        and all(Path(p).is_absolute() and Path(p).is_file() for p in cached.values())):
                    runtimes = cached
                else:
                    runtimes = probe_runtimes(args.scope)
                config = save_config(root, updates, apply=True)
                state["scopes"][args.scope] = {"config_fingerprint": config_fingerprint(config, args.scope), "runtimes": runtimes}
                atomic_write(path, json.dumps(state, indent=2).encode(), old)
                result = status(root, args.scope, args.state_root)
        print(json.dumps(result, indent=2))
        return 0
    except (SetupError, OSError, ValueError) as exc:
        print(json.dumps({"status": "NEEDS_SETUP", "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
