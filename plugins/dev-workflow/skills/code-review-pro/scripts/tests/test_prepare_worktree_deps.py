"""Tests for prepare_worktree_deps.py.

Covers:
- changed-path parsing from a sample diff and from --changed-file
- project-root detection incl. nested/monorepo package.json
- strategy selection: lockfile changed -> skip-build; manifest unchanged +
  source node_modules present -> junction-linked; missing source -> missing-source
- jsDepsStrategy roll-up (none/link/skip/mixed)
- junction round-trip: prepare creates a real junction, teardown removes ONLY
  the link — the target (with a sentinel file inside) survives intact
- exit codes 0 / 2 / 3
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_source_nm_missing_yields_missing_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = Path(tmpdir) / "wt"
            worktree.mkdir()
            make_package_json(root)
            # No node_modules in source
            result = MOD.compute_strategy(root, root, worktree, {"src/app.ts"})
            self.assertEqual("missing-source", result["strategy"])

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

    def test_exit_0_missing_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            worktree = Path(tmpdir) / "wt"
            repo.mkdir()
            worktree.mkdir()
            make_package_json(repo)
            # No node_modules in repo
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
            # Should succeed (missing-source, no node_modules in repo)
            self.assertEqual(0, rc)
            self.assertIn("missing-source", stdout)

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
