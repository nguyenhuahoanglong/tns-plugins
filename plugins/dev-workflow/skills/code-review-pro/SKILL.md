---
name: code-review-pro
description: Adaptive production-code review for PRs, branches, staged changes, and follow-ups. Use when runtime-attested Tiny or Pro validation and a verified report are required.
version: 3.0.1
---

# Code Review Pro

Review only production code. Tests and documents are evidence; generated, vendor, and binary files are excluded. Route explicit quick/lite reviews to `code-review-lite`. Direct user requests use `Invocation Source: direct-user` and `Lite Escalation Consent: n/a`. Lite-originated Pro requires `user-confirmed` or `explicit-auto` consent; missing consent is a hard stop before Pro execution.

## Mandatory preflight

Before reading repository files, git state, diffs, or classifying scope, run the shared harness from `<skill-dir>/scripts/review_harness`:

1. Run `runtime-preflight` for the active host/session. Trust only Codex rollout metadata or the Claude status-line payload plus transcript cross-check. Record exact `modelId` and `effort`; never use settings, display names, self-report, or `not exposed`.
2. Hard-stop if runtime status is not `pass`. Run session evaluation next. Pause on `confirmation-required`; proceed only after explicit user confirmation and record `overrideRecorded: true`. Do not read the repository while blocked or paused.
3. Save the structured runtime/session result as a JSON artifact in `.CodeReview/` before Gather. This is the runtime attestation.

Main runtime must satisfy shared `evaluate_runtime`; child Luna/low Build Validator runtime is not the main-review authority. Announce the attested model/effort and planned actors before dispatch.

## Workflow

### 1. Gather and scope

Read `references/review-workflow.md`. Resolve PR/branch/staged/working/files paths, then save the changed-path list. Build and persist the scope manifest before classifier or worktree creation:

```text
python <skill-dir>/scripts/review_harness/__main__.py scope-manifest {changed paths}
```

Only `productionFiles` are reviewed, counted, classified, passed to semantic agents, or allowed as finding targets. `evidenceFiles` inform findings only; `excludedFiles` are never review subjects. Retain PR, dependency, branch gate, repository, and follow-up provenance.

If the manifest has no production files, select **No-production-code**. Run only applicable branch validation; do not create worktrees, run builds/tests, dispatch semantic agents, or emit findings. Report the terminal outcome and artifacts.

For production scope, discover direct/affected tests from changed symbols, persist discovery, and run deterministic test commands before semantic dispatch. Persist command, exit status, duration, counts, and bounded logs. `use-unit-testing` is the exact advisory when direct tests are missing; it is never a finding. A failed/timeout test is blocking evidence; do not inspect tests as a finding target.

### 2. Classify and execute

Read `references/adaptive-classifier.md`. Choose **Tiny** only for <=3 production files, <=100 changed lines, and no risk trigger; otherwise choose **Pro**. Classifier counts exclude evidence/excluded paths.

Run branch validation where applicable. For Tiny, run one Build Validator per repo and then main all-lens review. For Pro, run Build Validator(s), Requirement Validator, and only recorded risk specialists. A branch gate failure stops later semantic dispatch; a build failure is blocking evidence but Requirement validation may still run if production code is readable.

Every semantic dispatch receives: persistent diff path, production allowlist, evidence paths, manifest path, test-evidence path, and role prompt. An out-of-allowlist finding is invalid and must be removed. Use `references/agents/_shared-contract.md`; child agents do no git commands.

### 3. Synthesize

Read `references/report-template.md` and `references/analysis-framework.md`. Write `.CodeReview/{safe-branch}.md` and v3 `.CodeReview/.{safe-branch}.review-meta.json`. The sidecar contains `recordVersion: 3`, `invocation: {source, liteConsent}`, retained provenance, exact `runtimeAttestation`, `scopeManifest`, and `testEvidence` references (`path`, `sha256`), scope lists, reviewed production files, test routing, validation blockers, and finding objects.

## Verify Output

Run the ADO autolink guard, then run the deterministic verifier before declaring completion:

```text
python <skill-dir>/scripts/verify_output.py ".CodeReview/{safe-branch}.md" --sidecar ".CodeReview/.{safe-branch}.review-meta.json"
```

Fix every FAIL. Preserve reports, sidecar, and evidence artifacts; remove temporary worktrees/diffs only after verification.

## Follow-up and enforcement

Use `references/followup-review.md` for follow-ups; invalid/v1/v2 records require fresh full-scope classification. Follow `references/feedback-reception.md` before acting on review feedback.

- No repository read precedes passing runtime/session preflight.
- No-production-code has no worktree, build, test, semantic agent, or finding.
- Findings must target `productionFiles`; tests/docs can only be cited as evidence.
- Do not sync/install this skill during a review.
