#!/usr/bin/env python3
"""CLI/build boundary tests; no Chrome, Dataverse, or real build needed."""
from __future__ import annotations

import contextlib
import copy
import argparse
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yana_grid_debug_override as subject


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        targets = set(subject.STAMP_TARGETS)
        for control in subject.CONTROL_SPECS:
            required, optional = subject.stamp_targets(control)
            targets.update(required)
            targets.update(optional)
        targets.add(subject.PCF_NODE_RELATIVE)
        for relative in targets:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unchanged", encoding="utf-8")
        (self.root / subject.GRID_WORKSPACE / subject.GRID_SPEC["manifest"]).write_text(
            '<manifest><control namespace="Technosoft.DMS.XRM.CustomControl.Grid" constructor="YanaGrid" /></manifest>',
            encoding="utf-8",
        )
        quickview = subject.CONTROL_SPECS["YanaQuickView"]
        (self.root / quickview["workspace"] / quickview["manifest"]).write_text(
            '<manifest><control namespace="Technosoft.DMS.XRM.CustomControl.QuickView" constructor="YanaQuickView" /></manifest>',
            encoding="utf-8",
        )
        profile = self.root / "profile"
        overrides = self.root / "overrides"
        profile.mkdir()
        overrides.mkdir()
        self.setup = {
            "browser_profile": str(profile),
            "overrides_directory": str(overrides),
            "default_control": "YanaGrid",
        }
        self.paths = {
            "root": self.root / "state",
            "config": self.root / "state" / "config.json",
            "profile": profile,
            "overrides": overrides,
        }
        self.grid_identity = {
            "namespace": "Technosoft.DMS.XRM.CustomControl.Grid",
            "constructor": "YanaGrid",
            "control_type": "",
            "control_directory": "cc_Technosoft.DMS.XRM.CustomControl.Grid.YanaGrid",
        }

    def run_cli(self, arguments):
        with patch.object(subject, "load_setup_config", return_value=self.setup), \
             patch.object(subject, "state_paths", return_value=self.paths), \
             contextlib.redirect_stdout(io.StringIO()):
            return subject.main(arguments)

    def test_origin_normalization_and_credentials_rejection(self):
        self.assertEqual(subject.parse_page_url("https://EXAMPLE.test/main.aspx")[1], "https://example.test")
        for url in ("http://example.test", "https://user:secret@example.test"):
            with self.subTest(url=url), self.assertRaises(subject.SkillError):
                subject.parse_page_url(url)

    def test_missing_profile_paths_never_default_to_current_directory(self):
        paths = subject.state_paths({})
        self.assertIsNone(paths["profile"])
        self.assertIsNone(paths["overrides"])
        with patch.object(subject, "load_setup_config", return_value={"default_control": "YanaGrid"}), \
             self.assertRaisesRegex(subject.SkillError, "OVERRIDE_SETUP_REQUIRED"):
            subject._require_override_setup(self.root)

    def test_setup_requires_absolute_existing_profile_and_overrides_paths(self):
        for config in (
            {"browser_profile": "relative/profile", "overrides_directory": str(self.paths["overrides"])},
            {"browser_profile": str(self.paths["profile"]), "overrides_directory": "relative/overrides"},
        ):
            with self.subTest(config=config), patch.object(subject, "load_setup_config", return_value=config), \
                 self.assertRaisesRegex(subject.SkillError, "absolute path"):
                subject._require_override_setup(self.root)

    def test_mapping_outside_configured_overrides_is_rejected_before_source_refresh_or_build(self):
        outside = self.root / "outside" / "bundle.js"
        outside.parent.mkdir()
        outside.write_bytes(b"old bytes")
        mapping_path = self.root / "map.json"
        mapping_path.write_text(json.dumps({
            "schema_version": 2,
            "origin": "https://example.test",
            "resources": [{
                "artifact": "bundle.js",
                "url": "https://example.test/webresources/cc_Technosoft.DMS.XRM.CustomControl.Grid.YanaGrid/bundle.js?token=observed",
                "override_file": str(outside),
            }],
        }), encoding="utf-8")
        args = subject.parse_args([
            "--mode", "plan", "--repo-root", str(self.root), "--page-url", "https://example.test/main.aspx",
            "--resource-map", str(mapping_path),
        ])
        with patch.object(subject, "load_setup_config", return_value=self.setup), \
             patch.object(subject, "state_paths", return_value=self.paths), \
             patch.object(subject, "prepare_output") as prepare_output, \
             self.assertRaisesRegex(subject.SkillError, "must stay inside"):
            subject.resource_workflow(args)
        prepare_output.assert_not_called()
        self.assertEqual(outside.read_bytes(), b"old bytes")

    def test_store_python_stops_before_reading_or_writing_override_state(self):
        with patch.object(subject, "ensure_native_filesystem_runtime", side_effect=subject.ResourceSetError("WINDOWS_STORE_PYTHON")), patch.object(subject, "resource_workflow") as workflow:
            self.assertEqual(self.run_cli(["--mode", "run", "--page-url", "https://example.test"]), 1)
        workflow.assert_not_called()
        self.assertFalse(self.paths["root"].exists())

    def test_build_dry_run_has_no_side_effects(self):
        before = subject.snapshot_source(self.root)
        with patch.object(subject.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            result = subject.build_bundle(self.root, True)
        run.assert_not_called()
        self.assertFalse(result.parent.exists())
        self.assertEqual(before, subject.snapshot_source(self.root))

    def test_build_rejects_outside_clean_target(self):
        (self.root / subject.GRID_WORKSPACE / "pcfconfig.json").write_text('{"outDir":"../../outside"}')
        with patch.object(subject.subprocess, "run") as run, self.assertRaises(subject.SkillError):
            subject.build_bundle(self.root, False)
        run.assert_not_called()

    def test_clean_build_uses_direct_node_and_explicit_mode(self):
        bundle = self.root / subject.BUNDLE_RELATIVE
        def run(command, **kwargs):
            self.assertNotIn("shell", kwargs)
            if command[2] == "build":
                bundle.parent.mkdir(parents=True)
                bundle.write_bytes(b"bundle")
            return Mock(returncode=0)
        with patch.object(subject.subprocess, "run", side_effect=run) as process:
            self.assertEqual(subject.build_bundle(self.root, False, "development"), bundle)
        self.assertEqual([c.args[0][2:] for c in process.call_args_list], [["clean"], ["build", "--buildMode", "development"]])
        self.assertTrue(all(c.args[0][0] == "node" for c in process.call_args_list))

    def test_quickview_build_targets_its_own_workspace_and_output(self):
        spec = subject.CONTROL_SPECS["YanaQuickView"]
        expected = self.root / spec["workspace"] / "out" / "controls" / "YanaQuickView" / "bundle.js"
        def run(command, **kwargs):
            if command[2] == "build":
                expected.parent.mkdir(parents=True, exist_ok=True)
                expected.write_bytes(b"quickview")
            return Mock(returncode=0)
        with patch.object(subject.subprocess, "run", side_effect=run) as process:
            self.assertEqual(subject.build_bundle(self.root, False, "production", "YanaQuickView"), expected)
        self.assertTrue(all(call.kwargs["cwd"] == self.root / spec["workspace"] for call in process.call_args_list))

    def test_failed_build_still_detects_identity_mutation(self):
        def run(*args, **kwargs):
            (self.root / subject.STAMP_TARGETS[0]).write_text("mutated")
            return Mock(returncode=1)
        with patch.object(subject.subprocess, "run", side_effect=run), self.assertRaisesRegex(subject.SkillError, "changed tracked source"):
            subject.build_bundle(self.root, False)

    def test_existing_sdk_and_legacy_solution_identity_files_are_guarded(self):
        for relative in subject.OPTIONAL_STAMP_TARGETS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original")
        before = subject.snapshot_source(self.root)
        self.assertTrue(all(path in before for path in subject.OPTIONAL_STAMP_TARGETS))
        (self.root / subject.OPTIONAL_STAMP_TARGETS[0]).write_text("changed version")
        with self.assertRaisesRegex(subject.SkillError, "sdkVersion"):
            subject.assert_source_unchanged(self.root, before)

    def test_legacy_mapping_fails_without_config_mutation(self):
        self.paths["root"].mkdir()
        original = '{"version":1,"mappings":{"https://example.test":{"override_file":"bundle.js"}}}'
        self.paths["config"].write_text(original)
        self.assertEqual(self.run_cli(["--mode", "run", "--page-url", "https://example.test/main.aspx"]), 1)
        self.assertEqual(self.paths["config"].read_text(), original)

    def test_setup_dry_run_does_not_apply_or_write_report(self):
        mapping = self.root / "map.json"
        mapping.write_text('{"schema_version":2}')
        report = self.root / "report.json"
        with patch.object(subject, "source_identity", return_value=self.grid_identity), \
             patch.object(subject, "normalize_mapping", return_value=(json.loads(mapping.read_text()), self.grid_identity)), \
             patch.object(subject, "prepare_output", return_value=(self.root, {"mode": "EXISTING_ARTIFACT"})), \
             patch.object(subject, "validate_mapping_destinations"), \
             patch.object(subject, "inspect_build", return_value={"identity": self.grid_identity}), \
             patch.object(subject, "make_plan", return_value={"status": "READY"}), \
             patch.object(subject, "apply_plan") as apply:
            result = self.run_cli(["--mode", "setup", "--page-url", "https://example.test/main.aspx", "--resource-map", str(mapping),
                                   "--artifact-dir", str(self.root), "--report", str(report), "--dry-run"])
        self.assertEqual(result, 0)
        apply.assert_not_called()
        self.assertFalse(report.exists())
        self.assertFalse(self.paths["root"].exists())

    def test_blocked_apply_does_not_write_config(self):
        mapping = self.root / "map.json"
        mapping.write_text('{"schema_version":2}')
        with patch.object(subject, "source_identity", return_value=self.grid_identity), \
             patch.object(subject, "normalize_mapping", return_value=(json.loads(mapping.read_text()), self.grid_identity)), \
             patch.object(subject, "prepare_output", return_value=(self.root, {"mode": "EXISTING_ARTIFACT"})), \
             patch.object(subject, "validate_mapping_destinations"), \
             patch.object(subject, "inspect_build", return_value={"identity": self.grid_identity}), \
             patch.object(subject, "make_plan", return_value={}), \
             patch.object(subject, "apply_plan", return_value={"status": "BLOCKED"}):
            result = self.run_cli(["--mode", "setup", "--page-url", "https://example.test/main.aspx", "--resource-map", str(mapping), "--artifact-dir", str(self.root)])
        self.assertEqual(result, 1)
        self.assertFalse(self.paths["root"].exists())

    def test_partial_runtime_verification_returns_failure(self):
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps({"plan": {}, "applied_at": "2026-09-29T00:00:00Z"}))
        evidence = self.root / "evidence.json"
        evidence.write_text("{}")
        with patch.object(subject, "verify_runtime", return_value={"status": "ASSETS_VERIFIED_NOT_DEPLOY_PARITY"}):
            self.assertEqual(self.run_cli(["--mode", "verify", "--receipt", str(receipt), "--runtime-evidence", str(evidence)]), 1)

    def test_asset_scope_verification_accepts_only_saved_scope(self):
        receipt = self.root / "receipt.json"
        evidence = self.root / "evidence.json"
        evidence.write_text("{}")
        for scope, expected in (("client-assets", 0), ("client-parity", 1)):
            receipt.write_text(json.dumps({"plan": {"verification_scope": scope}, "applied_at": "2026-09-29T00:00:00Z"}))
            with self.subTest(scope=scope), patch.object(subject, "verify_runtime", return_value={"status": "ASSETS_VERIFIED_NOT_DEPLOY_PARITY"}):
                self.assertEqual(self.run_cli(["--mode", "verify", "--receipt", str(receipt), "--runtime-evidence", str(evidence)]), expected)

    def test_setup_passes_default_or_explicit_scope_to_transaction(self):
        mapping = self.root / "map.json"
        mapping.write_text('{"schema_version":2}')
        for extra, expected in (([], "client-assets"), (["--verification-scope", "client-parity"], "client-parity")):
            with self.subTest(scope=expected), \
                 patch.object(subject, "source_identity", return_value=self.grid_identity), \
                 patch.object(subject, "normalize_mapping", return_value=(json.loads(mapping.read_text()), self.grid_identity)), \
                 patch.object(subject, "prepare_output", return_value=(self.root, {"mode": "EXISTING_ARTIFACT"})), \
                 patch.object(subject, "validate_mapping_destinations"), \
                 patch.object(subject, "inspect_build", return_value={"identity": self.grid_identity}), \
                 patch.object(subject, "make_plan", return_value={}), \
                 patch.object(subject, "apply_plan", return_value={"status": "BLOCKED"}) as apply:
                self.run_cli(["--mode", "setup", "--page-url", "https://example.test", "--resource-map", str(mapping), "--artifact-dir", str(self.root), *extra])
                self.assertEqual(apply.call_args.kwargs["verification_scope"], expected)

    def test_mapping_key_separates_repo_profile_control_and_variant(self):
        base = subject.mapping_scope(self.root, self.paths["profile"], "https://example.test", "YanaGrid", self.grid_identity)
        grid_key = subject.mapping_key(base)
        variants = dict(base, deployed_identity=base["deployed_identity"] + ".Long")
        quickview = dict(base, control="YanaQuickView")
        other_profile = dict(base, profile=subject.canonical_path(self.root / "other-profile"))
        other_repo = dict(base, repo=subject.canonical_path(self.root / "other-repo"))
        self.assertEqual(len({grid_key, subject.mapping_key(variants), subject.mapping_key(quickview),
                              subject.mapping_key(other_profile), subject.mapping_key(other_repo)}), 5)

    def test_untracked_symlink_is_not_read_when_fingerprinting_checkout(self):
        outside = self.root / "outside.ts"
        outside.write_text("external bytes", encoding="utf-8")
        link = self.root / "linked.ts"
        link.symlink_to(outside)

        def list_git(_repo, *arguments, **_kwargs):
            if arguments == ("diff", "--binary", "HEAD"):
                return ""
            if arguments == ("ls-files", "--others", "--exclude-standard", "-z"):
                return "linked.ts\x00"
            self.fail(f"Unexpected Git command: {arguments}")

        with patch.object(subject, "git_text", side_effect=list_git), \
             self.assertRaisesRegex(subject.SkillError, "Untracked symlink"):
            subject.worktree_fingerprint(self.root)

    def test_legacy_grid_map_requires_confirmation_and_copies_to_current_scope(self):
        origin = "https://example.test"
        old = {
            "schema_version": 2,
            "origin": origin,
            "resources": [{
                "artifact": "bundle.js",
                "url": origin + "/v1/webresources/cc_Technosoft.DMS.XRM.CustomControl.Grid.YanaGrid/bundle.js",
                "override_file": str(self.paths["overrides"] / "bundle.js"),
            }],
        }
        config = {"mappings": {origin: copy.deepcopy(old)}}
        args = argparse.Namespace(migrate_legacy_grid_map=False)
        with self.assertRaisesRegex(subject.SkillError, "LEGACY_GRID_MAP_REBIND_REQUIRED"):
            subject._legacy_mapping_for_scope(args, config, origin, "YanaGrid", self.grid_identity,
                                              self.paths, self.root, None)
        args.migrate_legacy_grid_map = True
        mapping, key, scope, migrated, legacy_origin = subject._legacy_mapping_for_scope(
            args, config, origin, "YanaGrid", self.grid_identity, self.paths, self.root, None,
        )
        self.assertTrue(migrated)
        self.assertEqual(key, subject.mapping_key(scope))
        self.assertEqual(legacy_origin, origin)
        self.assertEqual(config["mappings"][origin], old)
        self.assertEqual(mapping["_scope"], scope)

    def test_legacy_grid_map_never_migrates_to_quickview_or_another_scope(self):
        origin = "https://example.test"
        config = {"mappings": {origin: {"schema_version": 2, "origin": origin, "resources": []}}}
        args = argparse.Namespace(migrate_legacy_grid_map=True)
        quick = subject.control_identity(
            '<manifest><control namespace="Technosoft.DMS.XRM.CustomControl.QuickView" constructor="YanaQuickView" /></manifest>'
        )
        with self.assertRaisesRegex(subject.SkillError, "LEGACY_GRID_MAP_ONLY"):
            subject._legacy_mapping_for_scope(args, config, origin, "YanaQuickView", quick,
                                              self.paths, self.root, None)

    def test_dirty_and_unpushed_source_skip_fetch(self):
        def fake_git(repo, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return Mock(returncode=0, stdout=str(repo))
            if args == ("status", "--porcelain", "--untracked-files=all"):
                return Mock(returncode=0, stdout="?? scratch.ts\n")
            if args == ("rev-parse", "--verify", "HEAD^{commit}"):
                return Mock(returncode=0, stdout="head-a")
            if args == ("symbolic-ref", "--quiet", "--short", "HEAD"):
                return Mock(returncode=0, stdout="US/1-work")
            self.fail(f"Unexpected Git command: {args}")
        with patch.object(subject, "run_git", side_effect=fake_git) as git:
            result = subject.prepare_override_source(self.root)
        self.assertEqual(result["mode"], "LOCAL_WORKTREE")
        self.assertTrue(result["local_changes_included"])
        self.assertFalse(any("fetch" in call.args[1] for call in git.call_args_list))

        def ahead_git(repo, *args):
            mapping = {
                ("rev-parse", "--show-toplevel"): str(repo),
                ("status", "--porcelain", "--untracked-files=all"): "",
                ("rev-parse", "--verify", "HEAD^{commit}"): "head-a",
                ("symbolic-ref", "--quiet", "--short", "HEAD"): "US/1-work",
                ("rev-parse", "--symbolic-full-name", "@{u}"): "refs/remotes/origin/US/1-work",
                ("config", "--get", "branch.US/1-work.remote"): "origin",
                ("config", "--get", "branch.US/1-work.merge"): "refs/heads/US/1-work",
                ("rev-list", "--left-right", "--count", "head-a...refs/remotes/origin/US/1-work"): "1 0",
            }
            if args not in mapping:
                self.fail(f"Unexpected Git command: {args}")
            return Mock(returncode=0, stdout=mapping[args])
        with patch.object(subject, "run_git", side_effect=ahead_git) as git:
            result = subject.prepare_override_source(self.root)
        self.assertEqual(result["mode"], "LOCAL_COMMITS")
        self.assertFalse(any(call.args[1] == "fetch" for call in git.call_args_list))

    def test_clean_latest_source_fetches_then_fast_forwards_only(self):
        state = {"head": "head-a", "status": "", "calls": []}
        def fake_git(repo, *args):
            state["calls"].append(args)
            mapping = {
                ("rev-parse", "--show-toplevel"): str(repo),
                ("status", "--porcelain", "--untracked-files=all"): state["status"],
                ("rev-parse", "--verify", "HEAD^{commit}"): state["head"],
                ("symbolic-ref", "--quiet", "--short", "HEAD"): "dev",
                ("rev-parse", "--symbolic-full-name", "@{u}"): "refs/remotes/origin/dev",
                ("config", "--get", "branch.dev.remote"): "origin",
                ("config", "--get", "branch.dev.merge"): "refs/heads/dev",
                ("rev-list", "--left-right", "--count", "head-a...refs/remotes/origin/dev"): "0 0",
                ("rev-parse", "--verify", "refs/remotes/origin/dev^{commit}"): "head-b",
            }
            if args == ("merge-base", "--is-ancestor", "head-a", "refs/remotes/origin/dev"):
                return Mock(returncode=0, stdout="")
            if args == ("fetch", "--no-tags", "origin", "+refs/heads/dev:refs/remotes/origin/dev"):
                return Mock(returncode=0, stdout="")
            if args == ("merge", "--ff-only", "refs/remotes/origin/dev"):
                state["head"] = "head-b"
                return Mock(returncode=0, stdout="")
            if args not in mapping:
                self.fail(f"Unexpected Git command: {args}")
            return Mock(returncode=0, stdout=mapping[args])
        with patch.object(subject, "run_git", side_effect=fake_git):
            result = subject.prepare_override_source(self.root)
        self.assertEqual(result["mode"], "FAST_FORWARD")
        self.assertEqual(result["head_sha"], "head-b")
        self.assertIn(("merge", "--ff-only", "refs/remotes/origin/dev"), state["calls"])

    def test_dry_run_never_fetches_even_for_clean_branch(self):
        def fake_git(repo, *args):
            mapping = {
                ("rev-parse", "--show-toplevel"): str(repo),
                ("status", "--porcelain", "--untracked-files=all"): "",
                ("rev-parse", "--verify", "HEAD^{commit}"): "head-a",
                ("symbolic-ref", "--quiet", "--short", "HEAD"): "dev",
                ("rev-parse", "--symbolic-full-name", "@{u}"): "refs/remotes/origin/dev",
                ("config", "--get", "branch.dev.remote"): "origin",
                ("config", "--get", "branch.dev.merge"): "refs/heads/dev",
                ("rev-list", "--left-right", "--count", "head-a...refs/remotes/origin/dev"): "0 0",
            }
            if args not in mapping:
                self.fail(f"Unexpected Git command: {args}")
            return Mock(returncode=0, stdout=mapping[args])
        with patch.object(subject, "run_git", side_effect=fake_git) as git:
            result = subject.prepare_override_source(self.root, dry_run=True)
        self.assertEqual(result["mode"], "WOULD_FETCH_AND_FAST_FORWARD")
        self.assertFalse(any(call.args[1] in {"fetch", "merge"} for call in git.call_args_list))


if __name__ == "__main__":
    unittest.main()
