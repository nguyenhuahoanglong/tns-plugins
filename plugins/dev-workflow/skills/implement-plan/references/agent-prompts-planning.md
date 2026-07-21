# Planning Agent Prompts

All dispatches are read-only and occur before approval.

## Explorer

Dispatch 1–3 distinct focuses after reading applicable `AGENTS.md`:

```text
Map context for: {feature summary}; project: {project-root}; focus: {specific question}.
Read applicable AGENTS.md and relevant docs.
Rules: read-only; do not edit, install, format, build, or run long tests. Return concise file/line
evidence, reusable patterns, quality/test assessment evidence, risks, and task boundaries.
```

Main agent personally reads critical files identified by reports.

## Architect

Use zero for trivial one-file changes, one for normal work, up to three distinct perspectives for
complex/multi-area work.

```text
Design implementation for: {feature summary}; project: {project-root}.
Read applicable AGENTS.md and cited Phase 0 files. Requirements/ACs: {locked criteria}; findings:
{evidence}. Name files, feature-slice boundaries, dependencies, interfaces, verification, trade-offs.
Rules: read-only; no edits, installs, builds, or tests; return one executable proposal.
```

## Plan quick-check

For 3+ tasks, send one fresh-eyes agent:

```text
Read ONLY plan file {plan-path}. For each task return at most "Task N: not executable because X", or
"All tasks executable." Do not read other files, edit, or suggest anything beyond executability.
```

Main agent fixes every gap before approval.
