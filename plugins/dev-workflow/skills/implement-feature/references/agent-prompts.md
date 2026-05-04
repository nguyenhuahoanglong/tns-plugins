# Agent Dispatch Prompts

Templates for Phases 2-6. Fill placeholders and dispatch via `Agent` tool. Spawn independent agents in a **single message** for parallel execution.

## Context Size Guidelines

| Content | Rule |
|---------|------|
| **Requirement summary** (implementer, reviewer) | Summary + relevant FRs + design decisions for WP scope. ~500 words max. |
| **Full requirement** (plan, QA) | Entire file if ≤2000 words; summarize if larger, preserving all ACs. |
| **Git diff** (reviewer) | Inline if ≤200 lines; otherwise instruct the agent to run `git diff` itself. |

---

## Phase 2 — Plan Agent

```
Agent({
  subagent_type: "Plan",
  description: "Plan feature: {feature-name}",
  prompt: `
Create an implementation plan.

## Requirement
{full requirement file content — see context size guidelines}

## Codebase Context
{Explore agent findings — structure, files, patterns, stack}

## Instructions
1. Read the project's AGENTS.md and coding standards
2. Break into WPs grouped by waves. No two WPs in a wave may touch overlapping files.
3. Each WP: name, file list, description, which ACs it addresses
4. Write to {artifact-folder}/{feature-name}-plan.md (filename embeds the feature name for self-identification). Every AC must map to at least one WP.
`
})
```

## Phase 3 — Code Implementer (per WP)

```
Agent({
  subagent_type: "code-implementer",
  description: "Implement WP-{n}: {wp-name}",
  prompt: `
Implement WP-{n}: {wp-name}. Project: {path} — read AGENTS.md for standards.

## Plan
**File**: {artifact-folder}/{feature-name}-plan.md
**Your WP heading**: #### WP-{n}: {wp-name}

Read plan.md first for full context (Goal, ACs, your WP details).

## Context
{requirement summary — see context size guidelines}

## Work Package
- **Files**: {file list}
- **Description**: {WP description from plan.md}
- **ACs**: {relevant ACs}

## Workflow
1. Read {artifact-folder}/{feature-name}-plan.md
2. Edit plan.md to set your WP **Status** from \`pending\` to \`in-progress\`
3. Implement — only modify files listed under your WP
4. When done, edit plan.md to set your WP **Status** to \`complete\`
5. Return a brief summary

## Rules
- ONLY modify listed files (plus plan.md for status updates). Follow existing patterns. No unnecessary abstractions.
- If blocked: set Status to \`blocked\` in plan.md, return partial progress + the specific question. You will receive guidance.
`
})
```

## Phase 3b — Rework (per WP)

Dispatched when Phase 4 finds must-fix issues.

```
Agent({
  subagent_type: "code-implementer",
  description: "Rework WP-{n}: {wp-name}",
  prompt: `
Fix must-fix issues from review of WP-{n}: {wp-name}. Project: {path}.

## Plan
**File**: {artifact-folder}/{feature-name}-plan.md — your WP heading: #### WP-{n}: {wp-name}

## Review Findings
{Must Fix section from {artifact-folder}/reviews/wp-{n}-review.md}

## Work Package
- **Files**: {file list} | **ACs**: {relevant ACs}

## Workflow
1. Set WP **Status** in plan.md to \`in-progress\` (from \`needs-rework\`)
2. Address every finding in the listed files
3. Set WP **Status** to \`complete\` when done

## Rules
- ONLY modify listed files (plus plan.md for status). Address every finding. No unrelated changes.
`
})
```

## Phase 4 — Code Reviewer (per WP)

```
Agent({
  subagent_type: "code-reviewer",
  description: "Review WP-{n}: {wp-name}",
  prompt: `
Review WP-{n}: {wp-name}

## Requirement Context
{requirement summary + relevant ACs — see context size guidelines}

## What Changed
{git diff — see context size guidelines for inline vs agent-fetched}

## Review Criteria
Correctness (fulfills ACs), code quality (SOLID/DRY/KISS), security (OWASP top-10), edge cases, integration.

## Output
**You MUST write** to: {artifact-folder}/reviews/wp-{n}-review.md
Format: ### Must Fix, ### Advisory (each: - {issue}: {desc} — {file:line}), ### Verdict (pass | must-fix)
`
})
```

## Phase 5 — QA Engineer

```
Agent({
  subagent_type: "qa-engineer",
  description: "QA verify: {feature-name}",
  prompt: `
Verify feature "{feature-name}" against requirements.

## Requirement
{full requirement file content — see context size guidelines}

## Acceptance Criteria
{all ACs from {feature-name}-plan.md}

## Files Changed
{all files modified across WPs}

## Instructions
1. **Write** test cases to {artifact-folder}/qa/test-cases.md — one+ per AC, positive/negative/edge
2. Execute: unit tests, build, lint, regression checks
3. **Write** results to {artifact-folder}/qa/test-results.md — pass/fail per case, overall verdict
Main agent reads these files to verify — do not skip writes.
`
})
```

## Phase 6 — Documentation Update (per file)

```
Agent({
  model: "{haiku | sonnet}",
  description: "Update {file-name}",
  prompt: `
Update {absolute-path-to-file} for structural changes from "{feature-name}".
Changes: {git diff --stat summary and description of new modules/scripts/folders}
Make surgical edits to affected sections only. Do not rewrite or change unrelated content.
`
})
```
