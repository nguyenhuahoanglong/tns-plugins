---
name: report-template
description: Exact v4 Lite report and record-v3 evidence contract
---

# Report Template

Use `.CodeReview/{safe-branch}.lite.md`; escalation produces no Lite report. Use v4 fields exactly.

```markdown
# Code Review (Lite): {title}

**Date**: {YYYY-MM-DD}
**Source**: {source}
**Target**: {target}
**Files Reviewed**: {count}
**Skill**: code-review-lite v4.0.0
**Review Profile**: No Production Code | Code Tiny | Lite
**Main Runtime**: {exact attested modelId} / {exact attested effort}
**Context Manifest**: {absolute ephemeral path | n/a}

## Runtime, Scope, and Test Evidence
- **Runtime Attestation**: {absolute path} / sha256:{hash}
- **Scope Manifest**: {absolute path} / sha256:{hash}
- **Test Evidence**: {absolute path} / sha256:{hash}
- **Lite Metadata**: {absolute .{safe-branch}.lite.review-meta.json path}
```

The sidecar contains `recordVersion: 3`, `skillName: code-review-lite`, `skillVersion: 4.0.0`,
`reviewProfile`, the complete runtime attestation, its exact `{status, sessionStatus,
overrideRecorded}` session projection, `productionAllowlist`, deterministic build/semantic-agent
evidence, and artifact `path`/`sha256`. The report runtime must equal the attestation and sidecar.
Existing sessions require `overrideRecorded: true`; fresh sessions require `false`.

```markdown
## Classification
- **Files Changed**: {n}
- **Changed Lines**: {n}
- **Documentation Only**: true | false
- **Risk Triggers**: {labels or None}
- **Specialist Triggers**: {Reviewer=label or None}

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

Test evidence uses `executions[]` and retains every run across repositories. Each execution records
repo, command, status, exit code, and passed/failed/skipped counts. No Production Code retains its
report, sidecar, runtime/scope/test artifacts, and a `not-applicable` test artifact, but has no
worktree, context, build/test execution, semantic agents, or findings. Code Tiny uses zero semantic
children. Lite runs Requirement Validator and at most one specialist only after gates; test/build
failure, timeout, or gap leaves Requirement Validator only. Missing direct tests for changed
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
finding targets. Escalation writes no Lite report or sidecar. Run the verifier after the existing
ADO autolink guard; use `--sidecar` only when the report cannot carry its metadata path.
