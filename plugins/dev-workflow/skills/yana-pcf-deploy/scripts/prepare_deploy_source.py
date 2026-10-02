#!/usr/bin/env python3
"""Resolve and materialize a guarded Yana PCF deployment source snapshot.

The caller chooses pinned source (release orchestration) or current-work source
(developer testing). Current-work deployments merge a fresh upstream/release tip
into the checked-out branch after disposable preflight, then snapshot the synced
HEAD with preserved WIP.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PRIVATE_NAMES = {
    "agents.local.md", ".env", ".npmrc", ".netrc", "credentials",
    "credentials.json", "secrets.json", "id_rsa", "id_ed25519",
}
PRIVATE_SUFFIXES = {".encrypted", ".secret", ".secrets", ".pem", ".key", ".pfx", ".p12"}
PRIVATE_DIRS = {".secrets", "secrets", "pats"}


class SourceError(RuntimeError):
    """Actionable source or snapshot failure."""


def git(repo: Path, *args: str, check: bool = True, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise SourceError(f"git {' '.join(args[:3])} failed: {message}")
    return result


def _out(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode("utf-8", "surrogateescape").strip()


def repo_root(repo: Path | str) -> Path:
    path = Path(repo).resolve()
    result = git(path, "rev-parse", "--show-toplevel")
    root = Path(_out(result)).resolve()
    if root != path:
        raise SourceError("Use repository root, not a subdirectory.")
    return root


def _current_branch(repo: Path) -> str:
    result = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if result.returncode:
        raise SourceError("Current checkout is detached; select a branch before deploying current work.")
    branch = _out(result)
    if not branch:
        raise SourceError("Could not resolve current branch.")
    return branch


def _head(repo: Path) -> str:
    return _out(git(repo, "rev-parse", "--verify", "HEAD^{commit}"))


def _upstream(repo: Path, branch: str, optional: bool = False) -> tuple[str, str, str] | None:
    remote = _out(git(repo, "config", "--get", f"branch.{branch}.remote", check=False))
    merge_ref = _out(git(repo, "config", "--get", f"branch.{branch}.merge", check=False))
    if not remote or remote == ".":
        if optional:
            return None
        raise SourceError(f"Branch '{branch}' has no usable remote upstream; cannot establish latest source.")
    if not merge_ref.startswith("refs/heads/"):
        raise SourceError(f"Branch '{branch}' has no usable remote upstream; cannot establish latest source.")
    remote_branch = merge_ref.removeprefix("refs/heads/")
    tracking_ref = f"refs/remotes/{remote}/{remote_branch}"
    return remote, remote_branch, tracking_ref


def _remote_ref(repo: Path, remote: str, branch: str) -> str:
    if not remote or branch.startswith("-") or ".." in branch or "\n" in branch:
        raise SourceError("Remote source ref is malformed.")
    return f"refs/remotes/{remote}/{branch}"


def fetch_ref(repo: Path, remote: str, branch: str, fetch: bool) -> tuple[str, str]:
    tracking_ref = _remote_ref(repo, remote, branch)
    if fetch:
        refspec = f"+refs/heads/{branch}:{tracking_ref}"
        result = git(repo, "fetch", "--no-tags", remote, refspec, check=False)
        if result.returncode:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise SourceError(f"Could not fetch latest {remote}/{branch}: {message}")
    resolved = git(repo, "rev-parse", "--verify", f"{tracking_ref}^{{commit}}", check=False)
    if resolved.returncode:
        raise SourceError(f"Remote ref '{remote}/{branch}' is unavailable; fetch latest source first.")
    return tracking_ref, _out(resolved)


def _load_config(repo: Path) -> dict[str, Any]:
    setup_file = Path(__file__).with_name("pcf_setup.py")
    if not setup_file.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("yana_pcf_setup", setup_file)
    if spec is None or spec.loader is None:
        raise SourceError("Could not load shared PCF setup configuration reader.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_config(repo)


def _created_from_release(repo: Path, branch: str) -> tuple[str, str] | None:
    """Return release branch and creation commit only from explicit branch reflog evidence."""
    result = git(repo, "reflog", "show", "--format=%H%x00%gs", f"refs/heads/{branch}", check=False)
    for record in result.stdout.splitlines():
        try:
            commit, subject = record.decode("utf-8", "replace").split("\0", 1)
        except ValueError:
            continue
        match = re.fullmatch(r"branch: Created from (?:origin/)?(\d+\.\d+\.\d+)", subject.strip(), flags=re.I)
        if match:
            return match.group(1), commit
    return None


def _release_source(repo: Path, branch: str, upstream_branch: str | None,
                    config: dict[str, Any], explicit: str | None) -> tuple[str, str, str, str | None]:
    """Resolve a release source only from exact branch, direct upstream, or explicit mapping."""
    candidate = explicit
    evidence = "explicit-confirmation" if explicit else None
    if candidate is None:
        configured = config.get("release_sources", {})
        candidate = configured.get(branch) if isinstance(configured, dict) else None
        if candidate:
            evidence = "saved-mapping"
    if candidate is None and SEMVER.fullmatch(branch):
        candidate = branch
        evidence = "current-release-branch"
    if candidate is None and upstream_branch and SEMVER.fullmatch(upstream_branch):
        candidate = upstream_branch
        evidence = "tracked-release-branch"
    creation: str | None = None
    if candidate is None:
        branch_creation = _created_from_release(repo, branch)
        if branch_creation:
            candidate, creation = branch_creation
            evidence = "branch-creation-reflog"
    if not candidate:
        raise SourceError(
            f"NEEDS_INPUT: cannot prove release source for current branch '{branch}'. "
            "Confirm exact X.Y.Z source or save branch mapping in AGENTS.local.md."
        )
    candidate = candidate.removeprefix("origin/")
    if not SEMVER.fullmatch(candidate):
        raise SourceError("Release source must be one exact X.Y.Z branch; 'latest' is not a source mapping.")
    return "origin", candidate, evidence or "unconfirmed", creation


def _private_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parts = [part.casefold() for part in PurePosixPath(normalized).parts]
    name = parts[-1] if parts else ""
    if any(part in PRIVATE_DIRS for part in parts):
        return True
    if name in PRIVATE_NAMES or name.startswith(".env."):
        return True
    return any(name.endswith(suffix) for suffix in PRIVATE_SUFFIXES)


def _nul_paths(repo: Path, *args: str) -> list[str]:
    result = git(repo, *args)
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def _safe_tracked_paths(repo: Path) -> tuple[list[str], list[str]]:
    changed = _nul_paths(repo, "diff", "--name-only", "-z", "HEAD", "--")
    safe, private = [], []
    for path in changed:
        (private if _private_path(path) else safe).append(path)
    return safe, private


def _safe_untracked_paths(repo: Path) -> tuple[list[str], list[str]]:
    untracked = _nul_paths(repo, "ls-files", "--others", "--exclude-standard", "-z")
    safe, private = [], []
    for path in untracked:
        (private if _private_path(path) else safe).append(path)
    return safe, private


def _private_ignored_paths(repo: Path) -> list[str]:
    """Find ignored private files so sync checks can fingerprint, but never copy, them."""
    ignored = _nul_paths(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    return sorted(path for path in ignored if _private_path(path))


def _local_changes(repo: Path) -> tuple[bytes, list[tuple[str, bytes]], list[str]]:
    unmerged = git(repo, "ls-files", "-u", check=False)
    if unmerged.stdout:
        raise SourceError("Working tree has unresolved Git conflicts; resolve them before deployment.")
    safe_tracked, private_tracked = _safe_tracked_paths(repo)
    safe_untracked, private_untracked = _safe_untracked_paths(repo)
    patch = b""
    if safe_tracked:
        patch = git(repo, "diff", "--binary", "--no-ext-diff", "HEAD", "--", *safe_tracked).stdout
    files: list[tuple[str, bytes]] = []
    for rel in safe_untracked:
        path = repo / Path(rel)
        if path.is_symlink():
            raise SourceError(f"Untracked source symlink is not copied into snapshot: {rel}")
        if not path.is_file():
            continue
        files.append((rel, path.read_bytes()))
    return patch, files, sorted(set(private_tracked + private_untracked + _private_ignored_paths(repo)))


def _all_wip_paths(repo: Path) -> set[str]:
    tracked = _nul_paths(repo, "diff", "--name-only", "-z", "HEAD", "--")
    untracked = _nul_paths(repo, "ls-files", "--others", "--exclude-standard", "-z")
    return set(tracked + untracked)


def _wip_signature(repo: Path) -> str:
    staged = sorted(_nul_paths(repo, "diff", "--cached", "--name-only", "-z", "HEAD", "--"))
    unstaged = sorted(_nul_paths(repo, "diff", "--name-only", "-z", "--"))
    untracked = sorted(_nul_paths(repo, "ls-files", "--others", "--exclude-standard", "-z"))
    tracked_private = [path for path in _nul_paths(repo, "ls-files", "-z") if _private_path(path)]
    ignored_private = _private_ignored_paths(repo)
    paths = sorted(set(staged + unstaged + untracked + tracked_private + ignored_private))
    records: list[tuple[str, str, str]] = []
    for rel in paths:
        path = repo / Path(rel)
        if path.is_symlink():
            value = "symlink:" + os.readlink(path)
        elif path.is_file():
            value = "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.exists():
            value = "other"
        else:
            value = "missing"
        records.append((rel, value, str(path.lstat().st_mode if path.exists() else 0)))
    payload = {
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "excludedPrivate": sorted(set(tracked_private + ignored_private)),
        "files": records,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_changed_paths(repo: Path, head: str, source_sha: str) -> set[str]:
    base_result = git(repo, "merge-base", head, source_sha, check=False)
    if base_result.returncode:
        raise SourceError("Current branch and requested source have no shared history; refusing merge.")
    base = _out(base_result)
    return set(_nul_paths(repo, "diff", "--name-only", "-z", base, source_sha, "--"))


def _merge_strategy(repo: Path, head: str, source_sha: str, source_ref: str | None) -> str:
    if not source_ref:
        return "local-only"
    relation = git(repo, "merge-base", head, source_sha, check=False)
    if relation.returncode:
        raise SourceError("Current branch and latest source have no shared Git history; refusing sync.")
    if git(repo, "merge-base", "--is-ancestor", source_sha, head, check=False).returncode == 0:
        return "already-included"
    if git(repo, "merge-base", "--is-ancestor", head, source_sha, check=False).returncode == 0:
        return "fast-forward"
    return "merge-commit"


def _remove_snapshot_private_files(worktree: Path) -> list[str]:
    """Ensure even accidentally tracked local config/secrets are absent from build input."""
    private_paths = sorted(path for path in _nul_paths(worktree, "ls-files", "-z") if _private_path(path))
    for rel in private_paths:
        path = worktree / Path(rel)
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            raise SourceError(f"Private tracked path is not a regular file in snapshot: {rel}")
    return private_paths


def _tree_content_hash(repo: Path) -> str:
    tracked = _nul_paths(repo, "ls-files", "-z")
    untracked, _ = _safe_untracked_paths(repo)
    paths = sorted(set(tracked + untracked))
    digest = hashlib.sha256()
    for rel in paths:
        if _private_path(rel):
            continue
        path = repo / Path(rel)
        if path.is_symlink():
            mode = stat.S_IFLNK
            content = os.readlink(path).encode("utf-8", "surrogateescape")
        elif path.is_file():
            mode = stat.S_IFREG | (stat.S_IMODE(path.stat().st_mode) & 0o111)
            content = path.read_bytes()
        else:
            continue
        digest.update(rel.encode("utf-8", "surrogateescape"))
        digest.update(b"\0" + str(mode).encode("ascii") + b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _changes_hash(patch: bytes, files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"tracked-patch\0")
    digest.update(patch)
    for rel, data in sorted(files):
        digest.update(b"\0untracked\0")
        digest.update(rel.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def _plan_hash(plan: dict[str, Any]) -> str:
    data = {key: value for key, value in plan.items() if key != "planHash"}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_plan(repo: Path | str, intent: str, fetch: bool = False,
              release_source: str | None = None) -> dict[str, Any]:
    root = repo_root(repo)
    if intent not in {"personal", "rc"}:
        raise SourceError("Current-work intent must be 'personal' or 'rc'.")
    branch = _current_branch(root)
    head = _head(root)
    upstream_remote: str | None = None
    upstream_branch: str | None = None
    upstream_ref: str | None = None
    if intent == "personal":
        upstream = _upstream(root, branch, optional=True)
        if upstream is None:
            remote_ref, remote_sha = None, head
            source_branch = branch
            source_kind = "local-only"
        else:
            upstream_remote, upstream_branch, upstream_ref = upstream
            remote_ref, remote_sha = fetch_ref(root, upstream_remote, upstream_branch, fetch)
            source_branch = f"{upstream_remote}/{upstream_branch}"
            source_kind = "remote-upstream"
        release_branch = None
    else:
        cfg = _load_config(root)
        # Direct upstream may establish source when it is itself an exact release branch.
        upstream = _upstream(root, branch, optional=True)
        up_remote, up_branch = (upstream[0], upstream[1]) if upstream else (None, None)
        upstream_branch = up_branch
        remote, release_branch, release_evidence, creation_sha = _release_source(root, branch, up_branch, cfg, release_source)
        remote_ref, remote_sha = fetch_ref(root, remote, release_branch, fetch)
        upstream_remote = remote
        upstream_ref = remote_ref
        source_branch = f"{remote}/{release_branch}"
        source_kind = "release-source"
        # A stored/user-confirmed mapping authorizes source choice. Still require a shared
        # history; never derive the release identity from a common ancestor alone.
        if release_evidence == "branch-creation-reflog":
            for descendant, name in ((head, "current branch"), (remote_sha, "latest release branch")):
                check = git(root, "merge-base", "--is-ancestor", creation_sha, descendant, check=False)
                if check.returncode:
                    raise SourceError(
                        f"Recorded creation from '{release_branch}' is not verified in {name}; confirm exact release source."
                    )
        if release_evidence in {"explicit-confirmation", "saved-mapping", "current-release-branch", "tracked-release-branch", "branch-creation-reflog"}:
            related = git(root, "merge-base", "HEAD", remote_sha, check=False)
            if related.returncode:
                raise SourceError(f"Configured release source '{release_branch}' has no shared history with '{branch}'.")
        else:
            raise SourceError(f"NEEDS_INPUT: release-source relationship for '{branch}' is not confirmed.")
    patch, files, private = _local_changes(root)
    changes_hash = _changes_hash(patch, files)
    plan = {
        "schemaVersion": 1,
        "sourcePolicy": "CurrentWork",
        "intent": intent,
        "currentBranch": branch,
        "currentHeadSha": head,
        "upstreamRemote": upstream_remote,
        "upstreamBranch": upstream_branch,
        "sourceRef": remote_ref,
        "sourceBranch": source_branch,
        "sourceKind": source_kind,
        "sourceSha": remote_sha,
        "mergeStrategy": _merge_strategy(root, head, remote_sha, remote_ref),
        "releaseSource": release_branch if intent == "rc" else None,
        "releaseEvidence": release_evidence if intent == "rc" else None,
        "workingChangesHash": changes_hash,
        "workingChangesPresent": bool(patch or files),
        "excludedPrivatePaths": private,
    }
    plan["planHash"] = _plan_hash(plan)
    return plan


def _read_plan(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schemaVersion") != 1 or data.get("sourcePolicy") != "CurrentWork":
        raise SourceError("Current-work source plan is invalid or unsupported.")
    if data.get("planHash") != _plan_hash(data):
        raise SourceError("Source plan hash mismatch; re-plan before deployment.")
    return data


def materialize_snapshot(repo: Path | str, data: dict[str, Any], fetch: bool = True,
                         snapshot_root: Path | None = None) -> dict[str, Any]:
    root = repo_root(repo)
    plan = _read_plan(data)
    if _current_branch(root) != plan["currentBranch"] or _head(root) != plan["currentHeadSha"]:
        raise SourceError("Current branch or HEAD changed after planning; re-plan before deployment.")
    patch, files, private = _local_changes(root)
    if private != plan.get("excludedPrivatePaths", []):
        raise SourceError("Private-file set changed after planning; re-plan before deployment.")
    if _changes_hash(patch, files) != plan["workingChangesHash"]:
        raise SourceError("Local tracked/untracked source changed after planning; re-plan before deployment.")
    source_ref = plan.get("sourceRef")
    if source_ref:
        match = re.fullmatch(r"refs/remotes/([^/]+)/(.+)", source_ref)
        if not match:
            raise SourceError("Source plan contains an invalid remote ref.")
        remote, remote_branch = match.groups()
        _, latest_sha = fetch_ref(root, remote, remote_branch, fetch)
        if latest_sha != plan["sourceSha"]:
            raise SourceError("Remote source SHA changed after planning; re-plan with latest source.")
    elif plan.get("sourceKind") != "local-only" or plan["sourceSha"] != plan["currentHeadSha"]:
        raise SourceError("Local-only source plan is invalid.")
    if snapshot_root is None:
        snapshot_root = Path(tempfile.mkdtemp(prefix="yana-pcf-source-"))
    else:
        snapshot_root = snapshot_root.resolve()
        snapshot_root.mkdir(parents=True, exist_ok=False)
    worktree = snapshot_root / "repo"
    git(root, "worktree", "add", "--detach", str(worktree), plan["currentHeadSha"])
    try:
        if source_ref:
            merge = git(worktree, "merge", "--no-commit", "--no-ff", "--no-edit", plan["sourceSha"], check=False)
            if merge.returncode:
                message = merge.stderr.decode("utf-8", "replace").strip()
                raise SourceError(f"Latest source merge conflicts in isolated preflight; original checkout preserved. {message}")
        tracked_private = _remove_snapshot_private_files(worktree)
        if patch:
            applied = git(worktree, "apply", "--3way", "--binary", "-", check=False, input_bytes=patch)
            if applied.returncode:
                message = applied.stderr.decode("utf-8", "replace").strip()
                raise SourceError(f"Local WIP cannot be replayed cleanly on latest source; original checkout preserved. {message}")
        for rel, content in files:
            destination = worktree / Path(rel)
            resolved_parent = destination.parent.resolve()
            if worktree.resolve() not in (resolved_parent, *resolved_parent.parents):
                raise SourceError(f"Untracked source escapes snapshot path: {rel}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                # The fresh upstream may have added the same path; do not silently overwrite.
                raise SourceError(f"Untracked local file collides with latest source: {rel}")
            destination.write_bytes(content)
        snapshot_git_diff = git(worktree, "diff", "--binary", "HEAD", "--").stdout
        digest = hashlib.sha256()
        digest.update(plan["planHash"].encode("ascii"))
        digest.update(snapshot_git_diff)
        for rel, content in files:
            digest.update(rel.encode("utf-8", "surrogateescape"))
            digest.update(hashlib.sha256(content).digest())
        snapshot_hash = digest.hexdigest()
        manifest = {
            "schemaVersion": 1,
            "sourcePolicy": "CurrentWork",
            "intent": plan["intent"],
            "currentBranch": plan["currentBranch"],
            "currentHeadSha": plan["currentHeadSha"],
            "sourceBranch": plan["sourceBranch"],
            "sourceKind": plan["sourceKind"],
            "sourceSha": plan["sourceSha"],
            "mergeStrategy": plan.get("mergeStrategy"),
            "releaseSource": plan.get("releaseSource"),
            "workingChangesHash": plan["workingChangesHash"],
            "snapshotHash": snapshot_hash,
            "excludedPrivatePaths": sorted(set(private + tracked_private)),
            "worktreePath": str(worktree),
            "snapshotRoot": str(snapshot_root),
        }
        return manifest
    except Exception:
        git(root, "worktree", "remove", "--force", str(worktree), check=False)
        shutil.rmtree(snapshot_root, ignore_errors=True)
        raise


def synchronize_and_snapshot(repo: Path | str, data: dict[str, Any], fetch: bool = True) -> dict[str, Any]:
    """Preflight, merge latest source into current branch, then snapshot post-sync checkout+WIP."""
    root = repo_root(repo)
    plan = _read_plan(data)
    if plan.get("currentBranch") != _current_branch(root) or plan.get("currentHeadSha") != _head(root):
        raise SourceError("Current branch or HEAD changed after planning; re-plan before deployment.")
    patch, files, private = _local_changes(root)
    if private != plan.get("excludedPrivatePaths", []) or _changes_hash(patch, files) != plan.get("workingChangesHash"):
        raise SourceError("Local tracked/untracked source changed after planning; re-plan before deployment.")

    incoming: set[str] = set()
    if plan.get("sourceRef"):
        ref_match = re.fullmatch(r"refs/remotes/([^/]+)/(.+)", plan["sourceRef"])
        if not ref_match:
            raise SourceError("Source plan contains an invalid remote ref.")
        remote, remote_branch = ref_match.groups()
        _, latest_sha = fetch_ref(root, remote, remote_branch, fetch)
        if latest_sha != plan["sourceSha"]:
            raise SourceError("Remote source SHA changed after planning; re-plan with latest source.")
        incoming = _source_changed_paths(root, plan["currentHeadSha"], plan["sourceSha"])
        overlap = sorted(incoming & _all_wip_paths(root))
        if overlap:
            raise SourceError(
                "Local WIP overlaps paths changed by latest source; branch sync is unsafe. "
                "Resolve/commit overlapping files, then re-plan: " + ", ".join(overlap[:12])
            )
        for rel in incoming:
            path = root / Path(rel)
            if path.exists() and _private_path(rel):
                raise SourceError(f"Latest source would replace excluded private local file '{rel}'; branch sync stopped.")
            if path.exists() and git(root, "check-ignore", "-q", "--", rel, check=False).returncode == 0:
                raise SourceError(f"Latest source would replace ignored local file '{rel}'; branch sync stopped.")

    initial_head = plan["currentHeadSha"]
    initial_wip = _wip_signature(root)

    # Build a disposable proof of the complete merge+WIP result before touching checkout.
    preflight = materialize_snapshot(root, plan, fetch=False)
    preflight_root = preflight["snapshotRoot"]
    keep_preflight = False
    branch_updated = False
    try:
        if plan.get("sourceRef"):
            _, latest_sha = fetch_ref(root, remote, remote_branch, fetch)
            if latest_sha != plan["sourceSha"]:
                raise SourceError("Remote source changed during preflight; re-plan before branch sync.")
            if _current_branch(root) != plan["currentBranch"] or _head(root) != initial_head:
                raise SourceError("Current branch or HEAD changed during preflight; re-plan before branch sync.")
            if _wip_signature(root) != initial_wip:
                raise SourceError("Local or excluded private files changed during preflight; re-plan before branch sync.")
            merge = git(root, "merge", "--no-edit", plan["sourceSha"], check=False)
            if merge.returncode:
                merge_head = git(root, "rev-parse", "--verify", "MERGE_HEAD", check=False)
                if merge_head.returncode == 0:
                    git(root, "merge", "--abort", check=False)
                if _head(root) == initial_head and _wip_signature(root) == initial_wip:
                    message = merge.stderr.decode("utf-8", "replace").strip()
                    raise SourceError(f"Latest source merge failed before build; checkout and WIP restored. {message}")
                keep_preflight = True
                raise SourceError(
                    "Unexpected merge failure changed checkout state. Build blocked; preserve preflight recovery "
                    f"snapshot at {preflight_root} and inspect Git status before retry."
                )
            branch_updated = _head(root) != initial_head
            if _wip_signature(root) != initial_wip:
                keep_preflight = True
                raise SourceError(
                    "Git merge changed local WIP state unexpectedly. Build blocked; preserve preflight recovery "
                    f"snapshot at {preflight_root} and inspect Git status."
                )
            _, latest_sha = fetch_ref(root, *re.fullmatch(
                r"refs/remotes/([^/]+)/(.+)", plan["sourceRef"]
            ).groups(), fetch=fetch)
            if latest_sha != plan["sourceSha"]:
                raise SourceError("Remote source changed during branch sync; re-plan before build.")

        synced_head = _head(root)
        patch_after, files_after, private_after = _local_changes(root)
        post_plan = dict(plan)
        post_plan["currentHeadSha"] = synced_head
        post_plan["workingChangesHash"] = _changes_hash(patch_after, files_after)
        post_plan["excludedPrivatePaths"] = private_after
        post_plan["planHash"] = _plan_hash(post_plan)
        snapshot = materialize_snapshot(root, post_plan, fetch=fetch)
        current_tree_hash = _tree_content_hash(root)
        snapshot_tree_hash = _tree_content_hash(Path(snapshot["worktreePath"]))
        if current_tree_hash != snapshot_tree_hash:
            cleanup_snapshot(root, snapshot["snapshotRoot"])
            raise SourceError("Post-sync source snapshot differs from checkout plus WIP; build blocked.")
        snapshot.update({
            "sourcePlanHash": plan["planHash"],
            "originalHeadSha": initial_head,
            "syncedCheckoutHeadSha": synced_head,
            "checkoutUpdated": branch_updated,
            "sourceTreeHash": current_tree_hash,
            "releaseEvidence": plan.get("releaseEvidence"),
            "mergeStrategy": plan.get("mergeStrategy"),
            "remoteUpdate": (
                f"merged latest {plan['sourceBranch']} into checked-out branch"
                if plan.get("sourceRef") else "local-only branch; no remote upstream configured"
            ),
        })
        return snapshot
    finally:
        if not keep_preflight:
            cleanup_snapshot(root, preflight_root)


def cleanup_snapshot(repo: Path | str, snapshot_root: Path | str) -> None:
    root = repo_root(repo)
    parent = Path(tempfile.gettempdir()).resolve()
    target = Path(snapshot_root).resolve()
    if parent not in (target, *target.parents) or not target.name.startswith("yana-pcf-source-"):
        raise SourceError("Refusing cleanup outside a generated Yana PCF source snapshot directory.")
    worktree = target / "repo"
    if worktree.exists():
        git(root, "worktree", "remove", "--force", str(worktree))
    shutil.rmtree(target)


def _emit(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    config_cmd = sub.add_parser("config", help="Read shared, non-secret AGENTS.local.md config.")
    config_cmd.add_argument("--repo", type=Path, required=True)
    plan_cmd = sub.add_parser("plan", help="Resolve current branch and latest approved source.")
    plan_cmd.add_argument("--repo", type=Path, required=True)
    plan_cmd.add_argument("--intent", choices=("personal", "rc"), required=True)
    plan_cmd.add_argument("--release-source", help="Exact user-confirmed X.Y.Z for this run.")
    plan_cmd.add_argument("--fetch", action="store_true")
    snapshot_cmd = sub.add_parser("snapshot", help="Create isolated source worktree from a saved plan.")
    snapshot_cmd.add_argument("--repo", type=Path, required=True)
    snapshot_cmd.add_argument("--plan-file", type=Path, required=True)
    snapshot_cmd.add_argument("--fetch", action="store_true")
    snapshot_cmd.add_argument("--snapshot-root", type=Path)
    sync_cmd = sub.add_parser("sync", help="Safely sync current branch, then snapshot post-sync code and WIP.")
    sync_cmd.add_argument("--repo", type=Path, required=True)
    sync_cmd.add_argument("--plan-file", type=Path, required=True)
    sync_cmd.add_argument("--fetch", action="store_true")
    cleanup_cmd = sub.add_parser("cleanup", help="Remove a generated isolated worktree.")
    cleanup_cmd.add_argument("--repo", type=Path, required=True)
    cleanup_cmd.add_argument("--snapshot-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "config":
            _emit(_load_config(repo_root(args.repo)))
        elif args.command == "plan":
            _emit(make_plan(args.repo, args.intent, fetch=args.fetch, release_source=args.release_source))
        elif args.command == "snapshot":
            data = json.loads(args.plan_file.read_text(encoding="utf-8-sig"))
            _emit(materialize_snapshot(args.repo, data, fetch=args.fetch, snapshot_root=args.snapshot_root))
        elif args.command == "sync":
            data = json.loads(args.plan_file.read_text(encoding="utf-8-sig"))
            _emit(synchronize_and_snapshot(args.repo, data, fetch=args.fetch))
        else:
            cleanup_snapshot(args.repo, args.snapshot_root)
            _emit({"status": "CLEANED"})
        return 0
    except (SourceError, OSError, ValueError, KeyError, TypeError) as exc:
        _emit({"status": "NEEDS_INPUT" if "NEEDS_INPUT:" in str(exc) else "BLOCKED", "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
