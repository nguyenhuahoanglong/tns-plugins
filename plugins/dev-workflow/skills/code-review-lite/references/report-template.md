---
name: report-template
description: Exact v4.1.2 Lite report and record-v3 evidence contract
---

# Report Template

Use `.CodeReview/{safe-branch}.lite.md`; Pro escalation produces no Lite report. Use v4.1.2 fields exactly.

```markdown
# Code Review (Lite): {title}

**Date**: {YYYY-MM-DD}
**Source**: {source}
**Target**: {target}
**Files Reviewed**: {count}
**Skill**: code-review-lite v4.1.2
**Review Profile**: No Production Code | Code Tiny | Lite
**Main Runtime**: {exact attested modelId} / {exact attested effort} ({trustLevel})
**Context Manifest**: {absolute ephemeral path | n/a}

## Runtime, Scope, and Test Evidence
- **Runtime Attestation**: {absolute path} / sha256:{hash}
- **Trust**: verified | self-reported | unknown
- **Recommendation**: met | not met
- **Scope Manifest**: {absolute path} / sha256:{hash}
- **Test Evidence**: {absolute path} / sha256:{hash}
- **Lite Metadata**: {absolute .{safe-branch}.lite.review-meta.json path}
```

Add a reminder line only when `Trust` is not `verified` or `Recommendation` is `not met`:

```markdown
> Reminder: runtime not verified as recommended ({trustLevel}{, reasonCode}); for higher-confidence review switch to Claude Opus (or Sonnet 5+) at high thinking and re-run.
```

The sidecar contains `recordVersion: 3`, `skillName: code-review-lite`, `skillVersion: 4.1.2`,
`reviewProfile`, the complete runtime attestation (including `trustLevel` and, when present,
`reasonCode`), its exact `{status, sessionStatus,
overrideRecorded}` session projection, `productionAllowlist`, deterministic build/semantic-agent
evidence, and artifact `path`/`sha256`. The report runtime must equal the attestation and sidecar.
Existing sessions require `overrideRecorded: true`; fresh sessions require `false`.

Apply this v4.1.2 decision table before creating a Lite artifact:

| Triggered families | Policy / response | Outcome | Lite fields |
|---|---|---|---|
| 0 or 1 | `auto` or `ask` | Lite | `not-needed`; selected `{Family} Reviewer` or `None`; unreviewed `None` |
| 2+ | explicit-user `auto`, or `ask` accepted | Pro | no Lite artifact |
| 2+ | `ask` declined; gates pass | Bounded Lite | `pro-declined`; select Security Reviewer > Philosophy Reviewer > Performance Reviewer > Standard Reviewer; other families unreviewed |
| 2+ | `ask` declined; branch FAIL | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |
| 2+ | `ask` declined; build/test fail, timeout, or gap | Bounded Lite | `pro-declined`; selected `None`; all families unreviewed |

```markdown
## Classification
- **Files Changed**: {n}
- **Changed Lines**: {n}
- **Documentation Only**: true | false
- **Risk Triggers**: {labels or None}
- **Specialist Triggers**: {Reviewer=label or None}
- **Escalation Policy**: auto | ask
- **Escalation Policy Provenance**: omitted-default | user-authored
- **Escalation Decision**: not-needed | pro-declined
- **Selected Specialist**: Security Reviewer | Philosophy Reviewer | Performance Reviewer | Standard Reviewer | None
- **Unreviewed Risk Families**: {ordered Reviewer=trigger list | None}

## Deterministic Gates
### Branch Work Item Gate
- **Status**: PASS | WARN | FAIL | SKIPPED
- **Branch**: {value}
- **Work Item**: {value}
- **Source**: {value}
- **Reason**: {bounded evidence}

### Build Gates
| Repo | Status | Command | Exit | Errors | Warnings | Log / Reason |
|---|---|---:|---:|---:|---:|---|
| `{repo}` | {status} | `{command}` | {n or n/a} | {n} | {n} | `{log}` / {reason} |

- **Test Gate**: PASS | ADVISORY (use-unit-testing) | BLOCKED (fail|timeout|gap) | NOT APPLICABLE (no-production-code)
```

`Escalation Policy` defaults to `ask` when omitted. For two or more families it pauses for the
user; only explicit-user `auto` routes immediately to Pro. For one/zero family Lite, use
`not-needed`, the selected `{Family} Reviewer` where applicable, and `None` unreviewed. For a declined
multi-family ask, preserve trigger order for `Unreviewed Risk Families`; successful bounded Lite
selects exactly one persisted value by Security Reviewer > Philosophy Reviewer > Performance
Reviewer > Standard Reviewer. For every Lite route, branch FAIL selects `None` and starts no
semantic agents; build/test fail, timeout, or gap selects `None`, runs only Requirement Validator,
and leaves every triggered family unreviewed. Pro auto/ask-accepted paths write neither Lite report
nor sidecar.

The sidecar mirrors the four fields exactly as `escalationPolicy`, `escalationDecision`,
`selectedSpecialist`, and `unreviewedRiskFamilies`; `selectedSpecialist` must be exactly `Security
Reviewer`, `Philosophy Reviewer`, `Performance Reviewer`, `Standard Reviewer`, or `None`. It
retains `recordVersion: 3`.

Test evidence uses `executions[]` and retains every run across repositories. Each execution records
repo, command, status, exit code, and passed/failed/skipped counts. No Production Code retains its
report, sidecar, runtime/scope/test artifacts, and a `not-applicable` test artifact, but has no
worktree, context, build/test execution, semantic agents, or findings. Code Tiny uses zero semantic
children. Lite runs Requirement Validator and at most one specialist only after gates; branch FAIL
runs no semantic agents, while test/build failure, timeout, or gap leaves Requirement Validator
only. Missing direct tests for changed
symbols adds exactly:

```markdown
- **Unit-Test Advisory**: use-unit-testing
```

```markdown
## Semantic Agents
### Triggered
- {agent/runtime/reason, or None}
### Agent Usage
| Agent | Runtime | Context Mode | Input Tokens | Cache Read | Cache Write | Output Tokens |
|---|---|---|---:|---:|---:|---:|
| {agent} | `{runtime}` | isolated manifest | {n or not exposed} | {n or not exposed} | {n or not exposed} | {n or not exposed} |

## Requirement Evidence
| Requirement | Status | Evidence |
|---|---|---|
| {criterion} | Addressed / Partial / Missing / Not verifiable | `{production-file}:{line}` |

## Behavior Preservation and Collateral Impact
| Behavior | Classification | Base -> New | Impact Trace | Preservation Evidence | Status |
|---|---|---|---|---|---|
| {behavior} | Direct requirement / Necessary collateral / Unrelated / Unclear | {delta} | {trace} | `{test-or-doc}:{line}` | Preserved / Regressed / Unproven |

- **Collateral Impact**: {bounded result or None}
- **Scope Drift**: {bounded result or None}

## Detailed Findings
None.
```

Each finding uses a `Target` bullet whose value is an allowlisted `{production-file}:{line}`. Tests/docs are citable evidence, not
finding targets. Pro escalation writes no Lite report or sidecar. Run the verifier after the existing
ADO autolink guard; use `--sidecar` only when the report cannot carry its metadata path.
