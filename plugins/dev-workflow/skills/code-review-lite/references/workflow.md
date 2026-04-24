---
name: workflow
description: Execution workflow for code-review-lite — scope resolution, diff collection, worktree setup, cleanup, and build-fail short report
---

# Workflow

## 1. Understand Scope

Determine what to review based on context:

- **PR ID provided**: Get target branch and metadata from PR details
- **Branch only**: Use current branch, ask for target if unclear
- **Specific files**: Review only those files
- **Staged changes**: Review what's about to be committed

### Primary: Azure DevOps CLI

```bash
# Find active PR for current branch
az repos pr list --source-branch "$(git branch --show-current)" --status active --output table

# Get PR details (target branch, title)
az repos pr show --id <pr-id>
```

### Fallback: Git Only

```bash
git branch --show-current
git log --oneline -10
git merge-base origin/main HEAD
```

## 2. Collect Changes

### Primary: Target Branch from PR

```bash
TARGET_BRANCH=$(az repos pr show --id <pr-id> --query targetRefName -o tsv | sed 's|refs/heads/||')
git diff --name-only $(git merge-base origin/$TARGET_BRANCH HEAD)..HEAD
git diff --no-prefix -U50 $(git merge-base origin/$TARGET_BRANCH HEAD)..HEAD
```

### Fallback: No PR

Ask for target branch (default to `main`/`master`/`develop`) and use the same `git diff` commands.

### Staged Changes Only

```bash
git diff --cached --name-only
git diff --cached --no-prefix -U50
```

### Large Diffs

Process in batches, priority order: core logic → configuration → tests → docs.

## 3. Worktree Setup

**Create worktree IFF any of these is true:**
- Target branch ≠ HEAD (reviewing a different branch)
- Working tree is dirty (uncommitted changes present)
- Staged changes are present

If HEAD is already the target branch AND tree is clean AND no staged changes → review in place (no worktree needed).

**Detection — running inside an existing review worktree**: Before creating, check whether CWD is already inside a `../{repo}-review-{branch}/` path. If so, either reuse that worktree (if branch matches) or refuse with: "Already inside a review worktree — remove it first or run from the main working tree."

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

Pass `WORKTREE_PATH` to each sub-agent as working directory. Agents do not run git commands.

## 4. Worktree Cleanup

**Run unconditionally** — even on build fail or mid-review errors.

```bash
git worktree remove "$WORKTREE_PATH"
```

Synthesis (Phase 4) may re-read flagged files, so cleanup runs AFTER Phase 4.

---

## Build Fail Short Report

Write this report when any build validator returns `Gate Result: FAIL`. Then run cleanup and STOP.

```markdown
# Code Review (Build Failed): {Feature/PR Title}

**Date**: {YYYY-MM-DD}
**Source**: {branch/commit/PR}
**Gate**: Build Validation — FAIL

## Build Status

| Project | Type | Status | Errors |
|---------|------|--------|--------|
| {name} | .NET 8 | FAIL | {n} |
| {name} | React | PASS | 0 |

## Errors

### `{ProjectName}`

1. **`{file}:{line},{col}`** — {error-code}: {message}

## Recommendation

Fix the build errors and re-run the review. Deep dive skipped to avoid reviewing broken code.
```
