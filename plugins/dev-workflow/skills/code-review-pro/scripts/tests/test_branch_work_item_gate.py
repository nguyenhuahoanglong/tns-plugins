import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "branch_work_item_gate.py"
SPEC = importlib.util.spec_from_file_location("branch_work_item_gate", SCRIPT)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def repo_with_context(root):
    docs = Path(root) / ".docs"
    docs.mkdir()
    (docs / "ado-context.md").write_text(
        "**Project URL**: https://dev.azure.com/TestOrg/TestProject/_backlogs/backlog",
        encoding="utf-8",
    )


def ado_runner(work_item_type, rc=0):
    def run(_cmd, cwd=None):
        if rc != 0:
            return rc, "", "work item not found"
        return 0, json.dumps({
            "fields": {
                "System.WorkItemType": work_item_type,
                "System.Title": "Gate item",
                "System.State": "Active",
            }
        }), ""
    return run


class BranchWorkItemGateTests(unittest.TestCase):
    def evaluate(self, branch, work_item_type="User Story", scope="branch", rc=0):
        with tempfile.TemporaryDirectory() as root:
            repo_with_context(root)
            return GATE.evaluate(
                scope,
                branch,
                root,
                az_exe="az",
                runner=ado_runner(work_item_type, rc),
            )

    def test_user_story_branch_without_slug_passes(self):
        result = self.evaluate("US/1878", "User Story")
        self.assertEqual("PASS", result["Status"])
        self.assertEqual("User Story", result["Expected Type"])

    def test_bug_branch_without_slug_passes(self):
        result = self.evaluate("BUG/2101", "Bug")
        self.assertEqual("PASS", result["Status"])
        self.assertEqual("Bug", result["Expected Type"])

    def test_issue_branch_without_slug_passes(self):
        result = self.evaluate("ISSUE/2102", "Issue")
        self.assertEqual("PASS", result["Status"])
        self.assertEqual("Issue", result["Expected Type"])

    def test_branch_with_slug_still_passes(self):
        result = self.evaluate("US/1878-valid-story", "User Story")
        self.assertEqual("PASS", result["Status"])
        self.assertEqual("1878", result["Work Item ID"])

    def test_unknown_prefix_warns_when_type_allowed(self):
        result = self.evaluate("hotfix/1878", "User Story")
        self.assertEqual("WARN", result["Status"])
        self.assertEqual("1878", result["Work Item ID"])
        self.assertEqual("User Story", result["Actual Type"])

    def test_prefix_type_mismatch_warns_when_type_allowed(self):
        result = self.evaluate("US/2101", "Bug")
        self.assertEqual("WARN", result["Status"])
        self.assertEqual("User Story", result["Expected Type"])
        self.assertEqual("Bug", result["Actual Type"])

    def test_malformed_branch_fails(self):
        result = self.evaluate("US-1878-invalid", "User Story")
        self.assertEqual("FAIL", result["Status"])
        self.assertIn("Branch must match", result["Reason"])

    def test_empty_slug_fails(self):
        result = self.evaluate("US/1878-", "User Story")
        self.assertEqual("FAIL", result["Status"])
        self.assertIn("{slug}/{work-item-id}", result["Reason"])

    def test_missing_branch_id_fails(self):
        result = self.evaluate("hotfix/no-ticket", "User Story")
        self.assertEqual("FAIL", result["Status"])
        self.assertEqual("None", result["Work Item ID"])

    def test_work_item_not_found_fails(self):
        result = self.evaluate("US/1878-valid-story", "User Story", rc=1)
        self.assertEqual("FAIL", result["Status"])
        self.assertEqual("work item not found", result["Reason"])

    def test_disallowed_work_item_type_fails(self):
        result = self.evaluate("US/1879", "Task")
        self.assertEqual("FAIL", result["Status"])
        self.assertEqual("Task", result["Actual Type"])
        self.assertEqual("User Story | Bug | Issue", result["Expected Type"])

    def test_az_unavailable_fails(self):
        with tempfile.TemporaryDirectory() as root:
            repo_with_context(root)
            with mock.patch.object(GATE.shutil, "which", return_value=None):
                result = GATE.evaluate("branch", "US/1878-valid-story", root)
        self.assertEqual("FAIL", result["Status"])
        self.assertEqual("az CLI not found on PATH", result["Reason"])

    def test_working_scope_skips(self):
        result = self.evaluate("US/1878-valid-story", "User Story", scope="working")
        self.assertEqual("SKIPPED", result["Status"])


if __name__ == "__main__":
    unittest.main()
