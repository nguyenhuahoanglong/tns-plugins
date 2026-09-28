#!/usr/bin/env python3
"""
pr_publish.py — publish a code review to an Azure DevOps PR thread.

PR mode of code-review-publish: posts the FULL review report inline as a new
PR discussion thread, prefixed with an author mention or neutral self-review
label.
Unlike work-item mode there is no attachment — PR threads render the report
inline. On followup it posts a fresh thread and resolves the prior one.

Subcommands:
    pr_publish.py pr-info <pr-id> [--org <url>]
        Resolve PR metadata + mention target. JSON:
        {prId, project, repo, repoId, sourceRef, targetRef, title,
         mentionGuid, mentionName, mentionEmail}

    pr_publish.py publish <pr-id> --report <path> [--org <url>]
        [--mention-guid <g>] [--mention-name <n>] [--greeting <text>]
        [--prior-thread <id>] [--resolve-status closed|fixed] [--dry-run]
        Compose body (greeting + '---' + report), POST a new thread, and —
        when --prior-thread is given — PATCH that thread to a resolved status.
        JSON: {threadId, commentId, mentionPolicy, selfReview, mentionGuid,
               mentionName, priorThreadResolved, webUrl}

The mention token written into the body is `@<GUID>` (uppercased) — the
documented Markdown-editor mention syntax. Posting it raw via REST registers a
true mention and notifies the user (copy-paste from the UI does not; raw does).

Exit codes:
  0 — success
  2 — file / az / IO error
  3 — invalid input / missing required field
"""

import sys
import json
import argparse
import subprocess
import tempfile
import shutil
import os
import locale
from uuid import UUID
from pathlib import Path

from ado_autolink_guard import check_file, find_issues, fix_file, fix_text

# On Windows `az` is az.cmd; resolve the real executable so subprocess finds it.
AZ = shutil.which("az") or "az"

DEFAULT_ORG = "https://dev.azure.com/TechnosoftAutomotive"
ADO_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"
API = "api-version=7.1"
DEFAULT_GREETING = "Hi {mention}, please help me check this code review result:"
SELF_REVIEW_GREETING = "Code review result:"
# ADO thread status strings accepted by the REST API.
RESOLVE_STATUS = {"closed", "fixed", "wontfix", "bydesign"}


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def decode_cli_output(output):
    """Decode CLI bytes as UTF-8, then strictly as the system locale encoding."""
    if isinstance(output, str):
        return output
    if not output:
        return ""
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as utf8_error:
        if os.name != "nt":
            raise utf8_error
        # `getencoding()` reports Windows' ANSI code page even when the parent
        # Python runs in UTF-8 mode; fall back for older Python versions.
        get_encoding = getattr(locale, "getencoding", None)
        encoding = (get_encoding() if get_encoding
                    else locale.getpreferredencoding(False))
        if encoding.casefold().replace("_", "-") in ("utf-8", "utf8"):
            raise utf8_error
        try:
            return output.decode(encoding)
        except UnicodeDecodeError as locale_error:
            raise locale_error from utf8_error


def run_az(args):
    """Run an `az` command, returning parsed JSON stdout (or raw text)."""
    proc = subprocess.run([AZ, *args], capture_output=True)
    stdout = decode_cli_output(proc.stdout)
    stderr = decode_cli_output(proc.stderr)
    if proc.returncode != 0:
        die(f"az {' '.join(args)} failed:\n{stderr.strip()}")
    out = stdout.strip()
    try:
        return json.loads(out) if out else None
    except json.JSONDecodeError:
        return out


def get_pr_meta(pr_id, org):
    pr = run_az([
        "repos", "pr", "show", "--id", str(pr_id), "--org", org,
        "--query",
        "{id:createdBy.id, name:createdBy.displayName, email:createdBy.uniqueName,"
        " repo:repository.name, repoId:repository.id,"
        " project:repository.project.name, source:sourceRefName,"
        " target:targetRefName, title:title}",
        "-o", "json",
    ])
    if not pr:
        die(f"PR {pr_id} not found or access denied", 3)
    return pr


def normalize_identity(value):
    """ADO identity IDs are GUIDs; display names and emails are not identity keys."""
    try:
        identity = UUID(value) if isinstance(value, str) else None
    except ValueError:
        identity = None
    if not identity or not identity.int:
        raise ValueError("ADO identity ID is missing or invalid")
    return str(identity)


def get_current_identity(org):
    """Read the identity authenticated through the same az rest path as POST."""
    try:
        connection = run_az([
            "rest", "--method", "GET", "--uri",
            f"{org.rstrip('/')}/_apis/connectionData",
            "--resource", ADO_RESOURCE, "-o", "json",
        ])
        user = connection.get("authenticatedUser") if isinstance(connection, dict) else None
        return normalize_identity(user.get("id") if isinstance(user, dict) else None)
    except (SystemExit, ValueError, UnicodeError, OSError) as exc:
        die("Cannot verify the authenticated ADO identity for automatic self-review "
            "detection. Restore ADO access or explicitly choose --self-review or "
            "--mention-guid. No comment was posted.", 3)


def resolve_mention(args, pr):
    """Explicit choices win; otherwise compare live GUIDs before publication."""
    if args.self_review:
        return True, "none", None, None, "explicit-self-review"
    if args.mention_guid:
        try:
            guid = normalize_identity(args.mention_guid)
        except ValueError as exc:
            die(str(exc), 3)
        return False, "explicit", guid, args.mention_name or pr["name"], "explicit-mention"
    try:
        author_id = normalize_identity(pr.get("id"))
    except ValueError as exc:
        die(str(exc), 3)
    current_id = get_current_identity(args.org)
    if current_id == author_id:
        return True, "none", None, None, "authenticated-user-matches-author"
    return False, "author", author_id, args.mention_name or pr["name"], "authenticated-user-differs-from-author"


def cmd_pr_info(args):
    pr = get_pr_meta(args.pr_id, args.org)
    out = {
        "prId": int(args.pr_id),
        "project": pr["project"],
        "repo": pr["repo"],
        "repoId": pr["repoId"],
        "sourceRef": pr.get("source"),
        "targetRef": pr.get("target"),
        "title": pr.get("title"),
        "mentionGuid": pr["id"],
        "mentionName": pr["name"],
        "mentionEmail": pr.get("email"),
    }
    print(json.dumps(out, indent=2))


def compose_body(report_text, mention_guid=None, mention_name=None, greeting=None,
                 self_review=False):
    if self_review:
        return f"{SELF_REVIEW_GREETING}\n\n---\n{report_text.lstrip()}"
    if not mention_guid:
        raise ValueError("mention_guid is required unless self_review is true")
    token = f"@<{mention_guid.upper()}>"
    line = (greeting or DEFAULT_GREETING).format(mention=token, name=mention_name)
    return f"{line}\n\n---\n{report_text.lstrip()}"


def post_thread(org, project, repo, pr_id, body):
    """POST a new active thread containing one comment. Returns (threadId, commentId)."""
    payload = {
        "comments": [{"parentCommentId": 0, "content": body, "commentType": 1}],
        "status": 1,  # active
    }
    uri = (f"{org}/{project}/_apis/git/repositories/{repo}"
           f"/pullRequests/{pr_id}/threads?{API}")
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        resp = run_az([
            "rest", "--method", "POST", "--uri", uri,
            "--resource", ADO_RESOURCE,
            "--headers", "Content-Type=application/json",
            "--body", f"@{tmp}",
        ])
    finally:
        os.unlink(tmp)
    thread_id = resp.get("id")
    comments = resp.get("comments") or [{}]
    return thread_id, comments[0].get("id")


def resolve_thread(org, project, repo, pr_id, thread_id, status):
    """PATCH a thread to a resolved status (closed/fixed/...)."""
    payload = {"status": status}
    uri = (f"{org}/{project}/_apis/git/repositories/{repo}"
           f"/pullRequests/{pr_id}/threads/{thread_id}?{API}")
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        run_az([
            "rest", "--method", "PATCH", "--uri", uri,
            "--resource", ADO_RESOURCE,
            "--headers", "Content-Type=application/json",
            "--body", f"@{tmp}",
        ])
    finally:
        os.unlink(tmp)


def cmd_publish(args):
    if args.self_review and any((args.mention_guid, args.mention_name, args.greeting)):
        die("--self-review cannot be combined with --mention-guid, --mention-name, or --greeting", 3)

    report = Path(args.report)
    if not report.exists():
        die(f"Report not found: {report}", 3)
    if args.dry_run:
        report_text, autolink_fixes = fix_text(report.read_text(encoding="utf-8"))
        issues = find_issues(report_text)
    else:
        autolink_fixes = fix_file(report)
        issues = check_file(report)
        report_text = report.read_text(encoding="utf-8")
    if issues:
        details = "\n".join(
            f"{issue.line}:{issue.column} {issue.token} {issue.text}"
            for issue in issues[:20]
        )
        die(f"ADO autolink guard failed after fix:\n{details}", 3)

    pr = get_pr_meta(args.pr_id, args.org)
    self_review, mention_policy, guid, name, detection = resolve_mention(args, pr)
    status = (args.resolve_status or "closed").lower()
    if status not in RESOLVE_STATUS:
        die(f"--resolve-status must be one of {sorted(RESOLVE_STATUS)}", 3)

    body = compose_body(report_text, guid, name, args.greeting,
                        self_review=self_review)

    if args.dry_run:
        print(json.dumps({
            "dryRun": True,
            "prId": int(args.pr_id),
            "project": pr["project"], "repo": pr["repo"],
            "mentionPolicy": mention_policy,
            "selfReview": self_review,
            "selfReviewDetection": detection,
            "mentionGuid": guid, "mentionName": name,
            "priorThread": args.prior_thread,
            "resolveStatus": status,
            "autolinkFixes": autolink_fixes,
            "body": body,
            "bodyPreview": body[:600],
            "bodyBytes": len(body.encode("utf-8")),
        }, indent=2))
        return

    thread_id, comment_id = post_thread(
        args.org, pr["project"], pr["repo"], args.pr_id, body)

    resolved = False
    if args.prior_thread:
        resolve_thread(args.org, pr["project"], pr["repo"],
                       args.pr_id, args.prior_thread, status)
        resolved = True

    web_url = (f"{args.org}/{pr['project']}/_git/{pr['repo']}"
               f"/pullrequest/{args.pr_id}?discussionId={thread_id}")
    print(json.dumps({
        "threadId": thread_id,
        "commentId": comment_id,
        "mentionPolicy": mention_policy,
        "selfReview": self_review,
        "selfReviewDetection": detection,
        "mentionGuid": guid,
        "mentionName": name,
        "priorThreadResolved": resolved,
        "priorThread": args.prior_thread,
        "webUrl": web_url,
    }, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Publish code review to an ADO PR thread")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("pr-info", help="resolve PR metadata + mention target")
    p_info.add_argument("pr_id")
    p_info.add_argument("--org", default=DEFAULT_ORG)
    p_info.set_defaults(func=cmd_pr_info)

    p_pub = sub.add_parser("publish", help="post review thread + resolve prior")
    p_pub.add_argument("pr_id")
    p_pub.add_argument("--report", required=True)
    p_pub.add_argument("--org", default=DEFAULT_ORG)
    p_pub.add_argument("--mention-guid", default=None,
                       help="override automatic detection and explicitly mention this GUID")
    p_pub.add_argument("--mention-name", default=None)
    p_pub.add_argument("--greeting", default=None,
                       help="override greeting; {mention} = @<GUID> token, {name} = display name")
    p_pub.add_argument("--self-review", action="store_true",
                       help="force no mention (default: detect self-review from authenticated ADO GUID)")
    p_pub.add_argument("--prior-thread", default=None,
                       help="followup: thread id to resolve after posting the new one")
    p_pub.add_argument("--resolve-status", default=None,
                       help="status applied to prior thread (closed|fixed|wontfix|bydesign)")
    p_pub.add_argument("--dry-run", action="store_true")
    p_pub.set_defaults(func=cmd_publish)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
