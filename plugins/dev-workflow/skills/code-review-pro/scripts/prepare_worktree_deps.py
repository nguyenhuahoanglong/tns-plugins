#!/usr/bin/env python3
"""Manage node_modules junctions in git worktrees used for code review.

Mirrored in code-review-pro/scripts/ and code-review-lite/scripts/ — keep in sync.

PREPARE mode: detects JS project roots from changed files (diff or --changed-file),
then for each root checks whether the source repo's node_modules is usable (present,
and either its node_modules/.bin has installed binaries or the project declares no
dependencies/devDependencies). Usable source deps are junction-linked into the
worktree exactly as before. When source deps are missing or unusable (e.g. present
but stale — package.json declares deps yet .bin is empty) and the diff didn't already
force a skip-build (manifest/lockfile changed), a frozen, lockfile-gated install runs
directly in the worktree project directory: ``npm ci --prefer-offline --no-audit
--no-fund`` for package-lock.json/npm-shrinkwrap.json, ``yarn install
--frozen-lockfile`` for yarn.lock, or ``pnpm install --frozen-lockfile
--prefer-offline`` for pnpm-lock.yaml. No lockfile present -> skip-build instead.
Pass --no-install to restore the old junction-only behavior: missing/unusable source
deps become skip-build and no install subprocess ever runs.

--require-bin NAME (repeatable) names a build tool the approved build command needs
(e.g. vite, tsc, webpack, react-scripts, vitest). When given, a project's source
node_modules is usable only if every required bin also resolves in that project's
node_modules/.bin as NAME, NAME.cmd, NAME.ps1, or NAME.exe (Windows shims). This check
applies uniformly to every JS project root found — it is deliberately NOT filtered by
whether the project's package.json "declares" the tool, because a bin's provider
package name doesn't reliably match the bin name (e.g. "tsc" ships from the
"typescript" package), so a declared-dependency relevance filter can't be made sound
and would silently miss exactly the broken-install shape this option exists to catch.
A populated-but-incomplete .bin (e.g. present but missing the project's own build tool
— a production-only install) is treated the same as an unusable source: falls through
to the lockfile-gated install / skip-build path above. Without --require-bin,
health-check behavior is unchanged.

TEARDOWN mode: removes every node_modules junction under the worktree WITHOUT
recursing into the junction target — i.e., it is safe and cannot delete real source
node_modules.

Usage:
    python prepare_worktree_deps.py --worktree <abs> --repo <abs> [--diff <abs>]
                                    [--changed-file <rel> ...] [--require-bin NAME ...]
                                    [--no-install] [--install-timeout <seconds>] [--json]
    python prepare_worktree_deps.py --teardown --worktree <abs> [--json]

Exit codes:
    0  success (includes skip-build / install / install-failed / no JS projects)
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


def _run_install(command, cwd, timeout):
    """Run *command* (a space-separated string) in *cwd*.

    npm/yarn/pnpm ship as .cmd shims on Windows, so invoke through
    ``cmd /c`` (mirrors the ``mklink`` fallback style above). Falls back to a
    plain list invocation if ``cmd`` itself is unavailable (non-Windows).

    Returns (success: bool, reason: str) where reason is empty on success.
    """
    argv = command.split()

    def _invoke(cmd_argv):
        return subprocess.run(
            cmd_argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )

    try:
        try:
            proc = _invoke(["cmd", "/c"] + argv)
        except FileNotFoundError:
            # cmd.exe not available (non-Windows) — fall back to plain invocation
            proc = _invoke(argv)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    except OSError as exc:
        return False, str(exc)[-500:]

    if proc.returncode == 0:
        return True, ""
    stderr_tail = (proc.stderr or "").strip()[-500:]
    return False, stderr_tail or f"exit code {proc.returncode}"


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
# Source deps health check / install command selection
# ---------------------------------------------------------------------------

# Ordered so an npm lockfile takes precedence over yarn/pnpm when several exist.
_LOCKFILE_COMMANDS = (
    ("package-lock.json", "npm ci --prefer-offline --no-audit --no-fund"),
    ("npm-shrinkwrap.json", "npm ci --prefer-offline --no-audit --no-fund"),
    ("yarn.lock", "yarn install --frozen-lockfile"),
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile --prefer-offline"),
)


def _has_declared_deps(pkg_json_path):
    """True if package.json declares dependencies/devDependencies.

    A malformed or unreadable package.json is treated conservatively as
    "has deps" — we can't prove it's safe to trust an empty/missing .bin.
    """
    try:
        data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(data, dict):
        return True
    return bool(data.get("dependencies")) or bool(data.get("devDependencies"))


def _source_deps_usable(proj_abs):
    """True if proj_abs/node_modules exists and can be trusted as-is.

    Usable when node_modules/.bin has at least one installed entry, or the
    project declares no dependencies/devDependencies (so an empty/missing
    .bin is expected, not evidence of a stale install).
    """
    source_nm = proj_abs / "node_modules"
    if not source_nm.exists():
        return False
    bin_dir = source_nm / ".bin"
    if bin_dir.is_dir():
        try:
            if any(bin_dir.iterdir()):
                return True
        except OSError:
            pass
    return not _has_declared_deps(proj_abs / "package.json")


def _pick_install_command(proj_abs):
    """Return the frozen-install command string for the first lockfile found.

    Returns None if no recognized lockfile exists in the project root.
    """
    for lockfile, command in _LOCKFILE_COMMANDS:
        if (proj_abs / lockfile).exists():
            return command
    return None


_BIN_SHIM_SUFFIXES = ("", ".cmd", ".ps1", ".exe")


def _resolve_bin(bin_dir, name):
    """True if *name* (or a Windows shim variant) exists directly in bin_dir."""
    if not bin_dir.is_dir():
        return False
    return any((bin_dir / f"{name}{suffix}").exists() for suffix in _BIN_SHIM_SUFFIXES)


def _missing_required_bins(proj_abs, required_bins):
    """Return the subset of required_bins unresolved in proj_abs/node_modules/.bin.

    Applied uniformly to every JS project root passed via --require-bin — deliberately
    NOT filtered by whether the project's package.json "declares" the tool. A bin's
    provider package name doesn't reliably match the bin name (e.g. "tsc" ships from
    the "typescript" package, "webpack-cli" provides "webpack" for some setups), so a
    declared-dependency relevance filter can't be made sound and would silently
    under-check exactly the kind of broken install (PR-1583: node_modules/vite missing)
    this option exists to catch. Uniform checking can over-fire on a monorepo project
    that doesn't use the tool at all (safe over-install/skip), which is an acceptable
    trade for never missing a real broken build.
    """
    if not required_bins:
        return []
    bin_dir = proj_abs / "node_modules" / ".bin"
    return [name for name in required_bins if not _resolve_bin(bin_dir, name)]


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

def compute_strategy(proj_root, repo_root, worktree_root, changed_paths, no_install=False,
                      require_bin=None):
    """Return (strategy, extra_kwargs) for a single JS project root.

    Args:
        proj_root:    absolute Path of the project root (inside repo_root)
        repo_root:    absolute Path of the source repo root
        worktree_root: absolute Path of the worktree root
        changed_paths: set of relative-to-repo_root path strings
        require_bin:  optional iterable of build-tool bin names (e.g. "vite") that
                       must resolve in the project's node_modules/.bin for source
                       deps to be considered usable (see _missing_required_bins)

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

    # Health check: is the source node_modules present and usable as-is?
    proj_abs = repo_root / proj_rel
    source_nm = proj_abs / "node_modules"
    worktree_nm = worktree_root / proj_rel / "node_modules"

    usable = _source_deps_usable(proj_abs)
    if usable and require_bin and _missing_required_bins(proj_abs, require_bin):
        usable = False

    if usable:
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

    # Source deps are missing or unusable — install (frozen, lockfile-gated)
    # unless the caller opted out with --no-install.
    if no_install:
        return {"strategy": "skip-build", "reason": "deps unavailable", "proj_rel": proj_rel_str}

    command = _pick_install_command(proj_abs)
    if command is None:
        return {"strategy": "skip-build", "reason": "no lockfile", "proj_rel": proj_rel_str}

    return {
        "strategy": "install",
        "proj_rel": proj_rel_str,
        "command": command,
        "cwd": str(worktree_root / proj_rel),
    }


# ---------------------------------------------------------------------------
# jsDepsStrategy roll-up
# ---------------------------------------------------------------------------

_LINK_KIND_STRATEGIES = {"junction-linked", "already-exists"}
_SKIP_KIND_STRATEGIES = {"skip-build", "install-failed"}
_INSTALL_KIND_STRATEGIES = {"install"}


def rollup_strategy(results):
    """Compute the jsDepsStrategy roll-up string from a list of result dicts.

    Vocabulary: link | skip | install | mixed | none.
    - link:    junction-linked or already-exists (a usable link)
    - skip:    skip-build or install-failed
    - install: a successful install
    - mixed:   2+ distinct kinds present
    - none:    nothing actionable (e.g. only missing-source/junction-failed entries)
    """
    if not results:
        return "none"
    kinds = set()
    for r in results:
        strategy = r["strategy"]
        if strategy in _LINK_KIND_STRATEGIES:
            kinds.add("link")
        elif strategy in _SKIP_KIND_STRATEGIES:
            kinds.add("skip")
        elif strategy in _INSTALL_KIND_STRATEGIES:
            kinds.add("install")
    if not kinds:
        return "none"
    if len(kinds) == 1:
        return next(iter(kinds))
    return "mixed"


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
        result = compute_strategy(proj_root, repo, worktree, changed_paths,
                                   no_install=args.no_install, require_bin=args.require_bin)
        results.append(result)

    # 4. Execute junctions and installs
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
        elif result["strategy"] == "install":
            Path(result["cwd"]).mkdir(parents=True, exist_ok=True)
            ok, reason = _run_install(result["command"], result["cwd"], args.install_timeout)
            if not ok:
                # Non-fatal: surfaced in output, exit code stays 0.
                result["strategy"] = "install-failed"
                result["reason"] = reason

    # 5. Output
    n_linked = sum(1 for r in results if r["strategy"] == "junction-linked")
    n_skip = sum(1 for r in results if r["strategy"] == "skip-build")
    n_missing = sum(1 for r in results if r["strategy"] == "missing-source")
    n_failed = sum(1 for r in results if r["strategy"] == "junction-failed")
    n_install = sum(1 for r in results if r["strategy"] == "install")
    n_install_failed = sum(1 for r in results if r["strategy"] == "install-failed")

    if args.json:
        projects_out = []
        for r in results:
            entry = {"path": r["proj_rel"], "strategy": r["strategy"]}
            if "link" in r:
                entry["link"] = r["link"]
            if "target" in r:
                entry["target"] = r["target"]
            if "command" in r:
                entry["command"] = r["command"]
            if "cwd" in r:
                entry["cwd"] = r["cwd"]
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
            elif s == "install":
                print(f"project  {proj}  strategy=install  command={r['command']}  cwd={r['cwd']}")
            elif s == "install-failed":
                print(f"project  {proj}  strategy=install-failed  reason={r.get('reason', '')}")
            else:
                print(f"project  {proj}  strategy={s}")
        print(f"Result: {n_linked} linked, {n_skip} skip-build, {n_missing} missing-source, "
              f"{n_install} installed, {n_install_failed} install-failed")

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
    parser.add_argument("--require-bin", action="append", metavar="NAME",
                        help="Build tool bin name the approved build command needs, "
                             "e.g. vite, tsc, webpack, react-scripts, vitest (repeatable, "
                             "prepare). Checked uniformly against every JS project root; "
                             "source node_modules is unusable if any required bin is "
                             "missing from node_modules/.bin, even when .bin has other "
                             "entries (production-only install detection)")
    parser.add_argument("--no-install", action="store_true",
                        help="Prepare only: never run npm/yarn/pnpm install; "
                             "missing/unusable source deps become skip-build (prepare)")
    parser.add_argument("--install-timeout", type=int, default=480, metavar="SECONDS",
                        help="Timeout in seconds for the install subprocess (default: 480, prepare)")
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
