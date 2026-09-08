---
name: code-reviewer
description: Lite adapter for isolated baseline code-reviewer dispatch and compact report synthesis
---

# Code Reviewer Baseline Adapter

Use one isolated `code-reviewer` instance in `baseline` mode. It maps direct requirements and behavior changes, then reviews general implementation quality. This adapter supplies Lite context and output rules; central agent contract owns review method.

## Dispatch

Provide production allowlist, evidence paths, direct requirements when available, diff, context manifest, and preflight path/token. In isolated scope supplied diff is authoritative: no Git, edits, nesting, or findings outside allowlist.

Append dynamic fields in this order:

```text
Context path: {absolute-context-path}
Mode/role: {work-item|regression-only|baseline}
Preflight path: {absolute-preflight-path}
Preflight token: {token}
```

Dispatch with `Task(subagent_type="code-reviewer", prompt="...", description="...")` at `opus / configured medium`. Require `Child Read: PASS {token}`.

## Synthesis

Keep forward AC mapping and reverse behavior mapping. Preserve `Direct requirement`, `Necessary collateral`, `Unrelated`, `Unclear`, plus `Preserved`, `Regressed`, and `Unproven`. Missing tests remain `use-unit-testing` advisory, never defect. Risk specialist output adds only its lens; it does not repeat baseline mapping.
