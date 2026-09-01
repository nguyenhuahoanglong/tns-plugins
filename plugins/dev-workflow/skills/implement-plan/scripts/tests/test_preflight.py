#!/usr/bin/env python3
"""Hermetic preflight probe tests: no real network, no real CLI."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "preflight.py"
SPEC = importlib.util.spec_from_file_location("preflight", SCRIPT)
PF = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PF  # dataclasses resolve annotations through sys.modules
SPEC.loader.exec_module(PF)


def probe(kind, target, pid="PF-1", blocks="Task 1"):
    return PF.Probe(pid, kind, target, blocks)


def ok_runner(*_args, **_kwargs):
    return {"returncode": 0, "stdout": "1.2.3", "stderr": ""}


def fail_runner(*_args, **_kwargs):
    return {"returncode": 1, "stdout": "", "stderr": "no profile for org"}


def timeout_runner(*_args, **_kwargs):
    return {"returncode": None, "stdout": "", "stderr": "timed out", "timeout": True}


def url_runner(status=200, error=None):
    def probe_url(_url, _timeout):
        return {"status": status} if error is None else {"status": None, "error": error}
    return probe_url


class TestPathProbes(unittest.TestCase):
    def test_existing_file_and_directory_are_ready(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "src").mkdir()
            (Path(root) / "src" / "cache.ts").write_text("x", encoding="utf-8")
            self.assertEqual(PF.probe_path("src/cache.ts", Path(root))[0], PF.READY)
            self.assertEqual(PF.probe_path("src", Path(root))[0], PF.READY)

    def test_new_file_with_existing_parent_is_ready(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "src").mkdir()
            state, detail = PF.probe_path("src/new.ts", Path(root))
            self.assertEqual(state, PF.READY)
            self.assertIn("parent folder exists", detail)

    def test_missing_parent_folder_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(PF.probe_path("nope/deeper/file.ts", Path(root))[0], PF.BLOCKED)


class TestCommandProbes(unittest.TestCase):
    def test_resolvable_command_reports_absolute_path(self):
        state, detail = PF.probe_command("python")
        self.assertEqual(state, PF.READY)
        self.assertTrue(Path(detail).is_absolute())

    def test_unresolvable_command_blocks(self):
        self.assertEqual(PF.probe_command("definitely-not-a-real-binary-xyz")[0], PF.BLOCKED)

    def test_version_argument_is_allowlisted(self):
        state, detail = PF.probe_command_version(probe("command-version", "python --serve"), ok_runner)
        self.assertEqual(state, PF.BLOCKED)
        self.assertIn("allowlisted", detail)

    def test_version_probe_uses_injected_runner(self):
        self.assertEqual(PF.probe_command_version(probe("command-version", "python --version"), ok_runner),
                         (PF.READY, "1.2.3"))

    def test_resolve_argv_returns_absolute_executable(self):
        self.assertTrue(Path(PF.resolve_argv(["python", "--version"])[0]).is_absolute())


class TestAuthProbes(unittest.TestCase):
    def test_keyed_lookup_only(self):
        self.assertEqual(PF.auth_argv("az-account"), ["az", "account", "show"])
        with self.assertRaises(PF.PlanError):
            PF.auth_argv("rm -rf /")
        with self.assertRaises(PF.PlanError):
            PF.auth_argv("az-account --subscription evil")

    def test_git_remote_requires_a_url_argument(self):
        self.assertEqual(PF.auth_argv("git-remote https://example.com/x.git")[-1], "https://example.com/x.git")
        with self.assertRaises(PF.PlanError):
            PF.auth_argv("git-remote ; whoami")

    def test_ado_pat_probe_takes_no_argument(self):
        self.assertIn("auth", PF.auth_argv("ado-pat"))
        with self.assertRaises(PF.PlanError):
            PF.auth_argv("ado-pat extra")

    def test_failure_blocks_with_reason(self):
        state, detail = PF.probe_auth(probe("auth", "pac-org"), fail_runner)
        self.assertEqual(state, PF.BLOCKED)
        self.assertIn("no profile", detail)

    def test_timeout_is_the_interactive_prompt_signature(self):
        state, detail = PF.probe_auth(probe("auth", "az-account"), timeout_runner)
        self.assertEqual(state, PF.BLOCKED)
        self.assertIn("interactive-prompt signature", detail)

    def test_unknown_key_surfaces_as_blocked_not_a_crash(self):
        result = PF.run_probe(probe("auth", "made-up-key"), Path("."), fail_runner, url_runner())
        self.assertEqual(result.state, PF.BLOCKED)
        self.assertIn("unknown auth key", result.detail)


class TestUrlProbe(unittest.TestCase):
    def test_success_is_ready(self):
        self.assertEqual(PF.probe_url("https://example.com", url_runner(200))[0], PF.READY)

    def test_unauthorized_is_ready_because_the_service_is_up(self):
        for status in (401, 403):
            self.assertEqual(PF.probe_url("https://example.com", url_runner(status))[0], PF.READY)

    def test_server_error_blocks(self):
        self.assertEqual(PF.probe_url("https://example.com", url_runner(503))[0], PF.BLOCKED)

    def test_transport_failure_blocks(self):
        self.assertEqual(PF.probe_url("https://x", url_runner(error="dns failure"))[0], PF.BLOCKED)

    def test_non_http_target_blocks(self):
        self.assertEqual(PF.probe_url("ftp://example.com", url_runner(200))[0], PF.BLOCKED)


class TestDependencyProbes(unittest.TestCase):
    def _package(self, root, deps, installed):
        manifest = Path(root) / "package.json"
        manifest.write_text(json.dumps({"devDependencies": {name: "1.0.0" for name in deps}}), encoding="utf-8")
        modules = Path(root) / "node_modules"
        modules.mkdir()
        for name in installed:
            (modules / name).mkdir()
        return manifest

    def test_missing_dev_dependencies_demand_npm_ci(self):
        with tempfile.TemporaryDirectory() as root:
            self._package(root, ["vitest", "eslint"], ["eslint"])
            state, detail = PF.probe_node_deps("package.json", Path(root))
            self.assertEqual(state, PF.BLOCKED)
            self.assertIn("npm ci", detail)
            self.assertIn("vitest", detail)

    def test_complete_install_is_ready(self):
        with tempfile.TemporaryDirectory() as root:
            self._package(root, ["vitest"], ["vitest"])
            self.assertEqual(PF.probe_node_deps("package.json", Path(root))[0], PF.READY)

    def test_absent_node_modules_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "package.json").write_text('{"dependencies":{"react":"18"}}', encoding="utf-8")
            self.assertEqual(PF.probe_node_deps("package.json", Path(root))[0], PF.BLOCKED)

    def test_restore_output_must_exist_and_be_current(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "app.csproj"
            project.write_text("<Project/>", encoding="utf-8")
            self.assertEqual(PF.probe_dotnet_restore("app.csproj", Path(root))[0], PF.BLOCKED)
            (Path(root) / "obj").mkdir()
            (Path(root) / "obj" / "project.assets.json").write_text("{}", encoding="utf-8")
            self.assertEqual(PF.probe_dotnet_restore("app.csproj", Path(root))[0], PF.READY)


class TestEnvAndManual(unittest.TestCase):
    def test_env_reports_presence_only(self):
        os.environ["IMPLEMENT_PLAN_TEST_VAR"] = "value"
        try:
            state, detail = PF.probe_env("IMPLEMENT_PLAN_TEST_VAR")
            self.assertEqual(state, PF.READY)
            self.assertNotIn("value", detail)
        finally:
            del os.environ["IMPLEMENT_PLAN_TEST_VAR"]
        self.assertEqual(PF.probe_env("IMPLEMENT_PLAN_TEST_VAR")[0], PF.BLOCKED)

    def test_manual_probe_is_never_executed(self):
        def exploding_runner(*_args, **_kwargs):
            raise AssertionError("manual probes must not execute anything")
        result = PF.run_probe(probe("manual", "Dataverse MCP list-tables"), Path("."), exploding_runner, None)
        self.assertEqual(result.state, PF.UNVERIFIABLE)


class TestRedaction(unittest.TestCase):
    def test_bearer_jwt_and_access_token_are_redacted(self):
        text = ('Bearer abc.def.ghi eyJhbGciOiJIUzI1NiJ9padpadpadpadpadpad '
                '{"access_token": "s3cr3t-value"}')
        redacted = PF.redact(text)
        self.assertNotIn("abc.def.ghi", redacted)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", redacted)
        self.assertNotIn("s3cr3t-value", redacted)

    def test_secret_env_values_are_redacted(self):
        os.environ["IMPLEMENT_PLAN_TEST_PAT"] = "pat-value-1234"
        try:
            self.assertNotIn("pat-value-1234", PF.clip("failed with pat-value-1234"))
        finally:
            del os.environ["IMPLEMENT_PLAN_TEST_PAT"]

    def test_output_is_capped(self):
        self.assertLessEqual(len(PF.clip("x" * 5000)), PF.OUTPUT_CAP + 3)


PLAN = """# Plan: Fixture

## Preflight

| ID | Kind | Target | Expect | Blocks |
|---|---|---|---|---|
| PF-1 | command | `python` | resolves on PATH | Task 1 |
| PF-2 | manual | MCP list-tables | returns rows | Task 1 |

## Tasks

### Task 1: Fixture task
- Status: pending
- Files: `src/cache.ts`, `src/index.ts`
- Mode: existing-method
"""


class TestPlanParsing(unittest.TestCase):
    def test_declared_and_derived_probes_are_collected(self):
        declared = PF.declared_probes(PLAN)
        derived = PF.derived_probes(PLAN)
        self.assertEqual([p.pid for p in declared], ["PF-1", "PF-2"])
        self.assertEqual([p.target for p in derived], ["src/cache.ts", "src/index.ts"])
        self.assertTrue(all(p.blocks == "Task 1" for p in derived))

    def test_unknown_kind_and_bad_arity_are_plan_errors(self):
        with self.assertRaises(PF.PlanError):
            PF.declared_probes(PLAN.replace("| PF-1 | command |", "| PF-1 | sudo |"))
        with self.assertRaises(PF.PlanError):
            PF.declared_probes(PLAN.replace("| resolves on PATH | Task 1 |", "| Task 1 |"))

    def test_aggregation_rule(self):
        def result(state):
            return PF.ProbeResult(probe("path", "x"), state, "")
        self.assertEqual(PF.autonomy([result(PF.READY)]), "verified-ready")
        self.assertEqual(PF.autonomy([result(PF.READY), result(PF.UNVERIFIABLE)]),
                         "unverifiable-with-fallback")
        self.assertEqual(PF.autonomy([result(PF.BLOCKED), result(PF.UNVERIFIABLE)]), "verified-blocked")

    def test_run_uses_injected_probes_end_to_end(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "src").mkdir()
            results = PF.run(PLAN, Path(root), runner=ok_runner, url_probe=url_runner())
            states = {r.probe.pid: r.state for r in results}
            self.assertEqual(states["PF-1"], PF.READY)
            self.assertEqual(states["PF-2"], PF.UNVERIFIABLE)
            self.assertEqual(PF.autonomy(results), "unverifiable-with-fallback")

    def test_markdown_render_is_paste_ready(self):
        results = PF.run(PLAN, Path("."), runner=ok_runner, url_probe=url_runner())
        rendered = PF.render_markdown(results, "2026-09-01T00:00:00Z")
        self.assertIn("### Preflight results", rendered)
        self.assertIn("Run: 2026-09-01T00:00:00Z", rendered)
        self.assertIn("Autonomy: ", rendered)


class TestCli(unittest.TestCase):
    def _write(self, root, text):
        path = Path(root) / "plan.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_missing_plan_is_usage_error(self):
        self.assertEqual(PF.main(["no-such-plan.md"]), 2)

    def test_malformed_preflight_is_usage_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, PLAN.replace("| PF-1 | command |", "| PF-1 | sudo |"))
            self.assertEqual(PF.main([str(path), "--repo-root", root]), 2)

    def test_blocked_probe_exits_one(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, PLAN.replace("`python`", "`definitely-not-a-real-binary-xyz`"))
            self.assertEqual(PF.main([str(path), "--repo-root", root]), 1)

    def test_clean_plan_exits_zero(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "src").mkdir()
            path = self._write(root, PLAN.replace("| PF-2 | manual | MCP list-tables | returns rows | Task 1 |\n", ""))
            self.assertEqual(PF.main([str(path), "--repo-root", root, "--format", "json"]), 0)


if __name__ == "__main__":
    unittest.main()
