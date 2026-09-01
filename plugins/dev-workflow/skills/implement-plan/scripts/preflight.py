#!/usr/bin/env python3
"""Read-only autonomy preflight: probe a plan's prerequisites without user interaction.

Closed set of probe kinds with typed arguments and keyed auth commands, never free-form shell.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

READY, BLOCKED, UNVERIFIABLE = "ready", "blocked", "unverifiable"
KINDS = ("path", "command", "command-version", "auth", "env", "url", "node-deps", "dotnet-restore", "manual")
VERSION_ARGS = ("--version", "-v", "version")
AUTH_TIMEOUT, URL_TIMEOUT, DEFAULT_TIMEOUT = 45, 10, 20
OUTPUT_CAP = 300
AUTH_READY_CODES = (401, 403)

AUTH_COMMANDS: dict[str, list[str]] = {
    "az-account": ["az", "account", "show"],
    "pac-list": ["pac", "auth", "list"],
    "pac-org": ["pac", "org", "who"],
    "nuget-sources": ["dotnet", "nuget", "list", "source"],
    "git-remote": ["git", "ls-remote", "--heads", "{arg}"],
}
AUTH_ARG_RE = re.compile(r"^(?:https://|ssh://|git@)[\w.~:/?#@!$&()*+,;=%'-]+$")
SECRET_ENV_RE = re.compile(r"PAT|TOKEN|SECRET|KEY|PASSWORD", re.I)
BEARER_RE = re.compile(r"Bearer\s+\S+", re.I)
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-.]{20,}")
ACCESS_TOKEN_RE = re.compile(r"(\"access_?token\"\s*:\s*)\"[^\"]+\"")
TABLE_RE = re.compile(r"^\|(?P<cells>.+)\|\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^### (?P<name>Task \d+):.*?(?=^### |^## |\Z)", re.MULTILINE | re.DOTALL)
FILES_RE = re.compile(r"^-?\s*Files:\s*(?P<value>.+?)\s*$", re.MULTILINE)


class PlanError(Exception):
    """Raised when the plan's Preflight declaration cannot be parsed."""


@dataclass(frozen=True)
class Probe:
    pid: str
    kind: str
    target: str
    blocks: str
    derived: bool = False


@dataclass(frozen=True)
class ProbeResult:
    probe: Probe
    state: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.probe.pid, "kind": self.probe.kind, "target": self.probe.target,
                "blocks": self.probe.blocks, "derived": self.probe.derived,
                "state": self.state, "detail": self.detail}


def redact(text: str) -> str:
    text = BEARER_RE.sub("[redacted]", text)
    text = JWT_RE.sub("[redacted]", text)
    text = ACCESS_TOKEN_RE.sub(r'\1"[redacted]"', text)
    for name, value in os.environ.items():
        if value and len(value) > 3 and SECRET_ENV_RE.search(name):
            text = text.replace(value, "[redacted]")
    return text


def clip(text: Any) -> str:
    flat = redact(" ".join(str(text).split()))
    return flat if len(flat) <= OUTPUT_CAP else flat[:OUTPUT_CAP] + "..."


def resolve_argv(argv: Sequence[str]) -> list[str]:
    """Resolve the executable to an absolute path: Windows .CMD shims fail when invoked bare."""
    if not argv:
        return list(argv)
    resolved = shutil.which(argv[0])
    return [resolved, *argv[1:]] if resolved else list(argv)


def default_runner(argv: Sequence[str], timeout: int) -> dict[str, Any]:
    try:
        done = subprocess.run(resolve_argv(argv), check=False, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)
        return {"returncode": done.returncode, "stdout": done.stdout or "", "stderr": done.stderr or ""}
    except subprocess.TimeoutExpired:
        return {"returncode": None, "stdout": "", "stderr": "timed out", "timeout": True}
    except OSError as error:
        return {"returncode": 127, "stdout": "", "stderr": str(error)}


def default_url_probe(url: str, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as response:
            return {"status": response.status}
    except urllib.error.HTTPError as error:
        return {"status": error.code}
    except Exception as error:  # noqa: BLE001 - any transport failure is a block
        return {"status": None, "error": str(error)}


def ado_cli_argv() -> list[str]:
    candidate = Path(__file__).resolve().parents[2] / "ado-operations" / "scripts" / "ado.py"
    return [sys.executable, str(candidate), "auth", "status"] if candidate.is_file() else ["ado", "auth", "status"]


def auth_argv(target: str) -> list[str]:
    key, _, argument = target.strip().partition(" ")
    argument = argument.strip()
    if key == "ado-pat":
        if argument:
            raise PlanError("auth ado-pat takes no argument")
        return ado_cli_argv()
    template = AUTH_COMMANDS.get(key)
    if template is None:
        raise PlanError("unknown auth key: " + (key or target))
    if "{arg}" in template:
        if not AUTH_ARG_RE.match(argument):
            raise PlanError(f"auth {key} requires a git URL argument")
        return [part.replace("{arg}", argument) for part in template]
    if argument:
        raise PlanError(f"auth {key} takes no argument")
    return list(template)


def parse_rows(text: str, heading: str) -> list[list[str]]:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^##\s|\Z)", text, re.MULTILINE)
    if not match:
        return []
    rows = []
    for row in TABLE_RE.finditer(match.group(1)):
        cells = [cell.strip() for cell in row.group("cells").split("|")]
        if cells and cells[0].lower() == "id":
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue
        rows.append(cells)
    return rows


def declared_probes(text: str) -> list[Probe]:
    probes = []
    for cells in parse_rows(text, "Preflight"):
        if len(cells) != 5:
            raise PlanError(f"Preflight row needs 5 columns, got {len(cells)}: " + " | ".join(cells))
        pid, kind, target, _expect, blocks = cells
        if kind not in KINDS:
            raise PlanError(f"{pid}: unknown probe kind: {kind}")
        probes.append(Probe(pid, kind, target.strip("`"), blocks))
    return probes


def derived_probes(text: str) -> list[Probe]:
    probes = []
    for task in TASK_RE.finditer(text):
        name = task.group("name")
        files = FILES_RE.search(task.group(0))
        if not files:
            continue
        for raw in files.group("value").split(","):
            candidate = raw.strip().strip("`").strip()
            if candidate and candidate.lower() not in {"none", "not applicable"}:
                probes.append(Probe(f"derived path {name} `{candidate}`", "path", candidate, name, derived=True))
    return probes


def probe_path(target: str, root: Path) -> tuple[str, str]:
    path = Path(target) if Path(target).is_absolute() else root / target
    if path.is_file():
        return READY, "file exists"
    if path.is_dir():
        return READY, "directory exists"
    if path.parent.is_dir():
        return READY, f"new file, parent folder exists: {path.parent}"
    return BLOCKED, f"neither the path nor its parent folder exists: {path}"


def probe_node_deps(target: str, root: Path) -> tuple[str, str]:
    manifest = Path(target) if Path(target).is_absolute() else root / target
    if not manifest.is_file():
        return BLOCKED, f"package.json not found: {manifest}"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return BLOCKED, "package.json unreadable: " + clip(error)
    modules = manifest.parent / "node_modules"
    if not modules.is_dir():
        return BLOCKED, f"node_modules missing entirely: run npm ci in {manifest.parent}"
    names = [*payload.get("dependencies", {}), *payload.get("devDependencies", {})]
    missing = [name for name in names if not (modules / name).exists()]
    if missing:
        return BLOCKED, (f"node_modules missing {len(missing)} declared package(s) "
                         f"({', '.join(missing[:3])}): run npm ci")
    return READY, f"all {len(names)} declared package(s) present"


def probe_dotnet_restore(target: str, root: Path) -> tuple[str, str]:
    project = Path(target) if Path(target).is_absolute() else root / target
    if not project.is_file():
        return BLOCKED, f"project file not found: {project}"
    assets = project.parent / "obj" / "project.assets.json"
    if not assets.is_file():
        return BLOCKED, f"no restore output: {assets} is missing"
    if assets.stat().st_mtime < project.stat().st_mtime:
        return BLOCKED, "restore output is older than the project file"
    return READY, "restore output is present and current"


def probe_command(target: str) -> tuple[str, str]:
    resolved = shutil.which(target)
    return (READY, resolved) if resolved else (BLOCKED, f"{target} does not resolve on PATH")


def probe_command_version(probe: Probe, runner: Callable[..., dict[str, Any]]) -> tuple[str, str]:
    name, _, argument = probe.target.partition(" ")
    argument = argument.strip() or "--version"
    if argument not in VERSION_ARGS:
        return BLOCKED, f"{argument} is not an allowlisted version argument"
    if not shutil.which(name):
        return BLOCKED, f"{name} does not resolve on PATH"
    outcome = runner([name, argument], DEFAULT_TIMEOUT)
    if outcome.get("timeout"):
        return BLOCKED, f"{name} {argument} timed out"
    if outcome.get("returncode") == 0:
        return READY, clip(outcome.get("stdout") or outcome.get("stderr") or "reported a version")
    return BLOCKED, clip(outcome.get("stderr") or outcome.get("stdout") or f"{name} {argument} failed")


def probe_auth(probe: Probe, runner: Callable[..., dict[str, Any]]) -> tuple[str, str]:
    outcome = runner(auth_argv(probe.target), AUTH_TIMEOUT)
    if outcome.get("timeout"):
        return BLOCKED, "check timed out, which is the interactive-prompt signature; sign in and re-run"
    if outcome.get("returncode") == 0:
        return READY, "non-interactive check succeeded"
    return BLOCKED, clip(outcome.get("stderr") or outcome.get("stdout") or "non-interactive check failed")


def probe_env(target: str) -> tuple[str, str]:
    return (READY, f"{target} is set") if os.environ.get(target) else (BLOCKED, f"{target} is not set")


def probe_url(target: str, url_probe: Callable[..., dict[str, Any]]) -> tuple[str, str]:
    if not target.startswith(("http://", "https://")):
        return BLOCKED, "target is not an http or https URL"
    outcome = url_probe(target, URL_TIMEOUT)
    status = outcome.get("status")
    if status is None:
        return BLOCKED, "unreachable: " + clip(outcome.get("error", "no response"))
    if 200 <= status < 400 or status in AUTH_READY_CODES:
        return READY, f"reachable ({status})"
    return BLOCKED, f"reachable but returned {status}"


def run_probe(probe: Probe, root: Path, runner, url_probe) -> ProbeResult:
    try:
        if probe.kind == "path":
            state, detail = probe_path(probe.target, root)
        elif probe.kind == "command":
            state, detail = probe_command(probe.target)
        elif probe.kind == "command-version":
            state, detail = probe_command_version(probe, runner)
        elif probe.kind == "auth":
            state, detail = probe_auth(probe, runner)
        elif probe.kind == "env":
            state, detail = probe_env(probe.target)
        elif probe.kind == "url":
            state, detail = probe_url(probe.target, url_probe)
        elif probe.kind == "node-deps":
            state, detail = probe_node_deps(probe.target, root)
        elif probe.kind == "dotnet-restore":
            state, detail = probe_dotnet_restore(probe.target, root)
        else:
            state, detail = UNVERIFIABLE, "manual probe, main agent must attest"
    except PlanError as error:
        state, detail = BLOCKED, str(error)
    return ProbeResult(probe, state, detail)


def autonomy(results: Iterable[ProbeResult]) -> str:
    states = {result.state for result in results}
    if BLOCKED in states:
        return "verified-blocked"
    return "unverifiable-with-fallback" if UNVERIFIABLE in states else "verified-ready"


def run(text: str, root: Path, runner=default_runner, url_probe=default_url_probe) -> list[ProbeResult]:
    probes = [*declared_probes(text), *derived_probes(text)]
    return [run_probe(probe, root, runner, url_probe) for probe in probes]


def render_markdown(results: Sequence[ProbeResult], stamp: str) -> str:
    lines = ["### Preflight results", f"Run: {stamp} scripts/preflight.py"]
    lines += [f"- {result.probe.pid} {result.state}: {result.detail}" for result in results]
    lines.append(f"Autonomy: {autonomy(results)}")
    return "\n".join(lines)


def render_text(results: Sequence[ProbeResult], plan_path: Path) -> str:
    blocked = sum(result.state == BLOCKED for result in results)
    unverifiable = sum(result.state == UNVERIFIABLE for result in results)
    lines = [f"=== PREFLIGHT: implement-plan ({plan_path}) ==="]
    lines += [f"{result.state.upper():<12}  {result.probe.pid}: {result.detail}" for result in results]
    lines.append(f"\nAutonomy: {autonomy(results)} "
                 f"({len(results)} probes, {blocked} blocked, {unverifiable} unverifiable)")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe an implement-plan plan's prerequisites, read-only.")
    parser.add_argument("plan_path")
    parser.add_argument("--repo-root", default=None, help="root for relative paths (default: current directory)")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    parser.add_argument("--stamp", default="", help="timestamp recorded in the markdown results block")
    args = parser.parse_args(argv)

    path = Path(args.plan_path)
    if not path.is_file():
        print(f"ERROR  plan file not found: {path}")
        return 2
    root = Path(args.repo_root) if args.repo_root else Path.cwd()
    try:
        results = run(path.read_text(encoding="utf-8", errors="replace"), root)
    except PlanError as error:
        print(f"ERROR  {error}")
        return 2

    if args.format == "json":
        print(json.dumps({"autonomy": autonomy(results), "probes": [r.to_dict() for r in results]}, indent=2))
    elif args.format == "markdown":
        print(render_markdown(results, args.stamp or "<timestamp>"))
    else:
        print(render_text(results, path))
    return 1 if any(result.state == BLOCKED for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
