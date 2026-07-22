---
name: followup-review
description: Strict v3 follow-up detection, delta reclassification, finding carry-forward, and sidecar schema
---

# Follow-up Review

Follow-ups use the same runtime, scope, test, classifier, actor, and verifier contract as initial reviews.

## Detection

Require the report and sidecar. Accept only a parsed `recordVersion: 3`, `skillName: code-review-pro`, `skillVersion: 3.0.2` record with all retained provenance and three contained, hash-bound artifact references. A missing/invalid/pre-v3 record requires fresh full-scope classification; never upgrade a legacy record in place.

Recompute the normalized scoped-diff SHA-256:

- PR/branch: `{scopeBase}..HEAD`
- staged: `git diff --cached --binary`
- working: `git diff HEAD --binary` plus sorted untracked path/content hashes
- files: the original base and sorted explicit paths

Stop without new review work only when the recomputed fingerprint equals `diffFingerprint`. `HEAD == reviewedCommit` is insufficient for staged/working content.

## Delta

After running the runtime preflight (advisory) and session classification, diff `{reviewedCommit}..HEAD`, create new scope/test artifacts, and classify only the delta:

- No-production-code: branch gate when applicable, no worktree/build/test/semantic actor/finding.
- Tiny: one Build Validator per repository, then Tiny main all-lens review.
- Pro: one Build Validator per repository, Requirement Validator, then only classified specialists.

Re-evaluate requirement context if it changed or regression-only mode can now resolve a direct item. For each prior finding, re-read its production path and mark Resolved, Partial, Unresolved, or Regressed. Remove resolved findings, carry unresolved/partial findings with stable slugs, and allocate new slugs only for new causes.

## Record v3

This abridged shape lists every required field. Artifact `path` values are contained relative paths beside the sidecar; `sha256` is the digest of the referenced bytes.

```json
{
  "recordVersion": 3,
  "skillName": "code-review-pro",
  "skillVersion": "3.0.2",
  "reviewProfile": "Pro",
  "reviewKind": "follow-up",
  "iteration": 2,
  "reviewedAt": "ISO-8601",
  "runtimeAttestation": {"path": ".feature.runtime.json", "sha256": "..."},
  "scopeManifest": {"path": ".feature.scope.json", "sha256": "..."},
  "testEvidence": {"path": ".feature.tests.json", "sha256": "..."},
  "session": {"status": "fresh", "overrideRecorded": false},
  "runtime": {
    "main": "gpt-5.6-terra / medium",
    "trustLevel": "verified",
    "build": "haiku / default",
    "requirement": "opus / default",
    "specialists": "sonnet / default"
  },
  "classifier": {
    "filesChanged": 4,
    "changedLines": 140,
    "scopeStatus": "pass",
    "riskTriggers": ["api-contract"],
    "specialistTriggers": {"Philosophy Reviewer": ["api-contract"]}
  },
  "productionFiles": ["src/file.cs"],
  "evidenceFiles": ["tests/file-tests.cs"],
  "excludedFiles": ["dist/bundle.js"],
  "reviewedFiles": ["src/file.cs"],
  "reposReviewed": ["repo"],
  "testGate": {"status": "PASS", "blocking": false},
  "blockingValidations": [],
  "findings": [
    {"action": "Must Fix", "file": "src/file.cs", "line": 42, "evidence": ["tests/file-tests.cs"]}
  ],
  "branchWorkItemGate": {
    "status": "PASS",
    "branch": "US/1234-short-slug",
    "prefix": "US",
    "workItemId": "1234",
    "expectedType": "User Story",
    "actualType": "User Story",
    "title": "Example story",
    "state": "Active",
    "source": "pr",
    "reason": "Branch prefix and ADO work item type match"
  },
  "triggered": [
    "Branch Work Item Gate(haiku / default; branch work item convention)",
    "Build Validator[repo](haiku / default; code build)",
    "Requirement Validator(opus / default; work-item)",
    "Philosophy Reviewer(sonnet / default; api-contract)"
  ],
  "skipped": [
    "Security Reviewer(no security trigger)",
    "Performance Reviewer(no performance trigger)",
    "Standard Reviewer(no standards trigger)"
  ],
  "requirementMode": "work-item",
  "reviewedCommit": "sha",
  "targetBranch": "develop",
  "workItemId": 1234,
  "scopeType": "pr",
  "scopeBase": "origin/develop",
  "diffFingerprint": "sha256:...",
  "prOnlyMode": false,
  "prMergePreview": true,
  "mergePreviewStrategy": "server-merge",
  "jsDepsStrategy": "install",
  "standardsPaths": ["AGENTS.md"],
  "exemplarMap": {}
}
```

The scope arrays must exactly equal the scope artifact projections, with no duplicates or overlap. The test artifact contains `discovery` plus non-empty, unique-repository `executions[]`; fail/timeout runs require blocked report/test-gate routing. Triggered/skipped actors must match the report and use recorded child runtimes. PR-only implies `scopeType: pr`; PR scope retains the merge-preview strategy; `skip | mixed` dependencies require a `JS-SKIPPED` build row.

Initial reviews use the same schema with `reviewKind: initial` and `iteration: 1`. Follow-ups require `iteration >= 2`.

## Finish

Regenerate the full report and sidecar, run the ADO guard and `scripts/verify_output.py`, then remove only verified temporary worktrees/diffs. Preserve report, sidecar, and all referenced evidence artifacts.
