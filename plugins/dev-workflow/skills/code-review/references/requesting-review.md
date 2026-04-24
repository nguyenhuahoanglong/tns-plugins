---
name: requesting-review
description: When and how to request code reviews from others — subagents, human reviewers, or CI checks
---

# Requesting Review

Dispatch reviews to catch issues before they cascade.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After completing a major feature or task
- Before merging to main/default branch
- After fixing complex bugs

**Optional but valuable:**
- When stuck and need a fresh perspective
- Before refactoring (baseline check)
- After large-scale changes across multiple files

## How to Request

### 1. Prepare Context

```bash
# Get commit range
BASE_SHA=$(git merge-base origin/main HEAD)
HEAD_SHA=$(git rev-parse HEAD)

# Summary of changes
git diff --stat $BASE_SHA..$HEAD_SHA
```

### 2. Provide Review Context

Whether requesting from a human or a subagent, include:

- **What was implemented**: Brief description of the changes
- **Requirements/Plan**: What the code should accomplish (link to work item, spec, or plan)
- **Commit range**: BASE_SHA and HEAD_SHA for the reviewer to diff
- **Areas of concern**: Any parts you're uncertain about

### 3. Act on Feedback

| Feedback Priority | Action |
|-------------------|--------|
| Critical | Fix immediately before proceeding |
| Important/High | Fix before merging or moving to next task |
| Minor/Low | Note for later, fix if time allows |

If you disagree with feedback:
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

## Integration with Workflows

**Task-driven development:**
- Review after each significant task
- Fix issues before moving to next task
- Prevents issue compounding

**Pull Request workflow:**
- Verify tests pass first
- Request review before merge
- Address all Critical/High feedback

**Ad-hoc development:**
- Review before merge to main
- Review when stuck on a problem

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed High-priority issues
- Dismiss valid technical feedback without reasoning

## The Bottom Line

Review early. Fix issues before they compound. Technical feedback is a gift — evaluate it honestly.
