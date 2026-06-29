"""Tests for the merge-preview and pr-required subcommands added to ado_work_item.py.

No live az login required — all az calls are intercepted via the `runner`
parameter or by patching shutil.which / the module-level `run` function.
"""
import importlib.util
import argparse
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "ado_work_item.py"
SPEC = importlib.util.spec_from_file_location("ado_work_item", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PR = {
    "pullRequestId": 42,
    "sourceRefName": "refs/heads/feature/my-branch",
    "targetRefName": "refs/heads/main",
    "mergeStatus": "succeeded",
    "lastMergeCommit": {"commitId": "aaa111"},
    "lastMergeSourceCommit": {"commitId": "bbb222"},
    "lastMergeTargetCommit": {"commitId": "ccc333"},
}

SAMPLE_PR_NO_COMMITS = {
    "pullRequestId": 99,
    "sourceRefName": "refs/heads/feature/other",
    "targetRefName": "refs/heads/main",
    "mergeStatus": "notSet",
}


# ---------------------------------------------------------------------------
# _extract_merge_preview — pure logic, no az
# ---------------------------------------------------------------------------

class ExtractMergePreviewTests(unittest.TestCase):

    def test_mergeRef_derivation(self):
        result = MOD._extract_merge_preview(42, SAMPLE_PR)
        self.assertEqual("refs/pull/42/merge", result["mergeRef"])

    def test_mergeRef_uses_supplied_pr_id(self):
        result = MOD._extract_merge_preview(100, SAMPLE_PR)
        self.assertEqual("refs/pull/100/merge", result["mergeRef"])

    def test_all_required_fields_present(self):
        result = MOD._extract_merge_preview(42, SAMPLE_PR)
        expected_keys = {
            "prId", "sourceRefName", "targetRefName",
            "lastMergeCommit", "lastMergeSourceCommit",
            "lastMergeTargetCommit", "mergeStatus", "mergeRef",
        }
        self.assertEqual(expected_keys, set(result.keys()))

    def test_commit_fields_populated(self):
        result = MOD._extract_merge_preview(42, SAMPLE_PR)
        self.assertEqual("aaa111", result["lastMergeCommit"])
        self.assertEqual("bbb222", result["lastMergeSourceCommit"])
        self.assertEqual("ccc333", result["lastMergeTargetCommit"])

    def test_missing_commit_fields_are_none(self):
        result = MOD._extract_merge_preview(99, SAMPLE_PR_NO_COMMITS)
        self.assertIsNone(result["lastMergeCommit"])
        self.assertIsNone(result["lastMergeSourceCommit"])
        self.assertIsNone(result["lastMergeTargetCommit"])

    def test_source_and_target_refs(self):
        result = MOD._extract_merge_preview(42, SAMPLE_PR)
        self.assertEqual("refs/heads/feature/my-branch", result["sourceRefName"])
        self.assertEqual("refs/heads/main", result["targetRefName"])
        self.assertEqual("succeeded", result["mergeStatus"])


# ---------------------------------------------------------------------------
# _fetch_pr — mock run() to avoid any network call
# ---------------------------------------------------------------------------

def _make_runner(rc, payload):
    """Return a fake run() that emits payload as JSON (or empty on failure)."""
    def runner(cmd, cwd=None):
        if rc == 0:
            return 0, json.dumps(payload), ""
        return rc, "", "pull request does not exist"
    return runner


class FetchPrTests(unittest.TestCase):

    def test_returns_dict_on_success(self):
        with mock.patch.object(MOD, "run", _make_runner(0, SAMPLE_PR)):
            result = MOD._fetch_pr("az", "https://dev.azure.com/Org", 42)
        self.assertEqual(SAMPLE_PR, result)

    def test_returns_none_when_not_found(self):
        with mock.patch.object(MOD, "run", _make_runner(1, {})):
            result = MOD._fetch_pr("az", "https://dev.azure.com/Org", 999)
        self.assertIsNone(result)

    def test_returns_none_for_empty_dict_response(self):
        # Some az versions return exit 0 with {} for missing PRs.
        with mock.patch.object(MOD, "run", _make_runner(0, {})):
            result = MOD._fetch_pr("az", "https://dev.azure.com/Org", 999)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Argument parsing — merge-preview
# ---------------------------------------------------------------------------

class MergePreviewArgParseTests(unittest.TestCase):

    def _parse(self, argv):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        p = sub.add_parser("merge-preview")
        p.add_argument("--pr", type=int, required=True)
        p.add_argument("--repo", default=".")
        p.add_argument("--json", action="store_true")
        return parser.parse_args(argv)

    def test_pr_required(self):
        with self.assertRaises(SystemExit):
            self._parse(["merge-preview"])

    def test_pr_parsed(self):
        args = self._parse(["merge-preview", "--pr", "42"])
        self.assertEqual(42, args.pr)

    def test_json_flag_default_false(self):
        args = self._parse(["merge-preview", "--pr", "42"])
        self.assertFalse(args.json)

    def test_json_flag_true(self):
        args = self._parse(["merge-preview", "--pr", "42", "--json"])
        self.assertTrue(args.json)

    def test_repo_default(self):
        args = self._parse(["merge-preview", "--pr", "42"])
        self.assertEqual(".", args.repo)

    def test_repo_override(self):
        args = self._parse(["merge-preview", "--pr", "42", "--repo", "/some/path"])
        self.assertEqual("/some/path", args.repo)


# ---------------------------------------------------------------------------
# Argument parsing — pr-required
# ---------------------------------------------------------------------------

class PrRequiredArgParseTests(unittest.TestCase):

    def _parse(self, argv):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        p = sub.add_parser("pr-required")
        p.add_argument("--pr", type=int, required=True)
        p.add_argument("--repo", default=".")
        p.add_argument("--json", action="store_true")
        return parser.parse_args(argv)

    def test_pr_required(self):
        with self.assertRaises(SystemExit):
            self._parse(["pr-required"])

    def test_pr_parsed(self):
        args = self._parse(["pr-required", "--pr", "7"])
        self.assertEqual(7, args.pr)

    def test_json_flag_default_false(self):
        args = self._parse(["pr-required", "--pr", "7"])
        self.assertFalse(args.json)

    def test_json_flag_true(self):
        args = self._parse(["pr-required", "--pr", "7", "--json"])
        self.assertTrue(args.json)


# ---------------------------------------------------------------------------
# Exit-code mapping — cmd_pr_required
# ---------------------------------------------------------------------------

class PrRequiredExitCodeTests(unittest.TestCase):

    def _run_cmd(self, pr_data, az_found=True, org_url="https://dev.azure.com/Org",
                 json_flag=False):
        """Invoke cmd_pr_required with mocked dependencies; return captured stdout."""
        args = argparse.Namespace(pr=42, repo=".", json=json_flag)

        with mock.patch.object(MOD.shutil, "which", return_value="az" if az_found else None), \
             mock.patch.object(MOD, "resolve_org", return_value=(org_url, "Proj")), \
             mock.patch.object(MOD, "_fetch_pr", return_value=pr_data):
            try:
                captured = []
                with mock.patch("builtins.print", side_effect=lambda *a, **kw: captured.append(a[0])):
                    MOD.cmd_pr_required(args)
                return 0, captured
            except SystemExit as exc:
                return exc.code, []

    def test_exit_0_when_pr_resolves(self):
        code, out = self._run_cmd(SAMPLE_PR)
        self.assertEqual(0, code)

    def test_exit_0_pass_line_in_text_output(self):
        code, out = self._run_cmd(SAMPLE_PR)
        self.assertTrue(any("PASS" in str(line) for line in out))

    def test_exit_2_when_az_missing(self):
        code, _out = self._run_cmd(SAMPLE_PR, az_found=False)
        self.assertEqual(2, code)

    def test_exit_2_when_org_unresolvable(self):
        args = argparse.Namespace(pr=42, repo=".", json=False)
        with mock.patch.object(MOD.shutil, "which", return_value="az"), \
             mock.patch.object(MOD, "resolve_org", return_value=(None, None)):
            with self.assertRaises(SystemExit) as ctx:
                MOD.cmd_pr_required(args)
        self.assertEqual(2, ctx.exception.code)

    def test_exit_4_when_pr_not_found(self):
        code, _out = self._run_cmd(None)
        self.assertEqual(4, code)

    def test_exit_4_fail_line_in_text_output(self):
        # text mode: print before sys.exit(4) — captured via patched print
        args = argparse.Namespace(pr=42, repo=".", json=False)
        printed = []
        with mock.patch.object(MOD.shutil, "which", return_value="az"), \
             mock.patch.object(MOD, "resolve_org", return_value=("https://dev.azure.com/Org", "Proj")), \
             mock.patch.object(MOD, "_fetch_pr", return_value=None), \
             mock.patch("builtins.print", side_effect=lambda *a, **kw: printed.append(a[0])):
            with self.assertRaises(SystemExit):
                MOD.cmd_pr_required(args)
        self.assertTrue(any("FAIL" in str(line) for line in printed))

    def test_json_output_resolved_true(self):
        _code, out = self._run_cmd(SAMPLE_PR, json_flag=True)
        payload = json.loads(out[0])
        self.assertEqual(42, payload["prId"])
        self.assertTrue(payload["resolved"])
        self.assertIn("reason", payload)

    def test_json_output_resolved_false_on_exit4(self):
        args = argparse.Namespace(pr=42, repo=".", json=True)
        printed = []
        with mock.patch.object(MOD.shutil, "which", return_value="az"), \
             mock.patch.object(MOD, "resolve_org", return_value=("https://dev.azure.com/Org", "Proj")), \
             mock.patch.object(MOD, "_fetch_pr", return_value=None), \
             mock.patch("builtins.print", side_effect=lambda *a, **kw: printed.append(a[0])):
            with self.assertRaises(SystemExit) as ctx:
                MOD.cmd_pr_required(args)
        self.assertEqual(4, ctx.exception.code)
        payload = json.loads(printed[0])
        self.assertFalse(payload["resolved"])


# ---------------------------------------------------------------------------
# cmd_merge_preview exit-code and JSON shape
# ---------------------------------------------------------------------------

class MergePreviewCmdTests(unittest.TestCase):

    def _run_cmd(self, pr_data, az_found=True, json_flag=False):
        args = argparse.Namespace(pr=42, repo=".", json=json_flag)
        printed = []
        with mock.patch.object(MOD.shutil, "which", return_value="az" if az_found else None), \
             mock.patch.object(MOD, "resolve_org", return_value=("https://dev.azure.com/Org", "Proj")), \
             mock.patch.object(MOD, "_fetch_pr", return_value=pr_data), \
             mock.patch("builtins.print", side_effect=lambda *a, **kw: printed.append(a[0])):
            try:
                MOD.cmd_merge_preview(args)
                return 0, printed
            except SystemExit as exc:
                return exc.code, printed

    def test_exit_0_on_success(self):
        code, _ = self._run_cmd(SAMPLE_PR)
        self.assertEqual(0, code)

    def test_exit_2_when_az_missing(self):
        code, _ = self._run_cmd(SAMPLE_PR, az_found=False)
        self.assertEqual(2, code)

    def test_exit_3_when_pr_not_found(self):
        code, _ = self._run_cmd(None)
        self.assertEqual(3, code)

    def test_json_shape(self):
        _code, out = self._run_cmd(SAMPLE_PR, json_flag=True)
        payload = json.loads(out[0])
        self.assertEqual(42, payload["prId"])
        self.assertEqual("refs/pull/42/merge", payload["mergeRef"])
        self.assertIn("sourceRefName", payload)
        self.assertIn("targetRefName", payload)
        self.assertIn("mergeStatus", payload)
        self.assertIn("lastMergeCommit", payload)
        self.assertIn("lastMergeSourceCommit", payload)
        self.assertIn("lastMergeTargetCommit", payload)

    def test_text_output_contains_merge_ref(self):
        _code, out = self._run_cmd(SAMPLE_PR, json_flag=False)
        combined = "\n".join(str(x) for x in out)
        self.assertIn("refs/pull/42/merge", combined)


if __name__ == "__main__":
    unittest.main()
