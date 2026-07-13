# Planning Agent Prompts

All dispatches here are read-only and occur before approval.

## Phase 0 explorer

Dispatch 1-3 tool-native explorers per `plan-analysis.md`:

```text
Map codebase context for: {feature/change summary}
Project: {project-root}. Read applicable AGENTS.md and relevant docs.
Focus: {one specific area/question}

Rules:
- Read-only. No edits, installs, formatting, builds, or long tests.
- Return relevant files, patterns to reuse, quality-assessment evidence, risks/questions, and task boundaries.
- Cite file paths and useful line anchors. Keep output concise.
```

When parallel, give distinct focuses: implementation patterns, dependency surface, or quality/test
conventions. Main agent reads critical files after reports.

## Phase 1 architect

Use zero for trivial one-file change, one for standard change, up to three distinct perspectives for
complex/multi-area change. Claude Code uses Plan agent; Codex uses explorer with design brief.

```text
Design implementation approach for: {feature/change summary}
Project: {project-root}. Read applicable AGENTS.md and relevant docs.
Phase 0 findings: {files, patterns, constraints, risks}
Requirements and Acceptance Criteria: {locked criteria}

Name concrete files, feature-slice task boundaries, dependency order, interfaces, verification, and
trade-offs.

Rules:
- Read-only. No edits, installs, formatting, builds, or tests.
- Return concise proposal. Do not leave unresolved implementation options.
```

Main agent reconciles proposals into one approach matching locked scope and ACs.

## Plan quick-check

Run one cheap fresh-eyes agent only for plans with 3+ tasks:

```text
Read ONLY plan file at {plan-path}. For each task, decide whether you could execute it from plan text
without asking a question. Return at most short list of "Task N: not executable because X", or
"All tasks executable." Keep response under 15 lines. Do not read other files or suggest changes
beyond executability gaps.
```

Main agent fixes every gap before Approval Gate.
