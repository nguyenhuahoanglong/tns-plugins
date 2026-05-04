---
name: implement-feature
description: "Orchestrate autonomous feature implementation: interview, plan, implement (parallel agents), review, and QA verify. Use for '/implement-feature'."
version: 1.2.0
---

# Implement Feature

Autonomous end-to-end feature implementation. After an initial interview, the main agent drives planning, parallel implementation, review, and QA without further user interaction.

## Input

Accepts one of:
- **Work item ID**: Numeric → use `azdevops-operations` skill to fetch requirement details
- **File path**: Path to a requirement document → read the file
- **Folder path**: Path to a feature folder → use as artifact folder directly
- **Inline text**: Requirement described directly in the conversation

## Artifact Location

Resolve the artifact folder and feature name **once** at the start, before any file writes:

| Input | Artifact folder | Feature name |
|---|---|---|
| **File path** | Parent directory of the file | Folder basename, or filename minus `-requirement`/`-plan` if folder is generic (`.backlog`/`.plans`/`docs`) |
| **Folder path** | The folder itself | Folder basename |
| **Work item ID** | `.plans/{feature-name}/` (fallback) | Kebab-case of the work item title (truncate to ~5 words) |
| **Inline text** | `.plans/{feature-name}/` (fallback) | Kebab-case of the requirement subject (truncate to ~5 words) |

Create the folder if it doesn't exist. Artifacts:
- `{feature-name}-requirement.md` — locked requirements
- `{feature-name}-plan.md` — work-package plan (read/updated by implementers)
- `qa/`, `reviews/` — sub-folders for QA artifacts and review findings

The feature/requirement name is embedded in the filename so requirement and plan files self-identify when listed alongside other artifacts.

## Phase 1 — Gather & Interview

**This is the ONLY phase with user interaction.** Be thorough — after confirmation, all decisions are yours.

### 1.1 Parse input

Detect the input type and resolve the artifact folder (see [Artifact Location](#artifact-location)):
- **Work item ID** → invoke `azdevops-operations` to retrieve full details
- **File** → read it
- **Folder** → scan for existing artifacts:
  - If `{feature-name}-requirement.md` (or legacy `requirement.md`) exists → read it and use as starting input (treat as file path input)
  - If `{feature-name}-plan.md` (or legacy `plan.md`) also exists → check its status to decide whether to resume or restart
  - If folder is empty → proceed as inline (interview from scratch)
- **Inline** → use as-is

### 1.2 Gather codebase context

Spawn an **Explore agent** (medium thoroughness) to understand:
- Project structure, technology stack, coding standards (read project AGENTS.md)
- Existing patterns relevant to the feature
- Files and modules the feature will touch or extend

### 1.3 Structured interview

Conduct a focused interview across five categories — see `references/interview-guide.md` for the full question bank (functional, design, boundaries, constraints, acceptance criteria).

**Rules:** Ask 3-5 questions per round. Max 3 interview rounds. Do NOT proceed until you can state: *"I understand exactly what to build, how to build it, and how to verify it."*

### 1.4 Lock requirements

- Write `{artifact-folder}/{feature-name}-requirement.md` using `references/requirement-template.md`
  - **Skip** if the artifact folder already contains a requirement file that was used as input — update in place instead
- Present the user a summary: requirement + acceptance criteria + design decisions
- Get explicit confirmation → **autonomous mode begins, no more user questions**

## Phase 2 — Plan

Spawn a **Plan agent** with `{artifact-folder}/{feature-name}-requirement.md` content and codebase context. See `references/agent-prompts.md` for dispatch template and context size guidelines.

- Create `{artifact-folder}/{feature-name}-plan.md` following `references/plan-template.md`
- Group work packages into **waves** — no two WPs in the same wave may touch the same files
- Each WP: name, files, description, acceptance criteria it addresses

**Verify**: Read `plan.md` — file exists, all ACs mapped to WPs, no wave has overlapping files. If missing → re-dispatch once, then write plan directly. Update status to `implementing`.

## Phase 3 — Implement

For each wave, in dependency order:

1. Spawn **code-implementer** agents in parallel — one per WP in the wave
   - Each receives: `{artifact-folder}/{feature-name}-plan.md` path, its WP heading, requirement summary, coding standards
   - Each implementer **must** edit plan.md to set its WP **Status** from `pending` → `in-progress` at start, then `complete` (or `blocked`) at end
   - See `references/agent-prompts.md` for dispatch templates and context size guidelines
2. Wait for all agents in the wave to complete
3. Read `plan.md` and verify every WP in this wave is `Status: complete`. If any are not, investigate before proceeding
4. Proceed to next wave

## Phase 4 — Review

For each completed WP, spawn a **code-reviewer** agent (one per WP, not full pipeline):
- Input: git diff for WP files + requirement context
- Output: **must write** findings to `{artifact-folder}/reviews/wp-{n}-review.md`

**Verify**: Read the review file — must contain Must Fix / Advisory / Verdict sections with clear verdict (`pass` or `must-fix`). If missing or malformed → re-dispatch once. If still missing → main agent reviews directly.

**Decision rules** (based on file content, not agent return message):
- Advisory → note in plan, proceed
- Must-fix → set WP to `needs-rework`, re-dispatch implementer with review findings (see rework template in `references/agent-prompts.md`)

| Limit | On exhaust |
|-------|-----------|
| 2 rework attempts per WP | Main agent applies best-effort fix directly |

## Phase 5 — QA Verify

Spawn a **qa-engineer** agent:
1. Read `{artifact-folder}/{feature-name}-requirement.md` + acceptance criteria
2. **Must write** `{artifact-folder}/qa/test-cases.md` — test cases mapped to each AC
3. Execute tests (unit tests, build verification, lint)
4. **Must write** `{artifact-folder}/qa/test-results.md` — pass/fail per case with evidence

**Verify**: Read both files — `test-cases.md` maps to ACs, `test-results.md` has pass/fail per case with verdict. If missing → re-dispatch once. If still missing → main agent performs QA directly.

**Decision rules** (based on file content, not agent return message):
- All pass → proceed to Phase 6
- Failures → create targeted fix WPs, loop to Phase 3

| Limit | On exhaust |
|-------|-----------|
| 2 QA loops | Mark plan `blocked`, report to user with details |

## Phase 6 — Complete & Sync

### 6.1 Update plan status
1. Set `{artifact-folder}/{feature-name}-plan.md` status to `done`, check off all ACs
2. Add completion entry to iteration log with timestamp

### 6.2 Update documentation
Identify project files needing updates for **structural changes** (new modules, scripts, folders):
1. Run `git diff --stat` (or `HEAD~N` if commits were made) to get changed files
2. Scan for `AGENTS.md`, `README.md`, setup scripts referencing changed areas
3. For each, spawn a sub-agent — **haiku** for simple updates, **sonnet** for complex. See `references/agent-prompts.md`. Dispatch in parallel.
4. **Verify**: Read each updated file — changes accurate, scoped, formatting preserved.

### 6.3 Report
Summary: what was built, files changed, tests passing, documentation updated.
