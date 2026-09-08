---
name: code-reviewer
description: Pro baseline adapter for requirement/behavior evidence and implementation-quality review
---

# Code Reviewer Baseline

Use one `code-reviewer` in `baseline` mode for Pro. It owns direct-AC mapping, reverse behavior classification, regression-only preservation review, and general implementation-quality findings.

Provide the persistent diff, production allowlist, evidence paths, scope/test artifacts, requirement context, worktree, and `_shared-contract.md`. Supplied diff is authoritative; no Git, edits, nesting, or findings outside allowlist.

Dispatch with `Task(subagent_type="code-reviewer", prompt="...", description="...")` at `opus / default`. Require `Child Read: PASS {token}`. Risk-focused `code-reviewer` instances retain their named Security, Performance, Philosophy, or Standard lens and must not repeat full baseline mapping.
