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
    python ado_work_item.py context [--id N] [--pr N] [--repo PATH] [--no-parent] [--json]
    python ado_work_item.py detect  [--repo PATH]

Exit codes:
    0  success
    2  az CLI / auth / IO failure (az missing, not logged in, work item not found)
    3  no work item ID could be detected
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
