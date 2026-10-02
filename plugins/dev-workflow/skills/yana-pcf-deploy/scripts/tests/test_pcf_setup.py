import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "pcf_setup.py"
spec = importlib.util.spec_from_file_location("pcf_setup", SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".git" / "info" / "exclude").write_text("AGENTS.local.md\n")
        self.state = Path(self.temp.name) / "state"
        self.runtimes = {name: sys.executable for name in setup.RUNTIMES["deploy"]}

    def test_update_preserves_unrelated_prose_bom_and_newlines(self):
        path = self.repo / "AGENTS.local.md"
        prefix = b"\xef\xbb\xbf# Personal\r\nKeep these instructions.\r\n"
        path.write_bytes(prefix)
        setup.save_config(self.repo, {"personal_variant": "Alex"}, True)
        self.assertTrue(path.read_bytes().startswith(prefix))
        setup.save_config(self.repo, {"default_control": "YanaQuickView"}, True)
        self.assertEqual(path.read_text(encoding="utf-8-sig").count(setup.BEGIN), 1)
        self.assertEqual(setup.load_config(self.repo)["personal_variant"], "Alex")

    def test_preview_leaves_no_file_or_receipt(self):
        config = setup.save_config(self.repo, {"personal_variant": "Alex"})
        self.assertEqual(config["personal_variant"], "Alex")
        self.assertFalse((self.repo / "AGENTS.local.md").exists())
        self.assertFalse(self.state.exists())

    def test_nonignored_or_tracked_preferences_rejected(self):
        (self.repo / ".git" / "info" / "exclude").write_text("")
        with self.assertRaises(setup.SetupError):
            setup.save_config(self.repo, {"personal_variant": "Alex"}, True)
        path = self.repo / "AGENTS.local.md"
        path.write_text("Private")
        subprocess.run(["git", "-C", str(self.repo), "add", "AGENTS.local.md"], check=True)
        (self.repo / ".git" / "info" / "exclude").write_text("AGENTS.local.md\n")
        with self.assertRaises(setup.SetupError):
            setup.save_config(self.repo, {"personal_variant": "Alex"}, True)

    def test_secret_fields_reserved_variants_and_credential_urls_rejected(self):
        for values in ({"token": "redacted"}, {"personal_variant": "RC"},
                       {"personal_variant": "../bad"},
                       {"deploy_environment_url": "https://user:pass@org.example"},
                       {"deploy_environment_url": "https://org.example?token=redacted"}):
            with self.subTest(values=list(values)), self.assertRaises(setup.SetupError):
                setup.validate(values)

    def test_malformed_block_preserved(self):
        path = self.repo / "AGENTS.local.md"
        path.write_text(setup.BEGIN + "\ninvalid")
        before = path.read_bytes()
        with self.assertRaises(setup.SetupError):
            setup.save_config(self.repo, {"personal_variant": "Alex"}, True)
        self.assertEqual(path.read_bytes(), before)

    def test_second_run_uses_cached_scope_without_probing(self):
        args = ["init", "--repo", str(self.repo), "--scope", "deploy", "--state-root", str(self.state),
                "--deploy-environment-url", setup.DEFAULT_ENV, "--personal-variant", "Alex", "--apply"]
        with patch.object(setup, "probe_runtimes", return_value=self.runtimes):
            self.assertEqual(setup.main(args), 0)
        with patch.object(setup, "probe_runtimes", side_effect=AssertionError("Do not probe twice")):
            result = setup.status(self.repo, "deploy", self.state)
            self.assertEqual(setup.main(args + ["--release-source", "RC/123-fix", "1.7.0"]), 0)
        self.assertEqual(result["status"], "CONFIGURED")
        self.assertEqual(setup.status(self.repo, "override", self.state)["status"], "NEEDS_SETUP")

    def test_environment_change_invalidates_only_deploy_receipt(self):
        setup.save_config(self.repo, {"deploy_environment_url": setup.DEFAULT_ENV}, True)
        path = setup.state_path(self.repo, self.state)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "scopes": {"deploy": {
            "config_fingerprint": setup.config_fingerprint(setup.load_config(self.repo), "deploy"),
            "runtimes": self.runtimes}}}))
        setup.save_config(self.repo, {"personal_variant": "Alex"}, True)
        self.assertEqual(setup.status(self.repo, "deploy", self.state)["status"], "CONFIGURED")
        setup.save_config(self.repo, {"deploy_environment_url": "https://sandbox.example"}, True)
        self.assertEqual(setup.status(self.repo, "deploy", self.state)["status"], "NEEDS_SETUP")

    def test_legacy_prose_is_not_treated_as_missing_human_preferences(self):
        (self.repo / "AGENTS.local.md").write_text("Use personal variant Alex.\n")
        self.assertTrue(setup.status(self.repo, "deploy", self.state)["legacy_preferences_present"])

    def test_no_write_when_prerequisites_fail(self):
        with patch.object(setup, "probe_runtimes", side_effect=setup.SetupError("Missing runtime")):
            code = setup.main(["init", "--repo", str(self.repo), "--scope", "deploy", "--apply",
                               "--deploy-environment-url", setup.DEFAULT_ENV, "--state-root", str(self.state)])
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / "AGENTS.local.md").exists())

    def test_corrupt_receipt_blocks_init_without_changing_preferences(self):
        path = setup.state_path(self.repo, self.state)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "scopes": {"deploy": "bad"}}))
        with patch.object(setup, "probe_runtimes", return_value=self.runtimes):
            code = setup.main(["init", "--repo", str(self.repo), "--scope", "deploy", "--apply",
                               "--deploy-environment-url", setup.DEFAULT_ENV, "--state-root", str(self.state)])
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / "AGENTS.local.md").exists())

    def test_incomplete_cached_runtime_receipt_is_not_configured(self):
        setup.save_config(self.repo, {"deploy_environment_url": setup.DEFAULT_ENV}, True)
        path = setup.state_path(self.repo, self.state)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "scopes": {"deploy": {
            "config_fingerprint": setup.config_fingerprint(setup.load_config(self.repo), "deploy"),
            "runtimes": {"python": sys.executable}}}}))
        self.assertEqual(setup.status(self.repo, "deploy", self.state)["status"], "NEEDS_SETUP")

    def test_override_status_does_not_request_personal_identity(self):
        result = setup.status(self.repo, "override", self.state)
        self.assertNotIn("personal_variant_missing", result)
        self.assertNotIn("personal_variant", result["missing_config"])

    def test_init_defaults_and_saved_preferences_win(self):
        args = ["init", "--repo", str(self.repo), "--scope", "deploy", "--apply", "--state-root", str(self.state)]
        with patch.object(setup, "probe_runtimes", return_value=self.runtimes):
            self.assertEqual(setup.main(args), 0)
        self.assertEqual(setup.load_config(self.repo)["deploy_environment_url"], setup.DEFAULT_ENV)
        self.assertEqual(setup.load_config(self.repo)["default_control"], "YanaGrid")
        setup.save_config(self.repo, {"default_control": "YanaQuickView", "deploy_environment_url": "https://sandbox.example"}, True)
        with patch.object(setup, "probe_runtimes", side_effect=AssertionError("Use cached runtimes")):
            self.assertEqual(setup.main(args), 0)
        self.assertEqual(setup.load_config(self.repo)["default_control"], "YanaQuickView")
        self.assertEqual(setup.load_config(self.repo)["deploy_environment_url"], "https://sandbox.example")

    def test_cross_scope_preferences_rejected_before_write(self):
        code = setup.main(["init", "--repo", str(self.repo), "--scope", "override", "--apply",
                           "--deploy-environment-url", setup.DEFAULT_ENV, "--state-root", str(self.state)])
        self.assertEqual(code, 2)
        self.assertFalse((self.repo / "AGENTS.local.md").exists())


if __name__ == "__main__":
    unittest.main()
