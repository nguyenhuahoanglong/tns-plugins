---
name: review-workflow
description: Detailed execution steps for performing a code review - scope determination, change collection, and progress tracking
---

# Review Workflow

## 1. Understand Scope

Determine what to review based on context:

- **PR ID provided**: Get target branch and metadata from PR details
- **Branch only**: Use current branch, ask for target if unclear
- **Specific files**: Review only those files
- **Staged changes**: Review what's about to be committed

### Primary: Azure DevOps CLI

Use `az repos pr` to detect active PRs and extract metadata (target branch, title, linked work items).

```bash
# Find active PR for current branch
az repos pr list --source-branch "$(git branch --show-current)" --status active --output table

# Get PR details (target branch, title, description)
az repos pr show --id <pr-id>

# Get linked work items from PR
az repos pr work-item list --id <pr-id>
```

### Fallback: Git Only

When no PR exists or az CLI is unavailable:

```bash
# Current branch
git branch --show-current

# Recent commits on this branch
git log --oneline -10

# Find merge base with target
git merge-base origin/main HEAD
```

### Alternative: GitHub CLI

For GitHub-hosted repositories:

```bash
gh pr view --json targetBranch,title,body
```

## 2. Collect Changes

### Primary: Target Branch from PR

```bash
# Extract target branch from PR details
TARGET_BRANCH=$(az repos pr show --id <pr-id> --query targetRefName -o tsv | sed 's|refs/heads/||')

# List changed files
git diff --name-only $(git merge-base origin/$TARGET_BRANCH HEAD)..HEAD

# Full diff with generous context
git diff --no-prefix -U50 $(git merge-base origin/$TARGET_BRANCH HEAD)..HEAD
```

### Fallback: No PR

When no PR exists, ask the user for the target branch (default to `main`/`master`/`develop`) and use the same `git diff` commands above with that value.

### Staged Changes Only

```bash
git diff --cached --name-only
git diff --cached --no-prefix -U50
```

### Large Diffs

If the diff is large, process files in batches. Prioritize:
1. Core logic files (models, services, controllers)
2. Configuration changes
3. Test files
4. Documentation

## 3. Track Progress

For multi-file reviews, use the TodoWrite tool:
- Create one item per file to review
- Mark in-progress while analyzing
- Mark completed after documenting findings

Order files by complexity — review the most critical/complex files first.

## 4. Worktree Setup

Replaces in-place checkout. Preserves the user's working tree and supports multi-repo PRs (e.g., paired BE/FE).

For each repo touched by the PR:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_NAME=$(basename "$REPO_ROOT")
SOURCE_BRANCH="{pr-source-branch}"
SAFE_BRANCH="${SOURCE_BRANCH//\//-}"
WORKTREE_PATH="../${REPO_NAME}-review-${SAFE_BRANCH}"

# Handle re-run collisions
if git worktree list --porcelain | grep -q "$WORKTREE_PATH"; then
  git worktree remove --force "$WORKTREE_PATH"
fi

git fetch origin "$SOURCE_BRANCH"
git worktree add "$WORKTREE_PATH" "origin/$SOURCE_BRANCH"
```

Pass `WORKTREE_PATH` to each agent as the working directory. Agents read code from the worktree path directly — they run no git commands.

### Multi-Repo Discovery

In priority order:
1. PR linked repos in Azure DevOps (`az repos pr show --id <pr-id>`)
2. User explicitly lists repos in the request
3. Orchestrator asks: "I see changes in `{repo}`. Are there paired repos (e.g., paired BE/FE)?"

## 5. Worktree Cleanup

**Run unconditionally** — even on REJECT, build fail, or mid-deep-dive errors. The orchestrator owns cleanup; if it skips, worktrees leak.

For each worktree from step 4:

```bash
git worktree remove "$WORKTREE_PATH"
```

Synthesis (Phase 4) re-reads flagged code, so cleanup runs AFTER synthesis — not after Phase 3.
