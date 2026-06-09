---
name: requirement-validation
description: Orchestrator-side workflow for detecting, retrieving, and confirming work item requirements before dispatching the Requirement Validator agent
---

# Requirement Validation (Orchestrator-side)

This file covers the orchestrator's pre-work: finding the work item, fetching its details, and confirming with the user. The actual validation against code changes is performed by the Requirement Validator agent (see `agents/requirement-validator.md`).

## Phase 1: Detect Work Item

Look for work item IDs in these sources (in priority order):

### Primary: From PR Linked Work Items (Azure DevOps CLI)
```bash
# Get work items linked to the PR (most reliable source)
az repos pr work-item list --id <pr-id>

# Get PR details (description often contains work item references)
az repos pr show --id <pr-id>
```

PRs in Azure DevOps often have work items linked directly via the platform — this is the most reliable detection source.

### From Commit Messages
```bash
# Check recent commits for work item patterns
git log --oneline -20
```

Common patterns:
- `#1234` — Generic work item reference
- `AB#1234` — Azure DevOps format
- `[WI:1234]` — Bracketed format
- `Fixes #1234` / `Closes #1234` — GitHub format

### From Branch Name
```bash
git branch --show-current
# Extract numeric ID from patterns like: feature/1234-add-login, bug/WI-1234
```

### Alternative: GitHub CLI
```bash
gh pr view --json body,title
```

### Fallback
If no work item is detected, ask the user:
> "I couldn't find a linked work item. Could you provide the requirement context — a work item ID, acceptance criteria, or description of what this change should accomplish?"

## Phase 2: Retrieve Requirement

Use the azdevops-operations skill to fetch work item details:

### Get Work Item
```
AzDevOps-GetWorkItemById -Id <detected-id>
```

Extract from the work item:
- **Title** — What the work item is about
- **Description** — Detailed requirement context
- **Acceptance Criteria** — Specific conditions for completion
- **State** — Current workflow state
- **Priority** — Business priority level

### Get Parent Work Item
```
AzDevOps-GetWorkItemById -Id <parent-id>
```

The parent (Feature or Epic) provides broader context:
- Why this work is being done
- How it fits into a larger initiative
- Additional constraints or dependencies

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
