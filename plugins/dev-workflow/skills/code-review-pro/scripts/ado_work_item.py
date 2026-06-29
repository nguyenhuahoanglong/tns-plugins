#!/usr/bin/env python3
"""Fetch Azure DevOps work item context for code review skills.

Mirrored in code-review-pro/scripts/ and code-review-lite/scripts/ — keep in sync.

Detects the work item linked to the current change (PR linked items > branch
name > recent commit messages), fetches it via the `az boards` CLI, strips the
HTML that ADO stores in Description / Acceptance Criteria, and emits a compact
markdown block ready to inject into a reviewer agent prompt.

Organization/project resolution: `{repo}/.docs/ado-context.md` ("Project URL:"
line, maintained by the azdevops-context skill) > `git remote get-url origin`.

Usage:
    python ado_work_item.py context       [--id N] [--pr N] [--repo PATH] [--no-parent] [--json]
    python ado_work_item.py detect        [--repo PATH]
    python ado_work_item.py merge-preview --pr N [--repo PATH] [--json]
    python ado_work_item.py pr-required   --pr N [--repo PATH] [--json]

Exit codes:
    0  success
    2  az CLI / auth / IO failure (az missing, not logged in, network error)
    3  no work item ID could be detected  (context / detect subcommands)
    4  PR not found / not resolvable      (pr-required subcommand only;
       az reached ADO but the PR id does not exist — distinct from code 2
       so the orchestrator can distinguish "tooling unavailable" from
       "PR genuinely absent" when enforcing PR-only review mode)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

AZ_TIMEOUT_SECONDS = 60

FIELD_TITLE = "System.Title"
FIELD_TYPE = "System.WorkItemType"
FIELD_STATE = "System.State"
FIELD_DESCRIPTION = "System.Description"
FIELD_ACCEPTANCE = "Microsoft.VSTS.Common.AcceptanceCriteria"
FIELD_REPRO = "Microsoft.VSTS.TCM.ReproSteps"
PARENT_RELATION = "System.LinkTypes.Hierarchy-Reverse"


def configure_utf8_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def fail(code, message):
    print(f"ado_work_item: {message}", file=sys.stderr)
    sys.exit(code)


def run(cmd, cwd=None):
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        # PYTHONIOENCODING forces the (Python-based) az CLI to emit UTF-8
        # instead of the console codepage, which silently drops characters.
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=AZ_TIMEOUT_SECONDS,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def git(repo, *args):
    rc, out, _ = run(["git", "-C", str(repo), *args])
    return out if rc == 0 else ""


def az_json(az_exe, args):
    """Run an az command expecting JSON output. Exits 2 on failure."""
    rc, out, err = run([az_exe, *args, "-o", "json"])
    if rc != 0:
        reason = err.splitlines()[0] if err else "az command failed"
        fail(2, f"az {' '.join(args[:3])} failed: {reason}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        fail(2, "az returned non-JSON output (extension prompt? run: "
                "az config set extension.use_dynamic_install=yes_without_prompt)")


# --- Organization / project resolution -------------------------------------

def resolve_org(repo):
    """Return (org_url, project) from .docs/ado-context.md or the git remote."""
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
                org_url = f"{parsed.scheme}://{parsed.netloc}/{parts[0]}"
                project = urllib.parse.unquote(parts[1]) if len(parts) > 1 else None
                return org_url, project

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
            host = f"https://{org}.visualstudio.com" if "visualstudio" in pattern \
                else f"https://dev.azure.com/{org}"
            return host, urllib.parse.unquote(match.group("project"))
    return None, None


# --- Work item ID detection -------------------------------------------------

BRANCH_ID_PATTERN = re.compile(r"(?i)(?:^|[/_-])(?:wi[-_]?|ab#)?(\d{3,6})(?=[-_./]|$)")
COMMIT_ID_PATTERNS = [
    re.compile(r"(?i)AB#(\d{3,6})"),
    re.compile(r"(?i)\[WI:(\d{3,6})\]"),
    re.compile(r"(?i)(?:fixes|closes|resolves)\s+#(\d{3,6})"),
    re.compile(r"(?<![\w&])#(\d{3,6})"),
]


def detect_from_pr(az_exe, org_url, pr_id):
    items = az_json(az_exe, ["repos", "pr", "work-item", "list",
                             "--id", str(pr_id), "--organization", org_url])
    if items:
        return int(items[0]["id"]), f"PR !{pr_id} linked work items"
    return None, None


def detect_from_repo(repo):
    branch = git(repo, "branch", "--show-current")
    match = BRANCH_ID_PATTERN.search(branch)
    if match:
        return int(match.group(1)), f"branch name '{branch}'"

    log = git(repo, "log", "--pretty=%s", "-20")
    for subject in log.splitlines():
        for pattern in COMMIT_ID_PATTERNS:
            match = pattern.search(subject)
            if match:
                return int(match.group(1)), f"commit message '{subject.strip()}'"
    return None, None


# --- HTML -> compact text ----------------------------------------------------

class HtmlToText(HTMLParser):
    BLOCK_TAGS = {"p", "div", "ul", "ol", "table", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("b", "strong"):
            self.parts.append("**")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("b", "strong"):
            self.parts.append("**")
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in ("tr", "li") or tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html):
    if not html:
        return ""
    parser = HtmlToText()
    parser.feed(html)
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Fetch + render -----------------------------------------------------------

def fetch_work_item(az_exe, org_url, work_item_id, with_parent=True):
    item = az_json(az_exe, ["boards", "work-item", "show",
                            "--id", str(work_item_id),
                            "--expand", "relations",
                            "--organization", org_url])
    fields = item.get("fields", {})
    data = {
        "id": item.get("id", work_item_id),
        "title": fields.get(FIELD_TITLE, ""),
        "type": fields.get(FIELD_TYPE, ""),
        "state": fields.get(FIELD_STATE, ""),
        "description": html_to_text(fields.get(FIELD_DESCRIPTION, "")
                                    or fields.get(FIELD_REPRO, "")),
        "acceptanceCriteria": html_to_text(fields.get(FIELD_ACCEPTANCE, "")),
        "parent": None,
    }

    if with_parent:
        for relation in item.get("relations") or []:
            if relation.get("rel") == PARENT_RELATION:
                parent_id = relation["url"].rstrip("/").rsplit("/", 1)[-1]
                parent = az_json(az_exe, ["boards", "work-item", "show",
                                          "--id", parent_id, "--expand", "none",
                                          "--fields", f"{FIELD_TITLE},{FIELD_TYPE},{FIELD_STATE}",
                                          "--organization", org_url])
                pfields = parent.get("fields", {})
                data["parent"] = {
                    "id": int(parent_id),
                    "title": pfields.get(FIELD_TITLE, ""),
                    "type": pfields.get(FIELD_TYPE, ""),
                    "state": pfields.get(FIELD_STATE, ""),
                }
                break
    return data


def render_markdown(data, source):
    lines = [f"## Work Item #{data['id']} — {data['title']}",
             f"- **Type/State**: {data['type']} / {data['state']}"]
    if data["parent"]:
        parent = data["parent"]
        lines.append(f"- **Parent**: #{parent['id']} — {parent['title']} ({parent['type']})")
    if source:
        lines.append(f"- **Detected from**: {source}")
    lines.append("")
    lines.append("### Description")
    lines.append(data["description"] or "_(none on work item)_")
    lines.append("")
    lines.append("### Acceptance Criteria")
    lines.append(data["acceptanceCriteria"] or "_(none on work item)_")
    return "\n".join(lines)


# --- PR helpers ---------------------------------------------------------------

def _fetch_pr(az_exe, org_url, pr_id):
    """Call az repos pr show and return the raw JSON dict.

    Raises SystemExit(2) on az / auth / IO failure.
    Returns None if az reaches ADO but the PR is not found (HTTP 404 / empty).
    """
    rc, out, err = run([az_exe, "repos", "pr", "show",
                        "--id", str(pr_id),
                        "--organization", org_url,
                        "-o", "json"])
    if rc != 0:
        reason = err.splitlines()[0] if err else "az repos pr show failed"
        # Treat "does not exist" / "not found" responses as a distinct not-found
        # signal so callers can map to exit 3 or 4 as appropriate.
        not_found_phrases = ("does not exist", "not found", "TF401232",
                             "could not be found", "no pull request")
        if any(p in reason.lower() for p in not_found_phrases):
            return None
        fail(2, f"az repos pr show --id {pr_id} failed: {reason}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        fail(2, "az returned non-JSON output (extension prompt? run: "
                "az config set extension.use_dynamic_install=yes_without_prompt)")
    # az can return an empty dict/list when the PR id is invalid without a
    # non-zero exit code in some versions.
    if not data or (isinstance(data, dict) and not data.get("pullRequestId")):
        return None
    return data


def _extract_merge_preview(pr_id, pr_data):
    """Return the merge-preview dict from a raw az repos pr show response."""
    last_merge = pr_data.get("lastMergeCommit") or {}
    last_merge_source = pr_data.get("lastMergeSourceCommit") or {}
    last_merge_target = pr_data.get("lastMergeTargetCommit") or {}
    return {
        "prId": pr_id,
        "sourceRefName": pr_data.get("sourceRefName"),
        "targetRefName": pr_data.get("targetRefName"),
        "lastMergeCommit": last_merge.get("commitId"),
        "lastMergeSourceCommit": last_merge_source.get("commitId"),
        "lastMergeTargetCommit": last_merge_target.get("commitId"),
        "mergeStatus": pr_data.get("mergeStatus"),
        "mergeRef": f"refs/pull/{pr_id}/merge",
    }


# --- Commands ------------------------------------------------------------------

def cmd_detect(args):
    work_item_id, source = detect_from_repo(args.repo)
    if work_item_id is None:
        print(json.dumps({"id": None, "source": None}))
        fail(3, "no work item ID detectable from branch name or recent commits")
    print(json.dumps({"id": work_item_id, "source": source}))


def cmd_context(args):
    az_exe = shutil.which("az")
    if not az_exe:
        fail(2, "az CLI not found on PATH — install Azure CLI to fetch work items")

    org_url, _project = resolve_org(args.repo)
    if not org_url:
        fail(2, "could not resolve ADO organization from .docs/ado-context.md "
                "or the git remote 'origin'")

    work_item_id, source = (args.id, None) if args.id else (None, None)
    if work_item_id is None and args.pr:
        work_item_id, source = detect_from_pr(az_exe, org_url, args.pr)
    if work_item_id is None:
        work_item_id, source = detect_from_repo(args.repo)
    if work_item_id is None:
        fail(3, "no work item ID detectable (no --id/--pr, nothing in branch "
                "name or last 20 commit subjects)")

    data = fetch_work_item(az_exe, org_url, work_item_id,
                           with_parent=not args.no_parent)
    data["source"] = source

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data, source))


def cmd_merge_preview(args):
    az_exe = shutil.which("az")
    if not az_exe:
        fail(2, "az CLI not found on PATH — install Azure CLI to fetch PR details")

    org_url, _project = resolve_org(args.repo)
    if not org_url:
        fail(2, "could not resolve ADO organization from .docs/ado-context.md "
                "or the git remote 'origin'")

    pr_data = _fetch_pr(az_exe, org_url, args.pr)
    if pr_data is None:
        fail(3, f"PR {args.pr} not found in organization {org_url}")

    result = _extract_merge_preview(args.pr, pr_data)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        lines = [
            f"## PR !{result['prId']} — Merge Preview",
            f"- **Source ref**:        {result['sourceRefName']}",
            f"- **Target ref**:        {result['targetRefName']}",
            f"- **Merge ref**:         {result['mergeRef']}",
            f"- **Merge status**:      {result['mergeStatus']}",
            f"- **Last merge commit**: {result['lastMergeCommit'] or '(none)'}",
            f"- **Last merge source**: {result['lastMergeSourceCommit'] or '(none)'}",
            f"- **Last merge target**: {result['lastMergeTargetCommit'] or '(none)'}",
        ]
        print("\n".join(lines))


def cmd_pr_required(args):
    az_exe = shutil.which("az")
    if not az_exe:
        # Exit 2: tooling unavailable — cannot determine PR existence.
        if args.json:
            print(json.dumps({"prId": args.pr, "resolved": False,
                              "reason": "az CLI not found on PATH"}))
        fail(2, "az CLI not found on PATH — install Azure CLI to verify PR")

    org_url, _project = resolve_org(args.repo)
    if not org_url:
        if args.json:
            print(json.dumps({"prId": args.pr, "resolved": False,
                              "reason": "could not resolve ADO organization"}))
        fail(2, "could not resolve ADO organization from .docs/ado-context.md "
                "or the git remote 'origin'")

    pr_data = _fetch_pr(az_exe, org_url, args.pr)

    if pr_data is None:
        # Exit 4: az reached ADO but PR id does not exist.
        msg = f"PR {args.pr} not found — this review requires a PR to proceed"
        if args.json:
            print(json.dumps({"prId": args.pr, "resolved": False, "reason": msg}))
        else:
            print(f"FAIL: {msg}")
        sys.exit(4)

    msg = f"PR {args.pr} resolved (mergeStatus: {pr_data.get('mergeStatus', 'unknown')})"
    if args.json:
        print(json.dumps({"prId": args.pr, "resolved": True, "reason": msg}))
    else:
        print(f"PASS: {msg}")


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_context = sub.add_parser("context", help="detect + fetch + render work item context")
    p_context.add_argument("--id", type=int, help="explicit work item ID (skips detection)")
    p_context.add_argument("--pr", type=int, help="PR ID to read linked work items from")
    p_context.add_argument("--repo", default=".", help="repository path (default: cwd)")
    p_context.add_argument("--no-parent", action="store_true", help="skip parent fetch")
    p_context.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_context.set_defaults(func=cmd_context)

    p_detect = sub.add_parser("detect", help="detection only, prints JSON {id, source}")
    p_detect.add_argument("--repo", default=".", help="repository path (default: cwd)")
    p_detect.set_defaults(func=cmd_detect)

    p_merge = sub.add_parser(
        "merge-preview",
        help="fetch PR merge-preview fields (refs, commits, mergeStatus, mergeRef)")
    p_merge.add_argument("--pr", type=int, required=True, help="PR ID")
    p_merge.add_argument("--repo", default=".", help="repository path (default: cwd)")
    p_merge.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p_merge.set_defaults(func=cmd_merge_preview)

    p_pr_req = sub.add_parser(
        "pr-required",
        help="gate: verify PR exists (exit 0=resolved, 2=az unavailable, 4=PR not found)")
    p_pr_req.add_argument("--pr", type=int, required=True, help="PR ID")
    p_pr_req.add_argument("--repo", default=".", help="repository path (default: cwd)")
    p_pr_req.add_argument("--json", action="store_true",
                          help="emit JSON {prId, resolved, reason}")
    p_pr_req.set_defaults(func=cmd_pr_required)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
