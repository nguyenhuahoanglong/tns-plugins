import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import pr_publish  # noqa: E402


GUID = "a046b071-4c1f-60bc-8970-9a33752df8ec"
OTHER_GUID = "b146b071-4c1f-60bc-8970-9a33752df8ec"
REPORT = "# Review\n\n" + ("Finding text. " * 80)
PR_META = {
    "id": GUID,
    "name": "Pull Request Author",
    "project": "Yana",
    "repo": "Core.Component.PCF",
}


class PublishModeTests(unittest.TestCase):
    def run_dry_publish(self, **overrides):
        current_identity = overrides.pop("_current_identity", OTHER_GUID)
        pr_meta = overrides.pop("_pr_meta", PR_META)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "review.md"
            report.write_text(REPORT, encoding="utf-8")
            values = {
                "self_review": False,
                "report": str(report),
                "dry_run": True,
                "pr_id": "79326",
                "org": "https://dev.azure.com/TechnosoftAutomotive",
                "mention_guid": None,
                "mention_name": None,
                "greeting": None,
                "prior_thread": None,
                "resolve_status": None,
            }
            values.update(overrides)
            out = io.StringIO()
            with patch.object(pr_publish, "get_pr_meta", return_value=pr_meta), \
                    patch.object(pr_publish, "get_current_identity", return_value=current_identity), \
                    contextlib.redirect_stdout(out):
                pr_publish.cmd_publish(SimpleNamespace(**values))
            return json.loads(out.getvalue())

    def test_default_mode_mentions_pr_author(self):
        result = self.run_dry_publish()
        self.assertEqual(result["mentionPolicy"], "author")
        self.assertFalse(result["selfReview"])
        self.assertEqual(result["mentionGuid"], GUID)
        self.assertIn(f"Hi @<{GUID.upper()}>", result["body"])
        self.assertEqual(result["selfReviewDetection"], "authenticated-user-differs-from-author")

    def test_same_authenticated_guid_automatically_suppresses_mention(self):
        result = self.run_dry_publish(_current_identity=GUID,
                                     _pr_meta={**PR_META, "id": GUID.upper()},
                                     greeting="Hi {name}, {mention}")
        self.assertTrue(result["selfReview"])
        self.assertEqual(result["mentionPolicy"], "none")
        self.assertEqual(result["selfReviewDetection"], "authenticated-user-matches-author")
        self.assertIsNone(result["mentionGuid"])
        self.assertIsNone(result["mentionName"])
        self.assertTrue(result["body"].startswith("Code review result:\n\n---\n"))
        self.assertNotIn("@<", result["body"])
        self.assertNotIn(PR_META["name"], result["body"])

    def test_explicit_modes_skip_identity_detection(self):
        with patch.object(pr_publish, "get_current_identity") as identity:
            args = SimpleNamespace(self_review=True, mention_guid=None)
            self.assertEqual(pr_publish.resolve_mention(args, PR_META)[4], "explicit-self-review")
            args = SimpleNamespace(self_review=False, mention_guid=OTHER_GUID, mention_name=None)
            self.assertEqual(pr_publish.resolve_mention(args, PR_META)[4], "explicit-mention")
            identity.assert_not_called()

    def test_connection_identity_is_guid_only_and_normalized(self):
        response = {"authenticatedUser": {"id": GUID.upper(), "displayName": "Other Name"}}
        with patch.object(pr_publish, "run_az", return_value=response) as run:
            self.assertEqual(pr_publish.get_current_identity("https://example.test/org/"), GUID)
        self.assertIn("https://example.test/org/_apis/connectionData", run.call_args.args[0])
        self.assertIn(pr_publish.ADO_RESOURCE, run.call_args.args[0])

    def test_missing_or_invalid_identity_never_falls_back_to_name(self):
        responses = [None, {}, {"authenticatedUser": {"displayName": PR_META["name"]}},
                     {"authenticatedUser": {"id": "invalid"}},
                     {"authenticatedUser": {"id": "00000000-0000-0000-0000-000000000000"}}]
        for response in responses:
            with self.subTest(response=response), \
                    patch.object(pr_publish, "run_az", return_value=response), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    pr_publish.get_current_identity("https://example.test/org")
                self.assertEqual(raised.exception.code, 3)

    def test_unavailable_identity_stops_before_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "review.md"
            report.write_text(REPORT, encoding="utf-8")
            args = SimpleNamespace(self_review=False, mention_guid=None, mention_name=None,
                                   greeting=None, report=str(report), dry_run=False,
                                   pr_id="1", org="https://example.test/org")
            with patch.object(pr_publish, "get_pr_meta", return_value=PR_META), \
                    patch.object(pr_publish, "run_az", side_effect=SystemExit(2)), \
                    patch.object(pr_publish, "post_thread") as post, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    pr_publish.cmd_publish(args)
                self.assertEqual(raised.exception.code, 3)
                post.assert_not_called()

    def test_explicit_mention_override_is_reported(self):
        result = self.run_dry_publish(mention_guid=OTHER_GUID)
        self.assertEqual(result["mentionPolicy"], "explicit")
        self.assertEqual(result["mentionGuid"], OTHER_GUID)
        self.assertIn(f"Hi @<{OTHER_GUID.upper()}>", result["body"])

    def test_self_review_uses_neutral_full_body_and_null_identity(self):
        result = self.run_dry_publish(self_review=True)
        self.assertEqual(result["mentionPolicy"], "none")
        self.assertTrue(result["selfReview"])
        self.assertIsNone(result["mentionGuid"])
        self.assertIsNone(result["mentionName"])
        self.assertTrue(result["body"].startswith("Code review result:\n\n---\n"))
        self.assertNotIn("@<", result["body"].split("\n", 1)[0])
        self.assertNotIn("Pull Request Author", result["body"].split("\n", 1)[0])
        self.assertIn(REPORT.strip(), result["body"])
        self.assertGreater(len(result["body"]), len(result["bodyPreview"]))

    def test_self_review_rejects_explicit_mention_options(self):
        args = SimpleNamespace(self_review=True, mention_guid=OTHER_GUID,
                               mention_name=None, greeting=None)
        with patch.object(pr_publish, "get_pr_meta") as get_pr_meta, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                pr_publish.cmd_publish(args)
        self.assertEqual(raised.exception.code, 3)
        get_pr_meta.assert_not_called()

    def test_az_output_uses_strict_locale_fallback_for_windows_bytes(self):
        completed = SimpleNamespace(returncode=0,
                                    stdout='{"title": "A — B"}'.encode("cp1252"),
                                    stderr=b"")
        with patch.object(pr_publish.subprocess, "run", return_value=completed) as run, \
                patch.object(pr_publish.locale, "getencoding", return_value="cp1252",
                             create=True), patch.object(pr_publish.os, "name", "nt"):
            self.assertEqual(pr_publish.run_az(["version"]), {"title": "A — B"})
        self.assertNotIn("encoding", run.call_args.kwargs)
        self.assertNotIn("errors", run.call_args.kwargs)

    def test_az_output_does_not_replace_undecodable_bytes(self):
        completed = SimpleNamespace(returncode=0, stdout=b"\xff", stderr=b"")
        with patch.object(pr_publish.subprocess, "run", return_value=completed), \
                patch.object(pr_publish.locale, "getencoding", return_value="ascii",
                             create=True):
            with self.assertRaises(UnicodeDecodeError):
                pr_publish.run_az(["version"])


class VerifyOutputTests(unittest.TestCase):
    def run_verifier(self, mode, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ("input.json" if isinstance(data, dict) else "input.txt")
            path.write_text(json.dumps(data) if isinstance(data, dict) else data,
                            encoding="utf-8")
            return __import__("subprocess").run(
                [sys.executable, str(SKILL_ROOT / "scripts" / "verify_output.py"),
                 mode, str(path)], capture_output=True, text=True, check=False)

    def test_full_dry_run_json_body_is_verifiable(self):
        body = "Code review result:\n\n---\n" + ("Finding. " * 200)
        result = self.run_verifier("body", {"body": body, "bodyPreview": body[:600]})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_author_mention_body_remains_verifiable(self):
        body = f"Hi @<{GUID.upper()}>, please help me check this code review result:\n\n---\nFull report"
        result = self.run_verifier("body", body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_self_review_state_and_legacy_mentioned_state_are_valid(self):
        base = {"prId": 79326, "threadId": 1, "commentId": 2, "iteration": 1}
        self_review = {**base, "mentionPolicy": "none", "selfReview": True,
                       "mentionGuid": None, "mentionName": None}
        legacy = {**base, "mentionGuid": GUID}
        for state in (self_review, legacy):
            with self.subTest(state=state):
                result = self.run_verifier("state", state)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_inconsistent_policy_state_is_rejected(self):
        state = {"prId": 79326, "threadId": 1, "commentId": 2, "iteration": 1,
                 "mentionPolicy": "none", "selfReview": True, "mentionGuid": GUID}
        result = self.run_verifier("state", state)
        self.assertEqual(result.returncode, 1)
        self.assertIn("null 'mentionGuid'", result.stdout)


if __name__ == "__main__":
    unittest.main()
