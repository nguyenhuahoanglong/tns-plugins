"""Behavior tests for current-work source resolution and isolated snapshots."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "prepare_deploy_source.py"
SPEC = importlib.util.spec_from_file_location("prepare_deploy_source", SCRIPT)
source = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(source)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def init_repo(path: Path, branch: str = "dev") -> None:
    path.mkdir(parents=True)
    git(path, "init", "--initial-branch", branch)
    git(path, "config", "user.name", "PCF Test")
    git(path, "config", "user.email", "pcf-test@example.invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    (path / "remote.txt").write_text("remote-base\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "initial")


def add_origin(repo: Path, bare: Path, branch: str = "dev") -> None:
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(bare.parent, "init", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "--set-upstream", "origin", branch)


def clone(bare: Path, path: Path, branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--branch", branch, str(bare), str(path)],
        capture_output=True, check=True,
    )
    git(path, "config", "user.name", "PCF Test")
    git(path, "config", "user.email", "pcf-test@example.invalid")


class PrepareDeploySourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pcf-source-test-")
        self.root = Path(self.temp.name)
        self.bare = self.root / "origin.git"
        self.repo = self.root / "repo"
        init_repo(self.repo)
        add_origin(self.repo, self.bare)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_personal_snapshot_merges_latest_upstream_and_preserves_all_local_work(self) -> None:
        # Local staged, unstaged, and untracked changes exist while upstream advances.
        (self.repo / "tracked.txt").write_text("local staged\n", encoding="utf-8")
        git(self.repo, "add", "tracked.txt")
        (self.repo / "tracked.txt").write_text("local staged plus unstaged\n", encoding="utf-8")
        (self.repo / "scratch.ts").write_text("untracked source\n", encoding="utf-8")
        writer = self.root / "writer"
        clone(self.bare, writer, "dev")
        (writer / "remote.txt").write_text("latest remote\n", encoding="utf-8")
        git(writer, "commit", "-am", "advance remote")
        git(writer, "push", "origin", "dev")

        original_head = git(self.repo, "rev-parse", "HEAD")
        plan = source.make_plan(self.repo, "personal", fetch=True)
        self.assertEqual(plan["mergeStrategy"], "fast-forward")
        snapshot = source.synchronize_and_snapshot(self.repo, plan, fetch=True)
        worktree = Path(snapshot["worktreePath"])
        try:
            self.assertEqual((worktree / "remote.txt").read_text(encoding="utf-8"), "latest remote\n")
            self.assertEqual((worktree / "tracked.txt").read_text(encoding="utf-8"), "local staged plus unstaged\n")
            self.assertEqual((worktree / "scratch.ts").read_text(encoding="utf-8"), "untracked source\n")
            self.assertEqual(snapshot["originalHeadSha"], original_head)
            self.assertEqual(snapshot["syncedCheckoutHeadSha"], git(self.repo, "rev-parse", "HEAD"))
            self.assertTrue(snapshot["checkoutUpdated"])
            self.assertNotEqual(git(self.repo, "rev-parse", "HEAD"), original_head)
            self.assertEqual((self.repo / "remote.txt").read_text(encoding="utf-8"), "latest remote\n")
            self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "local staged plus unstaged\n")
            self.assertTrue(snapshot["snapshotHash"])
            self.assertEqual(snapshot["sourceSha"], git(self.bare, "rev-parse", "refs/heads/dev"))
        finally:
            source.cleanup_snapshot(self.repo, snapshot["snapshotRoot"])
        self.assertFalse(worktree.exists())

    def test_rc_uses_confirmed_branch_mapping_and_merges_latest_release(self) -> None:
        git(self.repo, "checkout", "-b", "US/123")
        git(self.repo, "push", "--set-upstream", "origin", "US/123")
        git(self.repo, "checkout", "-b", "1.5.0")
        (self.repo / "release.txt").write_text("rc source\n", encoding="utf-8")
        git(self.repo, "add", "release.txt")
        git(self.repo, "commit", "-m", "release content")
        git(self.repo, "push", "--set-upstream", "origin", "1.5.0")
        git(self.repo, "checkout", "US/123")
        config = {
            "release_sources": {"US/123": "1.5.0"},
        }
        (self.repo / "AGENTS.local.md").write_text(
            "<!-- yana-pcf-config:start -->\n"
            "```pcf-config\n" + json.dumps(config, indent=2) +
            "\n```\n<!-- yana-pcf-config:end -->\n",
            encoding="utf-8",
        )
        (self.repo / "tracked.txt").write_text("work in progress\n", encoding="utf-8")
        plan = source.make_plan(self.repo, "rc", fetch=True)
        self.assertEqual(plan["releaseSource"], "1.5.0")
        snap = source.synchronize_and_snapshot(self.repo, plan, fetch=True)
        try:
            tree = Path(snap["worktreePath"])
            self.assertEqual((tree / "release.txt").read_text(encoding="utf-8"), "rc source\n")
            self.assertEqual((tree / "tracked.txt").read_text(encoding="utf-8"), "work in progress\n")
            self.assertEqual((self.repo / "release.txt").read_text(encoding="utf-8"), "rc source\n")
            self.assertTrue(snap["checkoutUpdated"])
            self.assertFalse((tree / "AGENTS.local.md").exists())
            self.assertEqual(git(self.repo, "symbolic-ref", "--short", "HEAD"), "US/123")
            self.assertIn("AGENTS.local.md", snap["excludedPrivatePaths"])
        finally:
            source.cleanup_snapshot(self.repo, snap["snapshotRoot"])

    def test_rc_does_not_guess_from_shared_ancestor(self) -> None:
        git(self.repo, "checkout", "-b", "US/456")
        git(self.repo, "push", "--set-upstream", "origin", "US/456")
        with self.assertRaisesRegex(source.SourceError, "NEEDS_INPUT"):
            source.make_plan(self.repo, "rc", fetch=False)

    def test_rc_uses_verified_branch_creation_reflog(self) -> None:
        git(self.repo, "checkout", "-b", "1.7.0")
        (self.repo / "release.txt").write_text("release base\n", encoding="utf-8")
        git(self.repo, "add", "release.txt")
        git(self.repo, "commit", "-m", "release base")
        git(self.repo, "push", "--set-upstream", "origin", "1.7.0")
        git(self.repo, "checkout", "dev")
        git(self.repo, "checkout", "-b", "US/789", "origin/1.7.0")
        git(self.repo, "push", "--set-upstream", "origin", "US/789")
        plan = source.make_plan(self.repo, "rc", fetch=True)
        self.assertEqual(plan["releaseSource"], "1.7.0")
        self.assertEqual(plan["releaseEvidence"], "branch-creation-reflog")

    def test_local_wip_overlap_stops_before_branch_sync(self) -> None:
        (self.repo / "tracked.txt").write_text("line one\nline two\n", encoding="utf-8")
        git(self.repo, "commit", "-am", "add two lines")
        git(self.repo, "push", "origin", "dev")
        (self.repo / "tracked.txt").write_text("local line one\nline two\n", encoding="utf-8")
        writer = self.root / "writer"
        clone(self.bare, writer, "dev")
        (writer / "tracked.txt").write_text("base\nremote line two\n", encoding="utf-8")
        git(writer, "commit", "-am", "remote line")
        git(writer, "push", "origin", "dev")
        plan = source.make_plan(self.repo, "personal", fetch=True)
        original_head = git(self.repo, "rev-parse", "HEAD")
        original_text = (self.repo / "tracked.txt").read_text(encoding="utf-8")
        with self.assertRaisesRegex(source.SourceError, "preflight|overlaps"):
            source.synchronize_and_snapshot(self.repo, plan, fetch=True)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original_head)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), original_text)

    def test_local_only_branch_can_deploy_without_remote_update(self) -> None:
        local = self.root / "local-only"
        init_repo(local, "work")
        (local / "tracked.txt").write_text("local test\n", encoding="utf-8")
        original_head = git(local, "rev-parse", "HEAD")
        plan = source.make_plan(local, "personal", fetch=True)
        self.assertEqual(plan["sourceKind"], "local-only")
        self.assertEqual(plan["sourceSha"], original_head)
        snapshot = source.synchronize_and_snapshot(local, plan, fetch=True)
        try:
            self.assertEqual(snapshot["remoteUpdate"], "local-only branch; no remote upstream configured")
            self.assertFalse(snapshot["checkoutUpdated"])
            self.assertEqual(git(local, "rev-parse", "HEAD"), original_head)
            self.assertEqual((Path(snapshot["worktreePath"]) / "tracked.txt").read_text(encoding="utf-8"), "local test\n")
        finally:
            source.cleanup_snapshot(local, snapshot["snapshotRoot"])

    def test_divergent_source_plan_discloses_local_merge_commit(self) -> None:
        git(self.repo, "checkout", "-b", "work")
        git(self.repo, "branch", "--set-upstream-to=origin/dev")
        (self.repo / "local.txt").write_text("local commit\n", encoding="utf-8")
        git(self.repo, "add", "local.txt")
        git(self.repo, "commit", "-m", "work branch change")
        writer = self.root / "writer"
        clone(self.bare, writer, "dev")
        (writer / "remote.txt").write_text("remote commit\n", encoding="utf-8")
        git(writer, "commit", "-am", "advance remote")
        git(writer, "push", "origin", "dev")

        plan = source.make_plan(self.repo, "personal", fetch=True)
        self.assertEqual(plan["mergeStrategy"], "merge-commit")
        snapshot = source.synchronize_and_snapshot(self.repo, plan, fetch=True)
        try:
            parents = git(self.repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
            self.assertEqual(len(parents), 3)
            self.assertEqual((Path(snapshot["worktreePath"]) / "local.txt").read_text(encoding="utf-8"), "local commit\n")
            self.assertEqual((Path(snapshot["worktreePath"]) / "remote.txt").read_text(encoding="utf-8"), "remote commit\n")
            self.assertEqual(snapshot["mergeStrategy"], "merge-commit")
            self.assertTrue(snapshot["checkoutUpdated"])
        finally:
            source.cleanup_snapshot(self.repo, snapshot["snapshotRoot"])

    def test_remote_change_after_plan_blocks_materialization(self) -> None:
        plan = source.make_plan(self.repo, "personal", fetch=True)
        writer = self.root / "writer"
        clone(self.bare, writer, "dev")
        (writer / "remote.txt").write_text("new remote tip\n", encoding="utf-8")
        git(writer, "commit", "-am", "advance after plan")
        git(writer, "push", "origin", "dev")
        original = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaisesRegex(source.SourceError, "Remote source SHA changed"):
            source.materialize_snapshot(self.repo, plan, fetch=True)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original)
        self.assertEqual((self.repo / "remote.txt").read_text(encoding="utf-8"), "remote-base\n")

    def test_local_work_change_after_plan_blocks_materialization(self) -> None:
        plan = source.make_plan(self.repo, "personal", fetch=True)
        (self.repo / "tracked.txt").write_text("changed after plan\n", encoding="utf-8")
        with self.assertRaisesRegex(source.SourceError, "changed after planning"):
            source.materialize_snapshot(self.repo, plan, fetch=True)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "changed after plan\n")

    def test_wip_edit_during_preflight_blocks_checkout_sync(self) -> None:
        (self.repo / ".gitignore").write_text(".env.local\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-m", "ignore local environment file")
        git(self.repo, "push", "origin", "dev")
        private_file = self.repo / ".env.local"
        private_file.write_text("TOKEN=before\n", encoding="utf-8")
        writer = self.root / "writer"
        clone(self.bare, writer, "dev")
        (writer / "remote.txt").write_text("latest remote\n", encoding="utf-8")
        git(writer, "commit", "-am", "advance remote")
        git(writer, "push", "origin", "dev")
        plan = source.make_plan(self.repo, "personal", fetch=True)
        original_head = git(self.repo, "rev-parse", "HEAD")
        real_materialize = source.materialize_snapshot

        def edit_after_preflight(*args, **kwargs):
            result = real_materialize(*args, **kwargs)
            (self.repo / "tracked.txt").write_text("edited during preflight\n", encoding="utf-8")
            private_file.write_text("TOKEN=changed during preflight\n", encoding="utf-8")
            return result

        with patch.object(source, "materialize_snapshot", side_effect=edit_after_preflight):
            with self.assertRaisesRegex(source.SourceError, "changed during preflight"):
                source.synchronize_and_snapshot(self.repo, plan, fetch=True)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original_head)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "edited during preflight\n")
        self.assertEqual(private_file.read_text(encoding="utf-8"), "TOKEN=changed during preflight\n")
        self.assertEqual((self.repo / "remote.txt").read_text(encoding="utf-8"), "remote-base\n")

    def test_wip_signature_detects_ignored_private_file_edits(self) -> None:
        (self.repo / ".gitignore").write_text(".env.local\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-m", "ignore local environment file")
        private_file = self.repo / ".env.local"
        private_file.write_text("TOKEN=before\n", encoding="utf-8")
        before = source._wip_signature(self.repo)
        private_file.write_text("TOKEN=after\n", encoding="utf-8")
        self.assertNotEqual(before, source._wip_signature(self.repo))

    def test_private_and_secret_local_files_never_enter_snapshot(self) -> None:
        (self.repo / "AGENTS.local.md").write_text("private preferences\n", encoding="utf-8")
        (self.repo / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.repo / "source.ts").write_text("safe source\n", encoding="utf-8")
        plan = source.make_plan(self.repo, "personal", fetch=False)
        self.assertEqual(plan["workingChangesPresent"], True)
        self.assertEqual(set(plan["excludedPrivatePaths"]), {".env.local", "AGENTS.local.md"})
        snapshot = source.materialize_snapshot(self.repo, plan, fetch=False)
        try:
            tree = Path(snapshot["worktreePath"])
            self.assertTrue((tree / "source.ts").is_file())
            self.assertFalse((tree / "AGENTS.local.md").exists())
            self.assertFalse((tree / ".env.local").exists())
        finally:
            source.cleanup_snapshot(self.repo, snapshot["snapshotRoot"])

    def test_accidentally_tracked_private_config_is_removed_from_snapshot(self) -> None:
        private_file = self.repo / "AGENTS.local.md"
        private_file.write_text("private preferences\n", encoding="utf-8")
        git(self.repo, "add", "AGENTS.local.md")
        git(self.repo, "commit", "-m", "synthetic tracked local config")
        git(self.repo, "push", "origin", "dev")
        plan = source.make_plan(self.repo, "personal", fetch=False)
        snapshot = source.materialize_snapshot(self.repo, plan, fetch=False)
        try:
            self.assertTrue(private_file.is_file())
            self.assertFalse((Path(snapshot["worktreePath"]) / "AGENTS.local.md").exists())
            self.assertIn("AGENTS.local.md", snapshot["excludedPrivatePaths"])
        finally:
            source.cleanup_snapshot(self.repo, snapshot["snapshotRoot"])


if __name__ == "__main__":
    unittest.main()
