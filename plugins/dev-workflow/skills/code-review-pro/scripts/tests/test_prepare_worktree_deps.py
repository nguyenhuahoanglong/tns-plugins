"""Tests for prepare_worktree_deps.py.

Covers:
- changed-path parsing from a sample diff and from --changed-file
- project-root detection incl. nested/monorepo package.json
- strategy selection: lockfile changed -> skip-build; manifest unchanged +
  usable source node_modules -> junction-linked; missing/unusable source deps
  with a lockfile -> install (frozen, lockfile-gated); no lockfile -> skip-build
- --no-install opt-out restores junction-only (skip-build) behavior
- jsDepsStrategy roll-up (none/link/skip/install/mixed)
- junction round-trip: prepare creates a real junction, teardown removes ONLY
  the link — the target (with a sentinel file inside) survives intact
- exit codes 0 / 2 / 3
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Load the module under test from the sibling directory
# ---------------------------------------------------------------------------
SCRIPT = Path(__file__).parents[1] / "prepare_worktree_deps.py"
SPEC = importlib.util.spec_from_file_location("prepare_worktree_deps", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git src/components/Button.tsx src/components/Button.tsx
--- src/components/Button.tsx
+++ src/components/Button.tsx
@@ -1,3 +1,4 @@
+import React from 'react';
 export default function Button() {}
diff --git src/utils/helper.ts src/utils/helper.ts
--- src/utils/helper.ts
+++ src/utils/helper.ts
@@ -10,0 +11 @@
+export const foo = 1;
"""

# A diff that includes a lockfile change
LOCKFILE_DIFF = """\
--- package-lock.json
+++ package-lock.json
@@ -1 +1 @@
-old
+new
--- src/app.ts
+++ src/app.ts
@@ -1 +1 @@
+const x = 1;
"""

# A diff that changes package.json
PKG_JSON_DIFF = """\
--- package.json
+++ package.json
@@ -1 +1 @@
-{}
+{"version":"2.0.0"}
"""


def make_package_json(directory):
    (Path(directory) / "package.json").write_text('{"name":"test"}', encoding="utf-8")


def make_package_json_with_deps(directory):
    """package.json declaring a dependency — an empty/missing .bin then means stale."""
    (Path(directory) / "package.json").write_text(
        '{"name":"test","dependencies":{"react":"^18.0.0"}}', encoding="utf-8"
    )


def make_usable_node_modules(directory):
    """node_modules with a populated .bin — the "real install" shape."""
    nm = Path(directory) / "node_modules"
    bin_dir = nm / ".bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "vite.cmd").write_text("@echo off", encoding="utf-8")
    return nm


def make_stale_node_modules(directory):
    """node_modules present but with an empty .bin — the "stale install" shape."""
    nm = Path(directory) / "node_modules"
    (nm / ".bin").mkdir(parents=True, exist_ok=True)
    return nm


def make_package_json_with_dev_deps(directory, names):
    """package.json declaring the given names as devDependencies."""
    dev_deps = {name: "^1.0.0" for name in names}
    (Path(directory) / "package.json").write_text(
        json.dumps({"name": "test", "devDependencies": dev_deps}), encoding="utf-8"
    )


def make_populated_bin(directory, names, suffix=""):
    """node_modules/.bin populated with the given entry names (+ optional shim suffix).

    Mimics a production-only install: .bin has MANY entries but is missing the
    project's own build tool (the PR-1583 shape) unless the build tool's name is
    included in *names*.
    """
    bin_dir = Path(directory) / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (bin_dir / f"{name}{suffix}").write_text("", encoding="utf-8")
    return bin_dir


class TestParseDiffPaths(unittest.TestCase):
    """parse_diff_paths extracts paths from --- / +++ lines."""

    def test_parses_changed_paths(self):
        paths = MOD.parse_diff_paths(SAMPLE_DIFF)
        self.assertIn("src/components/Button.tsx", paths)
        self.assertIn("src/utils/helper.ts", paths)

    def test_excludes_dev_null(self):
        diff = "--- /dev/null\n+++ src/new.ts\n"
        paths = MOD.parse_diff_paths(diff)
        self.assertNotIn("/dev/null", paths)
        self.assertIn("src/new.ts", paths)

    def test_empty_diff_returns_empty(self):
        paths = MOD.parse_diff_paths("diff --git foo bar\nindex aaa..bbb\n")
        self.assertEqual(set(), paths)

    def test_lockfile_path_included(self):
        paths = MOD.parse_diff_paths(LOCKFILE_DIFF)
        self.assertIn("package-lock.json", paths)


class TestIsJsRelated(unittest.TestCase):
    def test_ts_file(self):
        self.assertTrue(MOD.is_js_related("src/app.ts"))

    def test_tsx_file(self):
        self.assertTrue(MOD.is_js_related("src/Button.tsx"))

    def test_package_json(self):
        self.assertTrue(MOD.is_js_related("package.json"))

    def test_lockfile(self):
        self.assertTrue(MOD.is_js_related("yarn.lock"))

    def test_csharp_file(self):
        self.assertFalse(MOD.is_js_related("src/Service.cs"))

    def test_python_file(self):
        self.assertFalse(MOD.is_js_related("scripts/helper.py"))


class TestFindJsProjectRoots(unittest.TestCase):
    """find_js_project_roots detects package.json at/above changed files."""

    def test_single_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_package_json(root)
            (root / "src").mkdir()
            roots = MOD.find_js_project_roots({"src/app.ts"}, root)
            self.assertEqual({root}, roots)

    def test_monorepo_nested_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_package_json(root)
            pkg_a = root / "packages" / "a"
            pkg_a.mkdir(parents=True)
            make_package_json(pkg_a)
            (pkg_a / "src").mkdir()
            roots = MOD.find_js_project_roots({"packages/a/src/index.ts"}, root)
            # Both the nested package and repo root should be detected
            self.assertIn(root, roots)
            self.assertIn(pkg_a, roots)

    def test_no_package_json_no_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # No package.json anywhere
            roots = MOD.find_js_project_roots({"src/app.ts"}, root)
            self.assertEqual(set(), roots)

    def test_non_js_file_excluded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_package_json(root)
            roots = MOD.find_js_project_roots({"Service.cs"}, root)
            self.assertEqual(set(), roots)

    def test_package_json_change_itself_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            make_package_json(root)
            roots = MOD.find_js_project_roots({"package.json"}, root)
            self.assertIn(root, roots)


class TestComputeStrategy(unittest.TestCase):
    """compute_strategy selects the right action per project root."""

    def test_lockfile_changed_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            result = MOD.compute_strategy(root, root, worktree, {"package-lock.json"})
            self.assertEqual("skip-build", result["strategy"])
            self.assertEqual("deps changed", result["reason"])

    def test_yarn_lock_changed_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            result = MOD.compute_strategy(root, root, worktree, {"yarn.lock"})
            self.assertEqual("skip-build", result["strategy"])

    def test_pkg_json_changed_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            result = MOD.compute_strategy(root, root, worktree, {"package.json"})
            self.assertEqual("skip-build", result["strategy"])

    def test_source_nm_missing_no_lockfile_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            # No node_modules in source, no lockfile either
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("skip-build", result["strategy"])
            self.assertEqual("no lockfile", result["reason"])

    def test_source_nm_present_worktree_absent_yields_junction_linked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            (root / "node_modules").mkdir()
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("junction-linked", result["strategy"])
            self.assertIn("node_modules", result["link"])
            self.assertIn("node_modules", result["target"])

    def test_worktree_nm_already_exists_yields_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            (root / "node_modules").mkdir()
            (worktree / "node_modules").mkdir()
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("already-exists", result["strategy"])

    def test_stale_node_modules_with_declared_deps_yields_install(self):
        """source node_modules exists, .bin is empty, package.json HAS deps -> install."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            make_stale_node_modules(root)
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("install", result["strategy"])
            self.assertIn("npm ci", result["command"])

    def test_stale_node_modules_no_declared_deps_yields_junction_linked(self):
        """source node_modules exists, .bin is empty, package.json has NO deps -> junction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            make_stale_node_modules(root)
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("junction-linked", result["strategy"])

    def test_missing_source_with_package_lock_yields_install_npm_ci(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            # No node_modules in source at all
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("install", result["strategy"])
            self.assertEqual("npm ci --prefer-offline --no-audit --no-fund", result["command"])
            self.assertEqual(str(worktree), result["cwd"])

    def test_missing_source_with_yarn_lock_yields_yarn_frozen_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            (root / "yarn.lock").write_text("", encoding="utf-8")
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("install", result["strategy"])
            self.assertEqual("yarn install --frozen-lockfile", result["command"])

    def test_missing_source_with_pnpm_lock_yields_pnpm_frozen_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("install", result["strategy"])
            self.assertEqual("pnpm install --frozen-lockfile --prefer-offline", result["command"])

    def test_npm_lockfile_takes_precedence_over_yarn_and_pnpm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            (root / "yarn.lock").write_text("", encoding="utf-8")
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("install", result["strategy"])
            self.assertIn("npm ci", result["command"])

    def test_missing_source_no_lockfile_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            # No lockfile at all
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("skip-build", result["strategy"])
            self.assertEqual("no lockfile", result["reason"])

    def test_no_install_flag_yields_skip_build_deps_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_deps(root)
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            # Even with a lockfile present, --no-install must skip instead of installing
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"}, no_install=True)
            self.assertEqual("skip-build", result["strategy"])
            self.assertEqual("deps unavailable", result["reason"])


class TestRequireBin(unittest.TestCase):
    """--require-bin makes the health check tool-aware (PR-1583 regression)."""

    def test_production_only_install_missing_required_bin_yields_install(self):
        """.bin has many entries but is missing the required build tool -> install."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["vite", "eslint"])
            make_populated_bin(root, ["eslint", "prettier", "jest"])  # no vite
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite"],
            )
            self.assertEqual("install", result["strategy"])
            self.assertIn("npm ci", result["command"])

    def test_required_bin_present_as_cmd_shim_yields_junction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["vite"])
            make_populated_bin(root, ["vite"], suffix=".cmd")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite"],
            )
            self.assertEqual("junction-linked", result["strategy"])

    def test_required_bin_present_as_ps1_shim_yields_junction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["tsc"])
            make_populated_bin(root, ["tsc"], suffix=".ps1")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["tsc"],
            )
            self.assertEqual("junction-linked", result["strategy"])

    def test_no_require_bin_given_is_unchanged_behavior(self):
        """Regression guard: without --require-bin, a populated .bin stays usable
        even if it happens not to contain some tool name (old behavior)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["vite"])
            make_populated_bin(root, ["eslint", "prettier", "jest"])  # no vite
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("junction-linked", result["strategy"])

    def test_required_bin_missing_with_no_install_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["vite"])
            make_populated_bin(root, ["eslint"])  # no vite
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite"], no_install=True,
            )
            self.assertEqual("skip-build", result["strategy"])
            self.assertEqual("deps unavailable", result["reason"])

    def test_required_bin_check_applies_even_when_project_doesnt_declare_it(self):
        """Uniform rule: the required-bin check is NOT filtered by declared deps.

        A relevance filter keyed on package.json dependency names can't be made sound
        (a bin's provider package name doesn't reliably match the bin name — see
        test_tsc_required_but_only_typescript_declared_still_yields_install below), so
        the check applies to every JS project root uniformly. This can over-fire on a
        project that genuinely doesn't use the tool (safe over-install/skip), which is
        the accepted trade for never missing a real broken build like PR-1583.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["react"])  # vite not declared at all
            make_populated_bin(root, ["eslint", "prettier"])  # no vite either
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite"],
            )
            self.assertEqual("install", result["strategy"])

    def test_tsc_required_but_only_typescript_declared_still_yields_install(self):
        """The discriminating case a declared-dependency relevance filter would miss.

        "tsc" is provided by the "typescript" package, so a package.json declaring
        "typescript" (not "tsc") would make a name-based relevance filter treat "tsc"
        as irrelevant and skip the check entirely — silently reintroducing the
        PR-1583 false-negative for any tool whose bin name != package name. The
        uniform rule catches this correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["typescript"])
            make_populated_bin(root, ["eslint", "prettier", "jest"])  # no tsc*
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["tsc"],
            )
            self.assertEqual("install", result["strategy"])

    def test_missing_bin_with_malformed_package_json_still_yields_install(self):
        """Unreadable/malformed package.json doesn't change the uniform bin check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            (root / "package.json").write_text("{not valid json", encoding="utf-8")
            make_populated_bin(root, ["eslint"])  # no vite
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite"],
            )
            self.assertEqual("install", result["strategy"])

    def test_multiple_required_bins_mixed_shim_suffixes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json_with_dev_deps(root, ["vite", "typescript"])
            make_populated_bin(root, ["vite"], suffix=".cmd")
            make_populated_bin(root, ["tsc"], suffix=".ps1")
            result = MOD.compute_strategy(
                root, root, worktree, {"src/app.ts"}, require_bin=["vite", "tsc"],
            )
            self.assertEqual("junction-linked", result["strategy"])


class TestRollupStrategy(unittest.TestCase):
    def test_empty_is_none(self):
        self.assertEqual("none", MOD.rollup_strategy([]))

    def test_all_linked_is_link(self):
        results = [{"strategy": "junction-linked"}, {"strategy": "junction-linked"}]
        self.assertEqual("link", MOD.rollup_strategy(results))

    def test_all_skip_is_skip(self):
        results = [{"strategy": "skip-build"}, {"strategy": "skip-build"}]
        self.assertEqual("skip", MOD.rollup_strategy(results))

    def test_mixed_link_and_skip_is_mixed(self):
        results = [{"strategy": "junction-linked"}, {"strategy": "skip-build"}]
        self.assertEqual("mixed", MOD.rollup_strategy(results))

    def test_only_missing_source_is_none(self):
        results = [{"strategy": "missing-source"}]
        self.assertEqual("none", MOD.rollup_strategy(results))

    def test_missing_and_skip_is_skip(self):
        results = [{"strategy": "missing-source"}, {"strategy": "skip-build"}]
        self.assertEqual("skip", MOD.rollup_strategy(results))

    def test_install_only_is_install(self):
        results = [{"strategy": "install"}]
        self.assertEqual("install", MOD.rollup_strategy(results))

    def test_install_failed_only_is_skip(self):
        results = [{"strategy": "install-failed"}]
        self.assertEqual("skip", MOD.rollup_strategy(results))

    def test_link_and_install_is_mixed(self):
        results = [{"strategy": "junction-linked"}, {"strategy": "install"}]
        self.assertEqual("mixed", MOD.rollup_strategy(results))

    def test_already_exists_counts_as_link(self):
        results = [{"strategy": "already-exists"}]
        self.assertEqual("link", MOD.rollup_strategy(results))


# ---------------------------------------------------------------------------
# Install execution (cmd_prepare) — subprocess.run mocked, never runs real
# npm/yarn/pnpm and never hits the network.
# ---------------------------------------------------------------------------

class TestCmdPrepareInstallExecution(unittest.TestCase):
    """Exercises cmd_prepare's install step end-to-end with subprocess.run mocked."""

    def _run_prepare(self, worktree, repo, changed_file, no_install=False, install_timeout=480,
                      require_bin=None):
        args = types.SimpleNamespace(
            worktree=str(worktree),
            repo=str(repo),
            diff=None,
            changed_file=list(changed_file),
            json=True,
            no_install=no_install,
            install_timeout=install_timeout,
            require_bin=require_bin,
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            MOD.cmd_prepare(args)
        return json.loads(buf.getvalue())

    def test_install_invoked_with_npm_ci_and_worktree_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            fake_proc = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(MOD.subprocess, "run", return_value=fake_proc) as run_mock:
                data = self._run_prepare(worktree, repo, ["src/app.ts"])
            project = data["projects"][0]
            self.assertEqual("install", project["strategy"])
            self.assertIn("npm ci", project["command"])
            run_mock.assert_called_once()
            _, kwargs = run_mock.call_args
            self.assertEqual(str(worktree), kwargs["cwd"])

    def test_stale_bin_with_declared_deps_triggers_install(self):
        """source node_modules exists, .bin empty, package.json HAS deps -> install."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            make_stale_node_modules(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            fake_proc = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(MOD.subprocess, "run", return_value=fake_proc):
                data = self._run_prepare(worktree, repo, ["src/app.ts"])
            self.assertEqual("install", data["projects"][0]["strategy"])

    def test_no_lockfile_skip_build_subprocess_not_called(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            with mock.patch.object(MOD.subprocess, "run") as run_mock:
                data = self._run_prepare(worktree, repo, ["src/app.ts"])
            self.assertEqual("skip-build", data["projects"][0]["strategy"])
            self.assertEqual("no lockfile", data["projects"][0]["reason"])
            run_mock.assert_not_called()

    def test_no_install_flag_skip_build_subprocess_not_called(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(MOD.subprocess, "run") as run_mock:
                data = self._run_prepare(worktree, repo, ["src/app.ts"], no_install=True)
            self.assertEqual("skip-build", data["projects"][0]["strategy"])
            self.assertEqual("deps unavailable", data["projects"][0]["reason"])
            run_mock.assert_not_called()

    def test_install_nonzero_returncode_yields_install_failed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            fake_proc = mock.Mock(returncode=1, stdout="", stderr="npm ERR! network timeout")
            with mock.patch.object(MOD.subprocess, "run", return_value=fake_proc):
                data = self._run_prepare(worktree, repo, ["src/app.ts"])
            project = data["projects"][0]
            self.assertEqual("install-failed", project["strategy"])
            self.assertIn("npm ERR!", project["reason"])

    def test_install_timeout_yields_install_failed_with_timeout_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(
                MOD.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(cmd="npm ci", timeout=5),
            ):
                data = self._run_prepare(worktree, repo, ["src/app.ts"], install_timeout=5)
            project = data["projects"][0]
            self.assertEqual("install-failed", project["strategy"])
            self.assertIn("timeout after 5s", project["reason"])

    def test_install_failed_does_not_raise_system_exit(self):
        """install failures are non-fatal — exit code stays 0, unlike junction failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json_with_deps(repo)
            (repo / "package-lock.json").write_text("{}", encoding="utf-8")
            fake_proc = mock.Mock(returncode=1, stdout="", stderr="boom")
            args = types.SimpleNamespace(
                worktree=str(worktree), repo=str(repo), diff=None,
                changed_file=["src/app.ts"], json=True,
                no_install=False, install_timeout=480, require_bin=None,
            )
            with mock.patch.object(MOD.subprocess, "run", return_value=fake_proc):
                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf):
                        MOD.cmd_prepare(args)
                except SystemExit as exc:
                    self.fail(f"cmd_prepare should not exit on install failure, got {exc.code}")


# ---------------------------------------------------------------------------
# Junction round-trip — safety critical
# ---------------------------------------------------------------------------

@unittest.skipUnless(sys.platform == "win32", "junction test is Windows-only")
class TestJunctionRoundTrip(unittest.TestCase):
    """Verify prepare creates a junction and teardown removes ONLY the link.

    The sentinel file inside the target must survive teardown.  If teardown
    recurses into the junction (a destructive bug), the sentinel would be gone.
    """

    def _run_script(self, *argv):
        """Invoke the script as a subprocess; return (returncode, stdout, stderr)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *argv],
            capture_output=True, text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_prepare_creates_junction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()

            # Repo has package.json + node_modules with a sentinel file
            make_package_json(repo)
            (repo / "node_modules").mkdir()
            sentinel = repo / "node_modules" / "sentinel.txt"
            sentinel.write_text("real content", encoding="utf-8")

            # A changed TS file (not a dep change)
            rc, stdout, stderr = self._run_script(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "src/app.ts",
            )
            self.assertEqual(0, rc, msg=stderr)
            nm_link = worktree / "node_modules"
            self.assertTrue(nm_link.exists(), "junction was not created")
            # sentinel is visible through the junction
            self.assertTrue((nm_link / "sentinel.txt").exists(),
                            "sentinel not visible through junction")

    def test_teardown_removes_link_not_target(self):
        """SAFETY: teardown must not delete the junction target's contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()

            make_package_json(repo)
            (repo / "node_modules").mkdir()
            sentinel = repo / "node_modules" / "sentinel.txt"
            sentinel.write_text("real content", encoding="utf-8")

            # Prepare first
            rc, _, stderr = self._run_script(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "src/app.ts",
            )
            self.assertEqual(0, rc, msg=f"prepare failed: {stderr}")

            nm_link = worktree / "node_modules"
            self.assertTrue(MOD._is_junction(nm_link), "expected a junction")

            # Teardown
            rc, stdout, stderr = self._run_script(
                "--teardown",
                "--worktree", str(worktree),
            )
            self.assertEqual(0, rc, msg=f"teardown failed: {stderr}")

            # Junction is gone
            self.assertFalse(nm_link.exists(), "junction should have been removed")

            # Sentinel in the REAL source directory survives
            self.assertTrue(sentinel.exists(),
                            "SAFETY VIOLATION: teardown deleted the junction target contents")
            self.assertEqual("real content", sentinel.read_text(encoding="utf-8"))

    def test_teardown_skips_real_directories(self):
        """Teardown must not touch real node_modules directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            real_nm = worktree / "node_modules"
            real_nm.mkdir()
            sentinel = real_nm / "keep.txt"
            sentinel.write_text("do not delete", encoding="utf-8")

            rc, stdout, stderr = self._run_script(
                "--teardown",
                "--worktree", str(worktree),
            )
            self.assertEqual(0, rc, msg=f"teardown errored: {stderr}")
            self.assertTrue(sentinel.exists(), "teardown deleted a real directory")

    def test_json_output_prepare(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)
            (repo / "node_modules").mkdir()

            rc, stdout, stderr = self._run_script(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "src/app.ts",
                "--json",
            )
            self.assertEqual(0, rc, msg=stderr)
            data = json.loads(stdout)
            self.assertIn("projects", data)
            self.assertIn("jsDepsStrategy", data)
            self.assertEqual("link", data["jsDepsStrategy"])

    def test_json_output_teardown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()

            rc, stdout, stderr = self._run_script(
                "--teardown",
                "--worktree", str(worktree),
                "--json",
            )
            self.assertEqual(0, rc, msg=stderr)
            data = json.loads(stdout)
            self.assertIn("removed", data)
            self.assertEqual([], data["removed"])


# ---------------------------------------------------------------------------
# Exit code tests (subprocess)
# ---------------------------------------------------------------------------

class TestExitCodes(unittest.TestCase):
    def _run(self, *argv):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *argv],
            capture_output=True, text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_exit_0_no_js_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            # C# only — no package.json in repo
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "Service.cs",
            )
            self.assertEqual(0, rc)

    def test_exit_0_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "package-lock.json",
            )
            self.assertEqual(0, rc)

    def test_exit_0_missing_source_no_lockfile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)
            # No node_modules in repo, no lockfile -> skip-build, not a fatal error
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--changed-file", "src/app.ts",
            )
            self.assertEqual(0, rc)

    def test_exit_3_no_diff_no_changed_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
            )
            self.assertEqual(3, rc)

    def test_exit_3_diff_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--diff", str(Path(tmpdir) / "nonexistent.diff"),
            )
            self.assertEqual(3, rc)

    def test_exit_2_worktree_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()
            rc, _, _ = self._run(
                "--worktree", str(Path(tmpdir) / "does_not_exist"),
                "--repo", str(repo),
                "--changed-file", "src/app.ts",
            )
            self.assertEqual(2, rc)

    def test_exit_2_repo_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            rc, _, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(Path(tmpdir) / "does_not_exist"),
                "--changed-file", "src/app.ts",
            )
            self.assertEqual(2, rc)

    def test_exit_0_teardown_empty_worktree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            rc, _, _ = self._run("--teardown", "--worktree", str(worktree))
            self.assertEqual(0, rc)

    def test_exit_2_teardown_worktree_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rc, _, _ = self._run(
                "--teardown",
                "--worktree", str(Path(tmpdir) / "does_not_exist"),
            )
            self.assertEqual(2, rc)

    def test_parse_diff_file(self):
        """--diff file is parsed correctly (integration via subprocess)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)

            diff_file = Path(tmpdir) / "changes.diff"
            diff_file.write_text(SAMPLE_DIFF, encoding="utf-8")

            rc, stdout, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--diff", str(diff_file),
            )
            # Should succeed (no node_modules and no lockfile in repo -> skip-build)
            self.assertEqual(0, rc)
            self.assertIn("skip-build", stdout)

    def test_lockfile_in_diff_yields_skip_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)
            (repo / "node_modules").mkdir()

            diff_file = Path(tmpdir) / "lock.diff"
            diff_file.write_text(LOCKFILE_DIFF, encoding="utf-8")

            rc, stdout, _ = self._run(
                "--worktree", str(worktree),
                "--repo", str(repo),
                "--diff", str(diff_file),
            )
            self.assertEqual(0, rc)
            self.assertIn("skip-build", stdout)


if __name__ == "__main__":
    unittest.main()
