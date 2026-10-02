#!/usr/bin/env python3
r"""Build, plan, apply and verify a complete YanaGrid client resource override.

No Dataverse import. No server web-resource mutation. Local state stays under
%LOCALAPPDATA%\YanaPcfDebug\YanaGrid.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from resource_set import (
    ResourceSetError, apply_plan, ensure_native_filesystem_runtime, inspect_build, make_plan,
    control_identity, resolve_deployed_identity, validate_mapping_destinations, verify_runtime,
)


SKILL_NAME = "yana-pcf-debug-override"
GRID_WORKSPACE = "Technosoft.DMS.XRM.CustomControl.Grid"
QUICKVIEW_WORKSPACE = "Technosoft.DMS.XRM.CustomControl.QuickView"
CONTROL_SPECS = {
    "YanaGrid": {
        "workspace": Path(GRID_WORKSPACE),
        "constructor": "YanaGrid",
        "manifest": Path("YanaGrid") / "ControlManifest.Input.xml",
        "resx": Path("YanaGrid") / "localized" / "YanaGrid.1033.resx",
        "optional": (Path("YanaGrid") / "sdk" / "sdkVersion.ts",),
    },
    "YanaQuickView": {
        "workspace": Path(QUICKVIEW_WORKSPACE),
        "constructor": "YanaQuickView",
        "manifest": Path("YanaQuickView") / "ControlManifest.Input.xml",
        "resx": Path("YanaQuickView") / "localized" / "YanaQuickView.1033.resx",
        "optional": (),
    },
}
DEFAULT_CONTROL = "YanaGrid"
GRID_SPEC = CONTROL_SPECS[DEFAULT_CONTROL]
BUNDLE_RELATIVE = GRID_SPEC["workspace"] / "out" / "controls" / DEFAULT_CONTROL / "bundle.js"
PCF_NODE_RELATIVE = Path("node_modules") / "pcf-scripts" / "bin" / "pcf-scripts.js"
STAMP_TARGETS = (
    Path(GRID_WORKSPACE) / "YanaGrid" / "ControlManifest.Input.xml",
    Path(GRID_WORKSPACE) / "package.json",
    Path(GRID_WORKSPACE) / "YanaGrid" / "localized" / "YanaGrid.1033.resx",
    Path(GRID_WORKSPACE) / "version.json",
    Path("Solution") / "src" / "Other" / "Solution.xml",
)
OPTIONAL_STAMP_TARGETS = (
    Path(GRID_WORKSPACE) / "YanaGrid" / "sdk" / "sdkVersion.ts",
    Path(GRID_WORKSPACE) / "Solution" / "src" / "Other" / "Solution.xml",
)


class SkillError(RuntimeError):
    """Expected user-facing workflow failure."""


def section(name: str) -> None:
    print(f"=== {name} ===")


def state_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "YanaPcfDebug" / "YanaGrid"


def setup_helper_path() -> Path:
    """Resolve shared setup from this provider; never guess a machine plugin cache."""
    skills_root = Path(__file__).resolve().parents[2]
    return skills_root / "yana-pcf-deploy" / "scripts" / "pcf_setup.py"


def load_setup_config(repo_root: Path) -> dict[str, Any]:
    helper = setup_helper_path()
    if not helper.is_file():
        raise SkillError(
            "SETUP_DEPENDENCY_MISSING: yana-pcf-deploy/scripts/pcf_setup.py is missing from the active dev-workflow provider. "
            "Restore/update the complete plugin bundle before using override."
        )
    spec = importlib.util.spec_from_file_location("yana_pcf_shared_setup", helper)
    if spec is None or spec.loader is None:
        raise SkillError(f"Cannot load shared PCF setup helper: {helper}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        config = module.load_config(repo_root)
    except Exception as exc:
        raise SkillError(f"Shared PCF setup config is invalid: {exc}") from exc
    if not isinstance(config, dict):
        raise SkillError("Shared PCF setup helper returned invalid configuration.")
    return config


def state_paths(setup_config: dict[str, Any] | None = None) -> dict[str, Path | None]:
    root = state_root()
    setup_config = setup_config or {}
    profile = setup_config.get("browser_profile")
    overrides = setup_config.get("overrides_directory")
    return {
        "root": root,
        "config": root / "config.json",
        "profile": Path(profile).expanduser() if isinstance(profile, str) and profile else None,
        "overrides": Path(overrides).expanduser() if isinstance(overrides, str) and overrides else None,
    }


def control_spec(control: str) -> dict[str, Any]:
    try:
        return CONTROL_SPECS[control]
    except KeyError as exc:
        raise SkillError(f"Unsupported control: {control}. Choose YanaGrid or YanaQuickView.") from exc


def stamp_targets(control: str) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    spec = control_spec(control)
    workspace = spec["workspace"]
    required = (
        workspace / spec["manifest"],
        workspace / "package.json",
        workspace / spec["resx"],
        workspace / "version.json",
        Path("Solution") / "src" / "Other" / "Solution.xml",
    )
    optional = tuple(workspace / path for path in spec["optional"]) + (
        workspace / "Solution" / "src" / "Other" / "Solution.xml",
    )
    return required, optional


def parse_page_url(value: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise SkillError("PageUrl must be an absolute HTTPS URL.")
    return value, f"https://{parsed.netloc.lower()}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_source(repo_root: Path, control: str = DEFAULT_CONTROL) -> dict[Path, str]:
    required, optional = stamp_targets(control)
    missing = [path for path in required if not (repo_root / path).is_file()]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise SkillError(f"{control} source layout missing: {paths}")
    targets = (*required, *(path for path in optional if (repo_root / path).is_file()))
    return {path: sha256(repo_root / path) for path in targets}


def assert_source_unchanged(repo_root: Path, before: dict[Path, str]) -> None:
    changed = [str(path) for path, digest in before.items() if sha256(repo_root / path) != digest]
    if changed:
        joined = ", ".join(changed)
        raise SkillError(
            "Direct PCF build changed tracked source files; override copy skipped. "
            f"Inspect: {joined}"
        )


def load_config(paths: dict[str, Path]) -> dict[str, Any]:
    config_path = paths["config"]
    if not config_path.is_file():
        return {"version": 1, "mappings": {}}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid local config: {config_path}") from exc
    if not isinstance(config, dict) or not isinstance(config.get("mappings", {}), dict):
        raise SkillError(f"Invalid local config shape: {config_path}")
    config.setdefault("version", 1)
    config.setdefault("mappings", {})
    return config


def save_config(paths: dict[str, Path], config: dict[str, Any]) -> None:
    paths["root"].mkdir(parents=True, exist_ok=True)
    temp_path = paths["config"].with_suffix(".tmp")
    temp_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, paths["config"])


def build_bundle(
    repo_root: Path,
    dry_run: bool,
    build_mode: str = "production",
    control: str = DEFAULT_CONTROL,
) -> Path:
    spec = control_spec(control)
    pcf_bin = repo_root / PCF_NODE_RELATIVE
    workspace_root = repo_root / spec["workspace"]
    if not pcf_bin.is_file():
        raise SkillError(
            f"PCF build tool missing: {pcf_bin}. Restore dependencies from the repo lockfile first "
            "(run npm ci from the root when package-lock.json is present)."
        )
    if not (workspace_root / spec["manifest"]).is_file():
        raise SkillError(f"Not Core.Component.PCF repo root: {repo_root}")

    before = snapshot_source(repo_root, control)
    config_file = workspace_root / "pcfconfig.json"
    config = read_json(config_file) if config_file.is_file() else {}
    output_root = (workspace_root / config.get("outDir", "out/controls")).resolve()
    # The clean task recursively removes its configured output. Never pass it an unchecked path.
    if not output_root.is_relative_to(workspace_root.resolve() / "out"):
        raise SkillError(f"PCF clean output must remain inside the {control} workspace's out directory.")
    bundle = output_root / spec["constructor"] / "bundle.js"
    if dry_run:
        print(f"Would clean checked build output: {output_root}")
        print(f"Would run direct pcf-scripts build --buildMode {build_mode}: {pcf_bin}")
        print(f"Would verify source hashes: {len(before)} files")
        return bundle

    try:
        for arguments in (["clean"], ["build", "--buildMode", build_mode]):
            completed = subprocess.run(["node", str(pcf_bin), *arguments], cwd=workspace_root, check=False)
            if completed.returncode != 0:
                raise SkillError(f"PCF {arguments[0]} failed with exit code {completed.returncode}.")
    finally:
        assert_source_unchanged(repo_root, before)
    if not bundle.is_file() or bundle.stat().st_size == 0:
        raise SkillError(f"Build did not produce {control} bundle: {bundle}")
    return bundle


def run_git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def worktree_fingerprint(repo_root: Path) -> str:
    """Hash tracked diff and non-ignored untracked files without exposing their contents."""
    root = repo_root.resolve()
    digest = hashlib.sha256()
    patch = git_text(root, "diff", "--binary", "HEAD")
    digest.update(patch.encode("utf-8", errors="surrogatepass"))
    untracked = git_text(root, "ls-files", "--others", "--exclude-standard", "-z", allow_failure=True)
    for name in sorted(item for item in untracked.split("\x00") if item):
        candidate = root / name
        if candidate.is_symlink():
            raise SkillError(f"Untracked symlink prevents a safe build-source fingerprint: {name}")
        path = candidate.resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SkillError(f"Untracked source escapes the checkout: {name}") from exc
        if not path.is_file():
            continue
        digest.update(name.replace("\\", "/").encode("utf-8", errors="surrogatepass"))
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def git_text(repo_root: Path, *arguments: str, allow_failure: bool = False) -> str:
    result = run_git(repo_root, *arguments)
    if result.returncode and not allow_failure:
        raise SkillError("Git source check failed; no build or override was applied.")
    return result.stdout.strip()


def _revision_counts(repo_root: Path, head: str, upstream: str) -> tuple[int, int]:
    raw = git_text(repo_root, "rev-list", "--left-right", "--count", f"{head}...{upstream}")
    try:
        ahead, behind = (int(part) for part in raw.split())
    except (ValueError, TypeError) as exc:
        raise SkillError("Git returned an invalid ahead/behind count; source was not changed.") from exc
    return ahead, behind


def prepare_override_source(repo_root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Use local work as-is, or fetch and fast-forward a clean branch with no local commits."""
    repo_root = repo_root.resolve()
    top = git_text(repo_root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != repo_root:
        raise SkillError("Use the Core.Component.PCF checkout root for an override build.")
    status = git_text(repo_root, "status", "--porcelain", "--untracked-files=all")
    head = git_text(repo_root, "rev-parse", "--verify", "HEAD^{commit}")
    branch_result = run_git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    if status:
        return {
            "mode": "LOCAL_WORKTREE",
            "branch": branch,
            "head_sha": head,
            "latest_confirmed": False,
            "working_tree": "dirty",
            "local_changes_included": True,
            "git_mutation": "none",
        }
    if not branch:
        raise SkillError("Detached clean checkout has no branch source; select a branch before override.")

    upstream_result = run_git(repo_root, "rev-parse", "--symbolic-full-name", "@{u}")
    if upstream_result.returncode:
        raise SkillError("Clean branch has no upstream; specify or configure its source before override.")
    upstream_ref = upstream_result.stdout.strip()
    remote = git_text(repo_root, "config", "--get", f"branch.{branch}.remote", allow_failure=True)
    merge_ref = git_text(repo_root, "config", "--get", f"branch.{branch}.merge", allow_failure=True)
    if (
        remote in {"", "."}
        or not merge_ref.startswith("refs/heads/")
        or not upstream_ref.startswith(f"refs/remotes/{remote}/")
    ):
        raise SkillError("Upstream is not a configured remote branch; latest remote source cannot be confirmed.")
    before_ahead, _ = _revision_counts(repo_root, head, upstream_ref)
    if before_ahead:
        return {
            "mode": "LOCAL_COMMITS",
            "branch": branch,
            "head_sha": head,
            "upstream": upstream_ref,
            "latest_confirmed": False,
            "working_tree": "clean",
            "local_commits_ahead": before_ahead,
            "local_changes_included": True,
            "git_mutation": "none",
        }
    if dry_run:
        return {
            "mode": "WOULD_FETCH_AND_FAST_FORWARD",
            "branch": branch,
            "head_sha": head,
            "upstream": upstream_ref,
            "latest_confirmed": False,
            "working_tree": "clean",
            "local_changes_included": False,
            "git_mutation": "none",
        }

    if not re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]+", merge_ref) or ".." in merge_ref:
        raise SkillError("Configured upstream branch ref is invalid; source was not changed.")
    fetch_refspec = f"+{merge_ref}:{upstream_ref}"
    fetched = run_git(repo_root, "fetch", "--no-tags", remote, fetch_refspec)
    if fetched.returncode:
        raise SkillError("Fetching the configured upstream failed; current branch was not advanced.")
    status_after_fetch = git_text(repo_root, "status", "--porcelain", "--untracked-files=all")
    head_after_fetch = git_text(repo_root, "rev-parse", "--verify", "HEAD^{commit}")
    if status_after_fetch or head_after_fetch != head:
        raise SkillError("Checkout changed during fetch; review it before retrying override.")
    upstream_sha = git_text(repo_root, "rev-parse", "--verify", f"{upstream_ref}^{{commit}}")
    ancestor = run_git(repo_root, "merge-base", "--is-ancestor", head, upstream_ref)
    if ancestor.returncode != 0:
        raise SkillError("Remote upstream rewound or diverged; refusing reset, merge or build from stale source.")
    if upstream_sha != head:
        advanced = run_git(repo_root, "merge", "--ff-only", upstream_ref)
        if advanced.returncode:
            raise SkillError("Fast-forward failed; no merge commit was created and no override was applied.")
    final_head = git_text(repo_root, "rev-parse", "--verify", "HEAD^{commit}")
    final_status = git_text(repo_root, "status", "--porcelain", "--untracked-files=all")
    if final_head != upstream_sha or final_status:
        raise SkillError("Fast-forward result changed unexpectedly; inspect checkout before override.")
    return {
        "mode": "ALREADY_LATEST" if upstream_sha == head else "FAST_FORWARD",
        "branch": branch,
        "head_sha": final_head,
        "upstream": upstream_ref,
        "upstream_sha": upstream_sha,
        "latest_confirmed": True,
        "working_tree": "clean",
        "local_changes_included": False,
        "git_mutation": "fast-forward" if upstream_sha != head else "none",
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillError(f"Cannot read JSON input: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SkillError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def selected_control(args: argparse.Namespace, setup_config: dict[str, Any] | None = None) -> str:
    control = args.control or (setup_config or {}).get("default_control") or DEFAULT_CONTROL
    control_spec(control)
    return control


def prepare_output(args: argparse.Namespace, control: str) -> tuple[Path, dict[str, Any]]:
    if args.artifact_dir:
        return Path(args.artifact_dir).resolve(), {
            "mode": "EXISTING_ARTIFACT",
            "latest_confirmed": False,
            "freshness": "UNVERIFIED",
            "local_changes_included": None,
            "git_mutation": "none",
        }
    if args.dry_run:
        raise SkillError("DRY_RUN_REQUIRES_ARTIFACT_DIR: preview only an existing build; fetch and build are disabled.")
    repo_root = Path(args.repo_root).resolve()
    source = prepare_override_source(repo_root)
    before = worktree_fingerprint(repo_root)
    bundle = build_bundle(repo_root, False, args.build_mode, control)
    after = worktree_fingerprint(repo_root)
    if after != before:
        raise SkillError("Source tree changed during build; built output is not eligible for override.")
    source["worktree_fingerprint"] = after
    return bundle.parent, source


def source_identity(repo_root: Path, control: str) -> dict[str, str]:
    spec = control_spec(control)
    manifest = repo_root / spec["workspace"] / spec["manifest"]
    if not manifest.is_file():
        raise SkillError(f"Selected control manifest missing: {manifest}")
    identity = control_identity(manifest)
    if identity["constructor"] != spec["constructor"]:
        raise SkillError(f"Selected manifest constructor does not match {control}.")
    return identity


def canonical_path(value: Path) -> str:
    return os.path.normcase(str(value.expanduser().resolve(strict=False))).replace("\\", "/").casefold()


def mapping_scope(
    repo_root: Path,
    profile: Path,
    origin: str,
    control: str,
    deployed_identity: dict[str, str],
) -> dict[str, str]:
    return {
        "repo": canonical_path(repo_root),
        "profile": canonical_path(profile),
        "origin": origin,
        "control": control,
        "deployed_identity": deployed_identity["control_directory"],
    }


def mapping_key(scope: dict[str, str]) -> str:
    material = json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "v3:" + hashlib.sha256(material).hexdigest()


def normalize_mapping(
    mapping: dict[str, Any],
    origin: str,
    control: str,
    build_identity: dict[str, Any],
    requested_identity: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(mapping, dict) or mapping.get("schema_version") != 2:
        raise SkillError(
            "RESOURCE_MAP_REQUIRED: complete observed schema-2 resource mappings are required; "
            "bundle-only maps cannot prove loaded-asset parity."
        )
    mapped_origin = mapping.get("origin")
    if not isinstance(mapped_origin, str) or resource_origin(mapped_origin) != origin:
        raise SkillError("Resource map origin does not match the selected page URL.")
    saved_control = mapping.get("control")
    if saved_control is not None and saved_control != control:
        raise SkillError("Resource map belongs to a different control; select its control explicitly.")
    try:
        identity = resolve_deployed_identity(mapping, build_identity)
    except ResourceSetError as exc:
        raise SkillError(str(exc)) from exc
    if requested_identity and requested_identity != identity["control_directory"]:
        raise SkillError("Requested deployed identity does not match observed resource URLs.")
    mapping["origin"] = origin
    mapping["control"] = control
    mapping["deployed_identity"] = identity
    return mapping, identity


def resource_origin(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        ):
            return ""
        return parse_page_url(value)[1]
    except (ValueError, SkillError):
        return ""


def _new_mapping_candidates(
    mappings: dict[str, Any], base_scope: dict[str, str], requested_identity: str | None
) -> list[tuple[str, dict[str, Any]]]:
    candidates = []
    for key, value in mappings.items():
        if not isinstance(value, dict) or not isinstance(value.get("_scope"), dict):
            continue
        scope = value["_scope"]
        if all(scope.get(field) == base_scope[field] for field in ("repo", "profile", "origin", "control")):
            if requested_identity is None or scope.get("deployed_identity") == requested_identity:
                candidates.append((key, value))
    return candidates


def _legacy_mapping_for_scope(
    args: argparse.Namespace,
    config: dict[str, Any],
    origin: str,
    control: str,
    build_identity: dict[str, Any],
    paths: dict[str, Path],
    repo_root: Path,
    requested_identity: str | None,
) -> tuple[dict[str, Any], str, dict[str, str], bool, str | None]:
    mappings = config["mappings"]
    base_scope = {
        "repo": canonical_path(repo_root),
        "profile": canonical_path(paths["profile"]),
        "origin": origin,
        "control": control,
    }
    candidates = _new_mapping_candidates(mappings, base_scope, requested_identity)
    if len(candidates) > 1:
        raise SkillError("Multiple deployed identities match this repo/profile/origin; supply --deployed-identity from observed browser requests.")
    if candidates:
        key, candidate = candidates[0]
        mapping, identity = normalize_mapping(copy.deepcopy(candidate), origin, control, build_identity, requested_identity)
        expected_scope = mapping_scope(repo_root, paths["profile"], origin, control, identity)
        if candidate.get("_scope") != expected_scope or key != mapping_key(expected_scope):
            raise SkillError("Saved map scope does not match its key; refusing cross-profile reuse.")
        return mapping, key, expected_scope, False, None

    legacy = mappings.get(origin)
    if legacy is None:
        raise SkillError(
            "RESOURCE_MAP_REQUIRED: inspect exact requests for this repo/profile/origin/control and supply a complete resource map. "
            "A missing helper map does not prove Chrome lacks an existing folder grant."
        )
    claims = config.get("legacy_claims", {})
    claim = claims.get(origin) if isinstance(claims, dict) else None
    if claim:
        raise SkillError("LEGACY_MAP_ALREADY_BOUND: old Grid map is already bound to another repo/profile scope; create a new observed map.")
    if control != "YanaGrid":
        raise SkillError("LEGACY_GRID_MAP_ONLY: old origin-keyed mappings can never be reused for YanaQuickView.")
    if not args.migrate_legacy_grid_map:
        raise SkillError(
            "LEGACY_GRID_MAP_REBIND_REQUIRED: found an unscoped Grid map. Review its origin, identity and Overrides paths, "
            "then confirm one-time binding with --migrate-legacy-grid-map."
        )
    mapping, identity = normalize_mapping(copy.deepcopy(legacy), origin, control, build_identity, requested_identity)
    scope = mapping_scope(repo_root, paths["profile"], origin, control, identity)
    mapping["_scope"] = scope
    return mapping, mapping_key(scope), scope, True, origin


def _require_override_setup(repo_root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    setup_config = load_setup_config(repo_root)
    missing = [field for field in ("browser_profile", "overrides_directory") if not setup_config.get(field)]
    if missing:
        fields = ", ".join(missing)
        raise SkillError(
            f"OVERRIDE_SETUP_REQUIRED: missing {fields}. Run shared pcf_setup.py status/init --scope override; "
            "read ../yana-pcf-deploy/references/setup.md."
        )
    for field in ("browser_profile", "overrides_directory"):
        if not Path(setup_config[field]).is_absolute():
            raise SkillError(f"OVERRIDE_SETUP_REQUIRED: {field} must be an absolute path; repair shared setup.")
    paths = state_paths(setup_config)
    if paths["profile"] is None or not paths["profile"].is_dir():
        raise SkillError("OVERRIDE_SETUP_REQUIRED: configured browser profile directory is unavailable; do not create or switch profiles silently.")
    if paths["overrides"] is None or not paths["overrides"].is_dir():
        raise SkillError("OVERRIDE_SETUP_REQUIRED: configured Overrides folder is unavailable; preserve current browser state and repair setup.")
    return setup_config, paths


def inventory(args: argparse.Namespace) -> None:
    control = args.control or DEFAULT_CONTROL
    output, source = prepare_output(args, control)
    result = inspect_build(output)
    result["control"] = control
    result["source"] = source
    result["artifact_origin"] = "existing-output" if args.artifact_dir else "fresh-build"
    result["build_mode"] = None if args.artifact_dir else args.build_mode
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.report and not args.dry_run:
        write_json(Path(args.report), result)


def resource_workflow(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    _, origin = parse_page_url(args.page_url)
    setup_config, paths = _require_override_setup(repo_root)
    control = selected_control(args, setup_config)
    config = load_config(paths)
    manifest_identity = source_identity(repo_root, control)

    if args.resource_map:
        mapping = read_json(Path(args.resource_map))
        mapping, deployed_identity = normalize_mapping(
            mapping, origin, control, manifest_identity, args.deployed_identity,
        )
        scope = mapping_scope(repo_root, paths["profile"], origin, control, deployed_identity)
        key = mapping_key(scope)
        migrated = False
        legacy_origin = None
        mapping["_scope"] = scope
    else:
        mapping, key, scope, migrated, legacy_origin = _legacy_mapping_for_scope(
            args, config, origin, control, manifest_identity, paths, repo_root,
            args.deployed_identity,
        )
        deployed_identity = mapping["deployed_identity"]

    try:
        validate_mapping_destinations(mapping, paths["overrides"])
    except ResourceSetError as exc:
        raise SkillError(str(exc)) from exc

    output, source = prepare_output(args, control)
    inventory_data = inspect_build(output)
    try:
        built_deployed_identity = resolve_deployed_identity(mapping, inventory_data["identity"])
    except ResourceSetError as exc:
        raise SkillError(str(exc)) from exc
    if any(
        built_deployed_identity.get(field) != deployed_identity.get(field)
        for field in ("namespace", "constructor", "control_directory")
    ):
        raise SkillError("Selected build identity changed after source update; reobserve the deployed control before applying.")

    plan = make_plan(output, origin, paths["overrides"], mapping)
    plan["control"] = control
    plan["deployed_identity"] = deployed_identity
    plan["source"] = source
    plan["mapping_scope"] = scope
    plan["verification_scope"] = args.verification_scope
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.mode == "plan" or args.dry_run:
        if args.report and not args.dry_run:
            write_json(Path(args.report), plan)
        return
    receipt = apply_plan(plan, allow_host_unverified=args.allow_host_unverified,
                         verification_scope=args.verification_scope)
    if receipt.get("status") not in {"ASSETS_APPLIED", "ASSETS_APPLIED_NOT_DEPLOY_PARITY"}:
        raise SkillError("Resource apply was blocked; helper configuration was not changed.")
    receipt_path = Path(args.report) if args.report else paths["root"] / "last-apply.json"
    write_json(receipt_path, receipt)
    config["version"] = 3
    config["mappings"][key] = mapping
    if migrated and legacy_origin:
        config.setdefault("legacy_claims", {})[legacy_origin] = {
            "mapping_key": key,
            "scope": scope,
            "deployed_identity": deployed_identity,
        }
    save_config(paths, config)
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path),
                      "control": control, "deployed_identity": deployed_identity,
                      "source": source, "runtime_verification": "NOT_RUN",
                      "next": "Use active browser adapter, verify every loaded asset byte, then run verify."}, indent=2))


def verify(args: argparse.Namespace) -> None:
    receipt = read_json(Path(args.receipt))
    plan = dict(receipt["plan"])
    plan["applied_at"] = receipt["applied_at"]
    result = verify_runtime(plan, read_json(Path(args.runtime_evidence)))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.report and not args.dry_run:
        write_json(Path(args.report), result)
    accepted = result.get("status") == "CLIENT_RESOURCES_VERIFIED"
    if plan.get("verification_scope") == "client-assets":
        accepted = result.get("status") == "ASSETS_VERIFIED_NOT_DEPLOY_PARITY"
    if not accepted:
        raise SkillError("Runtime or host parity is incomplete. See verification report; do not claim deployed equivalence.")


def status(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    setup_config = load_setup_config(repo_root)
    paths = state_paths(setup_config)
    config = load_config(paths)
    section("STATUS")
    print(f"State root: {paths['root']}")
    print(f"Overrides folder: {paths['overrides'] or 'not configured'}")
    print(f"Configured browser profile: {paths['profile'] or 'not configured'}")
    print(f"CDP port: {config.get('debug_port', 'not started')}")
    mappings = config["mappings"]
    if not mappings:
        print("Helper mappings: none (Chrome folder grants and manually saved mappings are separate).")
        return
    print("Mappings:")
    for key, mapping in sorted(mappings.items()):
        scope = mapping.get("_scope", {}) if isinstance(mapping, dict) else {}
        origin = scope.get("origin", key if key.startswith("https://") else "unscoped")
        control = scope.get("control", "Grid (legacy)" if origin != "unscoped" else "unknown")
        identity = scope.get("deployed_identity", "unbound")
        print(f"  {origin} / {control} / {identity}: schema={mapping.get('schema_version', 'legacy-bundle-only')}, "
              f"resources={len(mapping.get('resources', []))}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan, apply and verify complete Yana PCF client resource overrides.")
    parser.add_argument("--mode", choices=("inventory", "plan", "setup", "run", "verify", "status"), default="run")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Core.Component.PCF repository root.")
    parser.add_argument("--control", choices=tuple(CONTROL_SPECS), help="Control to build; defaults to shared PCF config, then YanaGrid.")
    parser.add_argument("--page-url", help="Absolute HTTPS model-driven page URL containing the selected control.")
    parser.add_argument("--deployed-identity", help="Exact observed control directory, for example cc_<namespace>.YanaGrid.")
    parser.add_argument("--resource-map", help="Schema 2 map of observed URLs, override files, and host evidence.")
    parser.add_argument("--migrate-legacy-grid-map", action="store_true",
                        help="After user confirmation, copy one unscoped legacy Grid map into current repo/profile scope; never reuses it for QuickView.")
    parser.add_argument("--artifact-dir", help="Use an existing complete out/controls/<control> directory without rebuilding.")
    parser.add_argument("--build-mode", choices=("production", "development"), default="production")
    parser.add_argument("--verification-scope", choices=("client-assets", "client-parity"), default="client-assets",
                        help="Apply scope: client-assets tests logic/UI with host limits; client-parity also requires host parity. Verify uses the receipt's saved scope.")
    parser.add_argument("--allow-host-unverified", action="store_true", help="Explicit partial asset debugging only; never deployment parity.")
    parser.add_argument("--receipt", help="Saved apply receipt for runtime verification.")
    parser.add_argument("--runtime-evidence", help="Fresh captured runtime hashes and host evidence for verification.")
    parser.add_argument("--report", help="Write plan, apply receipt, inventory or verification JSON outside the skill source.")
    parser.add_argument("--dry-run", action="store_true", help="Read-only preview. Requires --artifact-dir; never fetches, writes, builds, or opens Chrome.")
    args = parser.parse_args(argv)
    if args.mode in {"plan", "setup", "run"} and not args.page_url:
        parser.error("--page-url is required for plan, setup and run.")
    if args.mode == "setup" and not args.resource_map:
        parser.error("setup requires --resource-map; a single --override-file is no longer sufficient.")
    if args.mode == "verify" and (not args.receipt or not args.runtime_evidence):
        parser.error("verify requires --receipt and --runtime-evidence.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ensure_native_filesystem_runtime()
        if args.mode in {"setup", "run", "plan"}:
            resource_workflow(args)
        elif args.mode == "inventory":
            inventory(args)
        elif args.mode == "verify":
            verify(args)
        else:
            status(args)
    except (SkillError, ResourceSetError, OSError, KeyError, ValueError) as exc:
        section("ERROR")
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
