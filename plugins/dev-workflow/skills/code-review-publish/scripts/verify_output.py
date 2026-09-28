#!/usr/bin/env python3
"""
verify_output.py — guardrail for code-review-publish output.

Checks the deterministic acceptance criteria that don't require hitting ADO:

  PR body shape   verify_output.py body <composed-body.txt|dry-run.json>
      - accepts author-mention greeting or neutral self-review label
      - has the `---` separator on its own line right after the greeting
      - the report follows (non-empty body after the separator)

  PR state file   verify_output.py state <.pr-publish.json>
      - required keys present: prId, threadId, commentId, iteration
      - accepts legacy mentionGuid state or explicit mentionPolicy/selfReview state
      - on followup (iteration > 1): priorThreadIds[] is non-empty

Use after a publish (or on the full `body` field in --dry-run JSON) to confirm the output
matches the contract before trusting it. Network-dependent checks (mention
renders, dev notified, prior thread resolved) are listed in
references/pr-publish.md and verified in the PR UI.

Exit codes: 0 = all checks pass, 1 = a check failed, 2 = IO/usage error.
"""

import sys
import re
import json
from pathlib import Path

from ado_autolink_guard import find_issues

MENTION_RE = re.compile(r"@<[0-9A-Fa-f-]{36}>")
GREETING_RE = re.compile(r"^Hi @<[0-9A-Fa-f-]{36}>,.*:\s*$")
GUID_RE = re.compile(r"^[0-9A-Fa-f-]{36}$")
SELF_REVIEW_GREETING = "Code review result:"


def fail(checks):
    print("=== VERIFY: code-review-publish ===")
    ok = True
    for passed, label in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
        ok = ok and passed
    print(f"\nResult: {'all checks pass' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


def verify_body(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("body"), str):
        text = payload["body"]
    lines = text.splitlines()
    first = lines[0] if lines else ""
    has_sep = any(l.strip() == "---" for l in lines[:4])
    try:
        sep_idx = next(i for i, l in enumerate(lines) if l.strip() == "---")
        report = "\n".join(lines[sep_idx + 1:]).strip()
    except StopIteration:
        report = ""
    unsafe_refs = find_issues(report)
    mentioned = bool(GREETING_RE.match(first)) and bool(MENTION_RE.search(first))
    self_review = first == SELF_REVIEW_GREETING and not MENTION_RE.search(first)
    fail([
        (mentioned or self_review,
         "supported author-mention or self-review introduction present"),
        (self_review or bool(MENTION_RE.search(first)),
         "mention policy matches introduction"),
        (has_sep, "'---' separator within the first lines"),
        (len(report) > 0, "report content present after separator"),
        (len(unsafe_refs) == 0, "report has no accidental ADO #number autolinks"),
    ])


def verify_state(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ["prId", "threadId", "commentId", "iteration"]
    checks = [(k in data and data[k] not in (None, ""), f"state has '{k}'") for k in required]
    if "mentionPolicy" not in data:
        # Previous states always stored a mention GUID; keep those readable.
        checks.append((data.get("mentionGuid") not in (None, ""),
                       "legacy state has 'mentionGuid'"))
    else:
        policy = data.get("mentionPolicy")
        self_review = data.get("selfReview")
        checks.append((policy in ("author", "explicit", "none"),
                       "state has supported 'mentionPolicy'"))
        checks.append((isinstance(self_review, bool), "state has boolean 'selfReview'"))
        if policy == "none":
            checks.append((self_review is True, "self-review policy sets selfReview=true"))
            checks.append((data.get("mentionGuid") is None,
                           "self-review state has null 'mentionGuid'"))
        elif policy in ("author", "explicit"):
            checks.append((self_review is False, "mention policy sets selfReview=false"))
            checks.append((isinstance(data.get("mentionGuid"), str)
                           and bool(GUID_RE.fullmatch(data["mentionGuid"])),
                           "mentioned state has GUID 'mentionGuid'"))
    if data.get("iteration", 1) and data["iteration"] > 1:
        prior = data.get("priorThreadIds") or []
        checks.append((len(prior) > 0, "followup state records priorThreadIds[]"))
    fail(checks)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("body", "state"):
        print("usage: verify_output.py body <body.txt> | state <.pr-publish.json>",
              file=sys.stderr)
        sys.exit(2)
    mode, path = sys.argv[1], sys.argv[2]
    if not Path(path).exists():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(2)
    (verify_body if mode == "body" else verify_state)(path)


if __name__ == "__main__":
    main()
