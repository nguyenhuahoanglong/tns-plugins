---
name: adaptive-classifier
description: Deterministic Docs-only, Tiny, and Pro classification plus risk-to-specialist trigger mapping
---

# Adaptive Classifier

Classify both initial reviews and follow-up deltas with this same contract.

## Inputs

Record:

- `filesChanged`: number of changed files in scope
- `changedLines`: added + removed lines from diff shortstat
- `docsOnly`: whether every changed file is documentation
- `riskTriggers`: every applicable trigger below, with one-sentence evidence
- `specialistTriggers`: map of reviewer name to triggering labels/evidence

Treat Markdown, reStructuredText, AsciiDoc, and plain text under documentation paths as documentation. A manifest, executable sample, generated contract, configuration file, schema, or code-bearing notebook is not docs-only.

## Profile Decision

1. **Docs-only** when `docsOnly=true`. Spawn zero agents.
2. **Tiny** only when all are true:
   - `docsOnly=false`
   - `filesChanged <= 3`
   - `changedLines <= 100`
   - no risk trigger
3. **Pro** otherwise. If evidence is ambiguous, select Pro and record `uncertain-impact`.

Thresholds are inclusive. Renames count as changed files. Added and removed lines both count.

## Mandatory Pro Risk Triggers

Any one trigger forbids Tiny, regardless of size:

| Trigger | Evidence examples |
|---|---|
| `shared-behavior` | shared/public helper, reused service, cross-feature behavior, common library |
| `api-contract` | route, public signature, DTO, serialization, message/event contract |
| `schema-data-contract` | DB/Dataverse schema, migration, persisted shape, mapping contract |
| `auth-security-boundary` | authentication, authorization, permissions, secrets, trust boundary, input validation |
| `dependency-build-surface` | package/SDK/runtime version, lockfile, build tool, dependency registration |
| `async-lifecycle` | async flow, cancellation, concurrency, retries, disposal, subscriptions, component lifecycle |
| `state-management` | persisted/shared/client state, cache, mutation ordering, event-driven state |
| `config-runtime` | runtime flags, environment config, deployment settings, DI/wiring |

Also record `large-change` when thresholds fail and `uncertain-impact` when impact cannot be proven small.

## Specialist Triggers

Requirement Validator is not a specialist and always runs in Pro.

| Specialist | Trigger when diff affects |
|---|---|
| Security Reviewer | `auth-security-boundary`; dependency/config change with security exposure; untrusted input, crypto, secrets, permissions |
| Performance Reviewer | `async-lifecycle`; concurrency, query/loop hot paths, batching, caching, resource ownership, scale-sensitive state |
| Philosophy Reviewer | `shared-behavior`, `api-contract`, `schema-data-contract`, `state-management`, or `config-runtime` with architecture/ownership/abstraction impact |
| Standard Reviewer | explicit standards-sensitive change, new pattern/folder/language construct, build/config convention, or dominant-exemplar divergence risk |

Size alone (`large-change`) triggers no specialist. Requirement Validator covers correctness/regression; spawn a specialist only when its own row has evidence.

## Announcement Contract

Before dispatch, state profile, counts, every classifier trigger, every specialist trigger, and every skipped agent with reason. Persist specialist triggers as `{"Performance Reviewer": ["async-lifecycle"]}` style data. Use the same labels in report and sidecar. Do not silently add or omit an agent after announcement; if later evidence changes triggers, announce the update before dispatch.
