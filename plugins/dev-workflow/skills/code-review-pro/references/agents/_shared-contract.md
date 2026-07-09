---
name: shared-contract
description: Shared preflight and finding-output contract for the security, performance, philosophy, standard, and requirement-validator agents
---

# Shared Agent Contract

Shared with your role prompt: this defines what every child agent shares; the role prompt defines the lens.

## Preflight

Read the sentinel path first, verify its token, emit `Child Read: PASS {token}` as the first line — or `Child Read: FAIL` and stop without analyzing on a missing/unreadable/mismatched token.

Then read every supplied path: role prompt, worktree root, diff file, changed files your lens covers. Never run git commands. Read-only.

## Output Skeleton

Group findings by file; within a file, order Critical -> High -> Medium -> Low. Inline severity tag on every finding — never a section heading.

- **Critical/High**: multi-line (title, `file:line`, evidence, impact, suggestion — role prompt names exact fields).
- **Medium/Low**: one line (severity tag, `file:line`, title, inline suggestion).
- Every finding cites `file:line` plus **Confidence** (`High | Medium | Low`); Medium/Low is accepted on this evidence without re-verification, so confidence must be honest.
- End with **Clean files**: `{n}` of `{total}` — no file names.
