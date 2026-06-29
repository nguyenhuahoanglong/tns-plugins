#!/usr/bin/env python3
"""Manage node_modules junctions in git worktrees used for code review.

Mirrored in code-review-pro/scripts/ and code-review-lite/scripts/ — keep in sync.

PREPARE mode: detects JS project roots from changed files (diff or --changed-file),
then for each root either creates a Windows directory junction pointing at the source
repo's node_modules or records a skip-build reason (when deps changed). Never runs
npm/yarn/pnpm install.

TEARDOWN mode: removes every node_modules junction under the worktree WITHOUT
recursing into the junction target — i.e., it is safe and cannot delete real source
node_modules.

Usage:
    python prepare_worktree_deps.py --worktree <abs> --repo <abs> [--diff <abs>]
                                    [--changed-file <rel> ...] [--json]
    python prepare_worktree_deps.py --teardown --worktree <abs> [--json]

Exit codes:
    0  success (includes skip-build / missing-source / no JS projects)
    2  IO/OS failure (junction create/remove failed; --worktree/--repo not a directory)
    3  (prepare only) no --diff readable and no --changed-file given
"""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Console / output helpers
# ---------------------------------------------------------------------------

def configure_utf8_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def fail(code, message):
    print(f"prepare_worktree_deps: {message}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Junction helpers
# ---------------------------------------------------------------------------

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_junction(path):
    """Return True if *path* is a Windows directory junction (reparse point)."""
    try:
        # Python 3.12+ exposes os.path.isjunction
        if hasattr(os.path, "isjunction"):
            return os.path.isjunction(path)
        st = os.lstat(path)
        return bool(st.st_file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False


def _create_junction(link, target):
    """Create a directory junction at *link* pointing to *target*.

    Tries _winapi.CreateJunction first (no admin needed on Windows 10+).
    Falls back to ``cmd /c mklink /J`` on AttributeError/OSError.

    Returns (success: bool, error_message: str).
    """
    link_str = str(link)
    target_str = str(target)

    # Primary: use stdlib _winapi (available on CPython/Windows, no admin req)
    try:
        import _winapi  # type: ignore[import]
        _winapi.CreateJunction(target_str, link_str)
        return True, ""
    except AttributeError:
        pass  # module not present (non-Windows or non-CPython) — fall through
    except OSError as exc:
        first_error = str(exc)
    else:
        first_error = ""

    # Fallback: cmd /c mklink /J  (link first, target second — same as CreateJunction)
    try:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link_str, target_str],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True, ""
        err = result.stderr.strip() or result.stdout.strip()
        return False, f"mklink /J failed: {err}"
    except OSError as exc:
        return False, f"cmd mklink fallback failed: {exc}"


def _remove_junction(path):
    """Remove a junction at *path* WITHOUT recursing into its target.

    Uses os.rmdir (removes the link entry only) or ``cmd /c rmdir`` WITHOUT /s.
    Returns (success: bool, error_message: str).
    """
    path_str = str(path)
    try:
        os.rmdir(path)
        return True, ""
    except OSError as exc:
        first_error = str(exc)

    # Fallback: cmd /c rmdir — note: NO /s flag, so it only removes the junction link
    try:
        result = subprocess.run(
            ["cmd", "/c", "rmdir", path_str],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True, ""
        err = result.stderr.strip() or result.stdout.strip()
        return False, f"rmdir failed: {err}"
    except OSError as exc:
        return False, f"cmd rmdir fallback failed: {exc}"


# ---------------------------------------------------------------------------
# Diff / changed-path parsing
# ---------------------------------------------------------------------------

_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"}
_JS_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json",  # catches package.json changes detected separately
    ".vue", ".svelte",
}


def parse_diff_paths(diff_text):
    """Extract changed relative paths from a ``git diff --no-prefix`` diff text.

    ``git diff --no-prefix`` omits the a/ b/ prefix, so ``+++ file.ts`` is the path.
    We collect paths from both ``---`` and ``+++`` lines (excluding /dev/null).
    """
    paths = set()
    for line in diff_text.splitlines():
        for prefix in ("--- ", "+++ "):
            if line.startswith(prefix):
                p = line[len(prefix):].strip()
                if p and p != "/dev/null":
                    paths.add(p)
    return paths


def is_js_related(path_str):
    """True if the path looks like it belongs to a JS/TS project."""
    p = Path(path_str)
    if p.name == "package.json":
        return True
    if p.name in _LOCKFILES:
        return True
    return p.suffix.lower() in _JS_EXTENSIONS


def find_js_project_roots(changed_paths, repo_root):
    """Return a set of Path objects (relative to repo_root) that are JS project roots.

    A JS project root is a directory that contains a ``package.json`` somewhere at
    or above each changed path, stopping at (and including) the repo root itself.

    Strategy:
    - For each changed path that is JS-related, walk from its directory up to repo_root.
    - Collect every directory that contains a package.json.
    - Also check the repo root directly if any changed file is JS-related.
    """
    repo_root = Path(repo_root).resolve()
    roots = set()

    for rel_str in changed_paths:
        if not is_js_related(rel_str):
            continue
        candidate = (repo_root / rel_str).resolve()
        # Start from the file's directory (or itself if it's a dir)
        if candidate.is_file():
            candidate = candidate.parent
        while True:
            pkg = candidate / "package.json"
            if pkg.exists():
                roots.add(candidate)
            if candidate == repo_root:
                break
            parent = candidate.parent
            if parent == candidate:  # filesystem root guard
                break
            candidate = parent

    return roots


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

def compute_strategy(proj_root, repo_root, worktree_root, changed_paths):
    """Return (strategy, extra_kwargs) for a single JS project root.

    Args:
        proj_root:    absolute Path of the project root (inside repo_root)
        repo_root:    absolute Path of the source repo root
        worktree_root: absolute Path of the worktree root
        changed_paths: set of relative-to-repo_root path strings

    Returns a dict with at minimum {"strategy": <str>} plus optional keys.
    """
    proj_root = Path(proj_root).resolve()
    repo_root = Path(repo_root).resolve()
    worktree_root = Path(worktree_root).resolve()

    try:
        proj_rel = proj_root.relative_to(repo_root)
    except ValueError:
        proj_rel = Path(".")

    proj_rel_str = str(proj_rel).replace("\\", "/")

    # Build the set of changed filenames within this project subtree (for lockfile check)
    norm_changed = set()
    for cp in changed_paths:
        norm_changed.add(cp.replace("\\", "/"))

    # Check whether package.json or any lockfile for this project is in the changed set
    def _in_changed(rel_file):
        # rel_file is relative to repo root
        rel_norm = str(rel_file).replace("\\", "/")
        return rel_norm in norm_changed

    pkg_json_rel = proj_rel / "package.json"
    if _in_changed(pkg_json_rel):
        return {"strategy": "skip-build", "reason": "deps changed", "proj_rel": proj_rel_str}

    for lockfile in _LOCKFILES:
        lockfile_rel = proj_rel / lockfile
        if _in_changed(lockfile_rel):
            return {"strategy": "skip-build", "reason": "deps changed", "proj_rel": proj_rel_str}

    # Check source node_modules existence
    source_nm = repo_root / proj_rel / "node_modules"
    if not source_nm.exists():
        return {"strategy": "missing-source", "proj_rel": proj_rel_str}

    # Check worktree node_modules
    worktree_nm = worktree_root / proj_rel / "node_modules"
    if worktree_nm.exists():
        return {
            "strategy": "already-exists",
            "proj_rel": proj_rel_str,
            "link": str(worktree_nm),
            "target": str(source_nm),
        }

    # Create junction
    return {
        "strategy": "junction-linked",
        "proj_rel": proj_rel_str,
        "link": str(worktree_nm),
        "target": str(source_nm),
    }


# ---------------------------------------------------------------------------
# jsDepsStrategy roll-up
# ---------------------------------------------------------------------------

def rollup_strategy(results):
    """Compute the jsDepsStrategy roll-up string from a list of result dicts."""
    if not results:
        return "none"
    strategies = {r["strategy"] for r in results}
    has_link = "junction-linked" in strategies
    has_skip = "skip-build" in strategies
    if has_link and has_skip:
        return "mixed"
    if has_link:
        return "link"
    if has_skip:
        return "skip"
    return "none"  # only missing-source or already-exists — no actionable links


# ---------------------------------------------------------------------------
# PREPARE command
# ---------------------------------------------------------------------------

def cmd_prepare(args):
    worktree = Path(args.worktree).resolve()
    repo = Path(args.repo).resolve()

    if not worktree.is_dir():
        fail(2, f"--worktree is not a directory: {worktree}")
    if not repo.is_dir():
        fail(2, f"--repo is not a directory: {repo}")

    # 1. Determine changed paths
    changed_paths = set()
    if args.changed_file:
        for f in args.changed_file:
            changed_paths.add(f.replace("\\", "/"))
    elif args.diff:
        diff_file = Path(args.diff)
        try:
            diff_text = diff_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            fail(3, f"cannot read --diff file: {exc}")
        changed_paths = parse_diff_paths(diff_text)
    else:
        fail(3, "no --diff file and no --changed-file arguments given")

    if not changed_paths:
        fail(3, "changed path set is empty after parsing --diff/--changed-file")

    # 2. Find JS project roots
    js_roots = find_js_project_roots(changed_paths, repo)

    results = []

    if not js_roots:
        if not args.json:
            print("=== WORKTREE DEPS: prepare ===")
            print("(no JS project roots found in changed paths)")
            print("Result: 0 linked, 0 skip-build, 0 missing-source")
        else:
            print(json.dumps({"projects": [], "jsDepsStrategy": "none"}, indent=2))
        return

    # 3. Compute strategy per project root
    for proj_root in sorted(js_roots):
        result = compute_strategy(proj_root, repo, worktree, changed_paths)
        results.append(result)

    # 4. Execute junctions
    os_errors = []
    for result in results:
        if result["strategy"] == "junction-linked":
            link = Path(result["link"])
            target = Path(result["target"])
            link.parent.mkdir(parents=True, exist_ok=True)
            ok, err_msg = _create_junction(link, target)
            if not ok:
                result["strategy"] = "junction-failed"
                result["error"] = err_msg
                os_errors.append(f"{result['proj_rel']}: {err_msg}")

    # 5. Output
    n_linked = sum(1 for r in results if r["strategy"] == "junction-linked")
    n_skip = sum(1 for r in results if r["strategy"] == "skip-build")
    n_missing = sum(1 for r in results if r["strategy"] == "missing-source")
    n_failed = sum(1 for r in results if r["strategy"] == "junction-failed")

    if args.json:
        projects_out = []
        for r in results:
            entry = {"path": r["proj_rel"], "strategy": r["strategy"]}
            if "link" in r:
                entry["link"] = r["link"]
            if "target" in r:
                entry["target"] = r["target"]
            if "reason" in r:
                entry["reason"] = r["reason"]
            if "error" in r:
                entry["error"] = r["error"]
            projects_out.append(entry)
        print(json.dumps({
            "projects": projects_out,
            "jsDepsStrategy": rollup_strategy(results),
        }, indent=2))
    else:
        print("=== WORKTREE DEPS: prepare ===")
        for r in results:
            s = r["strategy"]
            proj = r["proj_rel"]
            if s == "junction-linked":
                print(f"project  {proj}  strategy=junction-linked  source={r['target']}  link={r['link']}")
            elif s == "skip-build":
                print(f"project  {proj}  strategy=skip-build  reason={r.get('reason', 'deps changed')}")
            elif s == "missing-source":
                print(f"project  {proj}  strategy=missing-source")
            elif s == "already-exists":
                print(f"project  {proj}  strategy=already-exists  link={r['link']}")
            elif s == "junction-failed":
                print(f"project  {proj}  strategy=junction-failed  error={r.get('error', '')}")
            else:
                print(f"project  {proj}  strategy={s}")
        print(f"Result: {n_linked} linked, {n_skip} skip-build, {n_missing} missing-source")

    if os_errors:
        fail(2, "one or more junctions could not be created:\n" + "\n".join(os_errors))


# ---------------------------------------------------------------------------
# TEARDOWN command
# ---------------------------------------------------------------------------

def _find_node_modules(worktree_root):
    """Yield Path objects for every node_modules directory under worktree_root."""
    worktree_root = Path(worktree_root)
    for dirpath, dirnames, _ in os.walk(worktree_root, topdown=True):
        dp = Path(dirpath)
        if dp.name == "node_modules":
            yield dp
            # Do NOT descend into node_modules — avoids nested traversal
            dirnames.clear()
            continue
        # Prune node_modules from traversal if it appears in dirnames
        if "node_modules" in dirnames:
            yield dp / "node_modules"
            dirnames.remove("node_modules")


def cmd_teardown(args):
    worktree = Path(args.worktree).resolve()

    if not worktree.is_dir():
        fail(2, f"--worktree is not a directory: {worktree}")

    removed = []
    errors = []

    for nm_path in _find_node_modules(worktree):
        if not _is_junction(nm_path):
            # Real directory — leave it alone
            continue
        ok, err_msg = _remove_junction(nm_path)
        if ok:
            removed.append(nm_path)
        else:
            errors.append(f"{nm_path}: {err_msg}")

    if args.json:
        print(json.dumps({
            "removed": [str(p) for p in removed],
            "errors": errors,
        }, indent=2))
    else:
        print("=== WORKTREE DEPS: teardown ===")
        for p in removed:
            print(f"removed junction  {p}")
        if errors:
            for e in errors:
                print(f"ERROR  {e}")
        print(f"Result: {len(removed)} junction(s) removed")

    if errors:
        fail(2, "one or more junctions could not be removed:\n" + "\n".join(errors))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    parser.add_argument("--worktree", required=True,
                        help="Absolute path to the git worktree root")
    parser.add_argument("--repo",
                        help="Absolute path to the source repo root (required for prepare)")
    parser.add_argument("--diff",
                        help="Absolute path to a git diff --no-prefix diff file (prepare)")
    parser.add_argument("--changed-file", action="append", metavar="REL_PATH",
                        help="Relative changed file path (repeatable, prepare)")
    parser.add_argument("--teardown", action="store_true",
                        help="Remove node_modules junctions from the worktree")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON output instead of structured text")

    args = parser.parse_args()

    if args.teardown:
        cmd_teardown(args)
    else:
        if not args.repo:
            fail(2, "--repo is required for prepare mode")
        cmd_prepare(args)


if __name__ == "__main__":
    main()
