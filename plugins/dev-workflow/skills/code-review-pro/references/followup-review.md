---
name: followup-review
description: v2 follow-up records, delta reclassification, stable finding carry-forward, and sidecar schema
---

# Follow-up Review

Follow-up uses the same classifier and runtime contract as an initial review.

## Detection

Require both:

- `.CodeReview/{safe-branch}.md`
- `.CodeReview/.{safe-branch}.review-meta.json`

The sidecar must parse and contain `recordVersion: 2`, `skillName: code-review-pro`, `skillVersion: 2.2.0`, `scopeType`, `scopeBase`, and `diffFingerprint`. If missing, invalid, or v1, run a fresh full-scope review and write v2 records.

Recompute SHA-256 over the same normalized scoped diff:

- PR/branch: `{scopeBase}..HEAD`
- staged: `git diff --cached --binary`
- working: `git diff HEAD --binary` plus sorted untracked path/content hashes
- explicit files: same original base and sorted file scope

Stop without agents/worktree only when the recomputed fingerprint equals `diffFingerprint`. `HEAD == reviewedCommit` alone is insufficient because staged/working changes may exist.

## Delta

Diff `{reviewedCommit}..HEAD`, collect file/line counts, and classify that delta through `adaptive-classifier.md`. Announce the new profile and every trigger/skip before execution.

- Docs-only delta: zero agents; review documentation inline.
- Tiny delta: one Build Validator per repo; main agent verifies prior findings and reviews all lenses.
- Pro delta: Build Validator(s), Requirement Validator always, then only triggered specialists.

Use the prior report as context. Re-evaluate work-item context if direct requirements changed or prior mode was regression-only and a work item is now available.

## Resolution

For each prior open finding:

- **Resolved**: fixed code proves issue gone.
- **Partial**: improvement does not remove core issue.
- **Unresolved**: delta does not address it.
- **Regressed**: attempted fix introduces or exposes another defect.

Re-read code for every resolved Must Fix. Carry untouched findings forward. Remove resolved findings. Preserve slugs for unresolved/partial findings; allocate new slugs only for genuinely new issues.

## v2 Sidecar

```json
{
  "recordVersion": 2,
  "skillName": "code-review-pro",
  "skillVersion": "2.2.0",
  "reviewProfile": "Pro",
  "reviewKind": "follow-up",
  "classifier": {
    "filesChanged": 4,
    "changedLines": 140,
    "docsOnly": false,
    "riskTriggers": ["api-contract"],
    "specialistTriggers": {
      "Philosophy Reviewer": ["api-contract"]
    }
  },
  "branchWorkItemGate": {
    "status": "PASS",
    "branch": "US/1234-short-slug",
    "prefix": "US",
    "workItemId": "1234",
    "expectedType": "User Story",
    "actualType": "User Story",
    "title": "Example story",
    "state": "Active",
    "source": "branch",
    "reason": "Branch prefix and ADO work item type match"
  },
  "runtime": {
    "main": "gpt-5.5/xhigh",
    "build": "haiku / default",
    "requirement": "opus / default",
    "specialists": "sonnet / default"
  },
  "triggered": [
    "Branch Work Item Gate(haiku / default; branch work item convention)",
    "Build Validator[repo](haiku / default; code build)",
    "Requirement Validator(opus / default; work-item)",
    "Philosophy Reviewer(sonnet / default; api-contract)"
  ],
  "skipped": ["Security Reviewer(no security trigger)"],
  "reposReviewed": ["repo"],
  "requirementMode": "work-item",
  "scopeType": "pr",
  "scopeBase": "origin/develop",
  "diffFingerprint": "sha256:...",
  "reviewedCommit": "sha",
  "targetBranch": "develop",
  "workItemId": 1234,
  "prOnlyMode": false,
  "prMergePreview": false,
  "mergePreviewStrategy": "server-merge",
  "jsDepsStrategy": "install",
  "standardsPaths": ["AGENTS.md"],
  "exemplarMap": {},
  "reviewedFiles": ["src/file.cs"],
  "iteration": 2,
  "reviewedAt": "ISO-8601"
}
```

Initial reviews use the same schema with `reviewKind: initial` and `iteration: 1`. `reviewProfile` records the profile used for that iteration.

The four fields `prOnlyMode`, `prMergePreview`, `mergePreviewStrategy`, and `jsDepsStrategy` are additive at `recordVersion: 2`; existing follow-up reviews that pre-date v2.1.0 should be treated as missing these fields and a fresh full-scope review should be run. `scopeBase` and `diffFingerprint` semantics are unchanged by merge preview â€” the fingerprint is still computed over the normalized `{scopeBase}..HEAD` diff.

## Finish

Regenerate the complete report, update header/profile/trigger fields, run ADO guard, run `scripts/verify_output.py`, update sidecar, then clean the repo-local worktrees and delta file.
