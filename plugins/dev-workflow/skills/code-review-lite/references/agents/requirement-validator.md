---
name: requirement-validator
description: Lite adapter for isolated requirement-validator dispatch and compact report synthesis
---

# Requirement Validator Adapter

The central `requirement-validator` agent owns the review methodology. This reference only adapts Lite's context manifest, isolated dispatch tail, and compact output into the v3 report. Do not copy or override the central behavior-classification rules here.

## Stable Dispatch Contract

Provide these instructions before all variable values:

```text
Run a read-only Lite requirement review from the supplied context manifest.
Treat requirements.direct as binding only when its source is available.
Treat requirements.parentContext as context, never acceptance criteria.
Use the manifest changedFiles and diffPath as the review boundary.
Read unchanged code only for affected caller/consumer/event/state/config traces.
Run no git commands and make no edits.
Return compact, material-only requirement, behavior-preservation, collateral-impact, and finding records.
```

Append only this dynamic tail, in this order:

```text
Context path: {absolute-context-path}
Mode/role: {work-item|regression-only}
Preflight path: {absolute-preflight-path}
Preflight token: {token}
```

Dispatch with exact placeholder `Task(subagent_type="requirement-validator", prompt="...", description="...")` and runtime `opus / default`. Missing `Child Read: PASS {token}` invalidates the result.

## Output Adaptation

Map central output into the Lite report without widening claims:

| Central record | Lite destination | Adaptation |
|---|---|---|
| Criteria Mapping | Requirement Evidence | `Unclear` -> `Not verifiable`; preserve evidence |
| Behavior Deltas | Behavior Preservation and Collateral Impact | Preserve classification, base/new, trace, evidence, status |
| Scope Assessment | Collateral Impact / Scope Drift | Keep parent/collateral separate from direct criteria |
| Findings | Detailed Findings | Main agent re-verifies location and impact |
| Summary counts | Reviewer Notes | Include only when useful for omissions/limits |

The four behavior classes remain exact: `Direct requirement`, `Necessary collateral`, `Unrelated`, `Unclear`. The preservation states remain exact: `Preserved`, `Regressed`, `Unproven`. Never promote collateral behavior into a criterion, convert missing tests into a defect, or report a regression without exposed-path evidence.

## Failure Handling

- Preflight failure: record semantic dispatch failure; use no findings from the child.
- Invalid/missing manifest field: record `Not verifiable`; do not fetch more work-item context.
- Build failure/gap: still run this Requirement Validator after the branch gate allows review.
- Token/cache counters: copy exposed non-negative integers; otherwise write exact `not exposed`.
