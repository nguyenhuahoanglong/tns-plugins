#!/usr/bin/env python3
"""Validate review branch naming and backing Azure DevOps work item type."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path


AZ_TIMEOUT_SECONDS = 60
BRANCH_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)/(\d{3,6})(?:-[a-z0-9][a-z0-9-]*)?$")
TYPE_BY_PREFIX = {
    "US": "User Story",
    "BUG": "Bug",
    "ISSUE": "Issue",
}
ALLOWED_TYPES = {"User Story", "Bug", "Issue"}


def configure_utf8_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run(cmd, cwd=None):
    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
            encoding="utf-8",
            errors="replace",
            timeout=AZ_TIMEOUT_SECONDS,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def git(repo, *args):
    rc, out, _err = run(["git", "-C", str(repo), *args])
    return out if rc == 0 else ""


def normalize_branch(branch):
    value = (branch or "").strip()
    for prefix in ("refs/heads/", "origin/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value


def resolve_org(repo):
    context_file = Path(repo) / ".docs" / "ado-context.md"
    if context_file.is_file():
        try:
            text = context_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        match = re.search(r"\*\*Project URL\*\*:\s*(\S+)", text)
        if match:
            parsed = urllib.parse.urlparse(match.group(1))
            parts = [p for p in parsed.path.split("/") if p]
            if parsed.netloc and parts:
                return f"{parsed.scheme}://{parsed.netloc}/{parts[0]}"

    remote = git(repo, "remote", "get-url", "origin")
    patterns = [
        r"https://(?:[^@/]+@)?dev\.azure\.com/(?P<org>[^/]+)/(?P<project>[^/]+)/_git/",
        r"https://(?P<org>[^./]+)\.visualstudio\.com/(?:DefaultCollection/)?(?P<project>[^/]+)/_git/",
        r"git@ssh\.dev\.azure\.com:v3/(?P<org>[^/]+)/(?P<project>[^/]+)/",
    ]
    for pattern in patterns:
        match = re.search(pattern, remote)
        if match:
            org = match.group("org")
            if "visualstudio" in pattern:
                return f"https://{org}.visualstudio.com"
            return f"https://dev.azure.com/{org}"
    return None


def fetch_work_item(az_exe, org_url, work_item_id, runner=run):
    args = [
        az_exe,
        "boards",
        "work-item",
        "show",
        "--id",
        str(work_item_id),
        "--organization",
        org_url,
        "-o",
        "json",
    ]
    rc, out, err = runner(args)
    if rc != 0:
        reason = err.splitlines()[0] if err else "az boards work-item show failed"
        return None, reason
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return None, f"az returned invalid JSON: {exc}"


def result(status, **kwargs):
    base = {
        "Status": status,
        "Branch": kwargs.get("branch", "None"),
        "Prefix": kwargs.get("prefix", "None"),
        "Work Item ID": kwargs.get("work_item_id", "None"),
        "Expected Type": kwargs.get("expected_type", "None"),
        "Actual Type": kwargs.get("actual_type", "None"),
        "Title": kwargs.get("title", "None"),
        "State": kwargs.get("state", "None"),
        "Source": kwargs.get("source", "None"),
        "Reason": kwargs.get("reason", "None"),
    }
    return base


def evaluate(scope_type, branch=None, repo=".", az_exe=None, runner=run):
    scope = (scope_type or "").lower()
    if scope not in {"pr", "branch"}:
        return result(
            "SKIPPED",
            branch=normalize_branch(branch),
            source=scope_type or "unknown",
            reason="Scope has no created PR or branch to validate",
        )

    repo_path = Path(repo)
    source_branch = normalize_branch(branch) or normalize_branch(
        git(repo_path, "branch", "--show-current")
    )
    match = BRANCH_PATTERN.fullmatch(source_branch)
    if not match:
        return result(
            "FAIL",
            branch=source_branch or "None",
            source=scope,
            reason="Branch must match {slug}/{work-item-id} with optional -{text}",
        )

    prefix, work_item_id = match.group(1), match.group(2)
    expected_type = TYPE_BY_PREFIX.get(prefix.upper())
    resolved_az = az_exe or shutil.which("az")
    if not resolved_az:
        return result(
            "FAIL",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type=expected_type,
            source=scope,
            reason="az CLI not found on PATH",
        )

    org_url = resolve_org(repo_path)
    if not org_url:
        return result(
            "FAIL",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type=expected_type,
            source=scope,
            reason="Could not resolve ADO organization from .docs/ado-context.md or git remote",
        )

    item, error = fetch_work_item(resolved_az, org_url, work_item_id, runner=runner)
    if error:
        return result(
            "FAIL",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type=expected_type,
            source=scope,
            reason=error,
        )

    fields = item.get("fields", {})
    actual_type = fields.get("System.WorkItemType", "")
    title = fields.get("System.Title", "")
    state = fields.get("System.State", "")
    if actual_type not in ALLOWED_TYPES:
        return result(
            "FAIL",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type="User Story | Bug | Issue",
            actual_type=actual_type or "None",
            title=title or "None",
            state=state or "None",
            source=scope,
            reason="ADO work item type must be User Story, Bug, or Issue",
        )

    if expected_type is None:
        return result(
            "WARN",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type="None",
            actual_type=actual_type,
            title=title or "None",
            state=state or "None",
            source=scope,
            reason="Branch prefix is not US, BUG, or ISSUE; ADO work item ID is valid",
        )

    if actual_type != expected_type:
        return result(
            "WARN",
            branch=source_branch,
            prefix=prefix,
            work_item_id=work_item_id,
            expected_type=expected_type,
            actual_type=actual_type,
            title=title or "None",
            state=state or "None",
            source=scope,
            reason="ADO work item type does not match branch prefix; ADO work item ID is valid",
        )

    return result(
        "PASS",
        branch=source_branch,
        prefix=prefix,
        work_item_id=work_item_id,
        expected_type=expected_type,
        actual_type=actual_type,
        title=title or "None",
        state=state or "None",
        source=scope,
        reason="Branch prefix and ADO work item type match",
    )


def render_markdown(data):
    lines = ["## Branch Work Item Gate"]
    for key in (
        "Status",
        "Branch",
        "Prefix",
        "Work Item ID",
        "Expected Type",
        "Actual Type",
        "Title",
        "State",
        "Source",
        "Reason",
    ):
        lines.append(f"- **{key}**: {data.get(key, 'None')}")
    return "\n".join(lines)


def main(argv=None):
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-type", required=True,
                        help="Review scope type: pr, branch, staged, working, or files")
    parser.add_argument("--branch", help="Source branch. Defaults to current branch.")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    data = evaluate(args.scope_type, args.branch, args.repo)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data))
    return 1 if data["Status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
