---
name: requirement-validation
description: Orchestrator-side workflow for detecting, retrieving, and confirming work item requirements before dispatching the Requirement Validator agent
---

# Requirement Validation (Orchestrator-side)

This file covers the orchestrator's pre-work: finding the work item, fetching its details, and confirming with the user. The actual validation against code changes is performed by the Requirement Validator agent (see `agents/requirement-validator.md`).

## Prerequisites

Requires Azure CLI. On first run: `az config set extension.use_dynamic_install=yes_without_prompt` (auto-installs the azure-devops extension). Auth via `az login` or set `AZURE_DEVOPS_EXT_PAT`.

## Phase 1 + 2: Detect and Retrieve (Script-driven)

Run a single command — it detects the work item ID, fetches it (plus its parent), strips ADO's HTML, and returns prompt-ready markdown:

```bash
python <code-review-pro-skill>/scripts/ado_work_item.py context [--pr {pr-id}] --repo {repo-path}
```

Pass `--pr {pr-id}` whenever a PR ID is known — the script reads PR-linked work items, the most reliable source. You may also pass `--id N` to pin a specific work item and skip detection.

**Detection priority (what the script does internally):**
1. PR linked work items via `az repos pr work-item list` (most reliable)
2. Branch name patterns — e.g. `feature/1234-add-login`, `bug/WI-1234`
3. Commit message patterns — `AB#1234`, `[WI:1234]`, `Fixes #1234`, `#1234` — scanned across the last 20 commit subjects

One call handles detection + fetch + parent fetch + HTML stripping and prints a markdown block:

```
## Work Item #1234 — {title}
- **Type/State**: User Story / Active
- **Parent**: #1200 — {parent title} (Feature)
- **Detected from**: branch name 'feature/1234-x'   (only when auto-detected)

### Description
{plain text}

### Acceptance Criteria
{plain text}
```

Extracted fields: Title, Description, Acceptance Criteria, State, plus Parent for broader context (why the work matters).

## Fallback Chain

Used when the script exits non-zero.

### Exit 3 — no work item ID detectable

1. Read `{repo}/.docs/ado-context.md` if present — match branch name or changed-path keywords against its epic/feature/story alias tables and propose a candidate to the user, e.g.: "This looks like User Story #2197 — correct?"
2. If still nothing, ask the user:
   > "I couldn't find a linked work item. Could you provide the requirement context — a work item ID, acceptance criteria, or description of what this change should accomplish?"

### Exit 2 — az CLI not installed or not authenticated

Report the az problem to the user and go straight to step 2 above.

## Phase 3: Confirm with User

Present the detected requirement to the user before proceeding:

> **Detected Requirement:**
> - Work Item: #{id} - {title}
> - Parent: #{parent-id} - {parent-title}
> - Acceptance Criteria: {summarized criteria}
>
> Is this the correct context for this review? Do you have any additional goals or expectations?

Wait for user confirmation. The user may:
- Confirm the detected requirement
- Provide a different work item ID
- Add additional context or goals
- Clarify specific areas of concern

The confirmed work item details (title, description, acceptance criteria, parent) are passed to the Requirement Validator agent in Phase 3 — and to the Approach Gate (Phase 2a) inline by the orchestrator.
