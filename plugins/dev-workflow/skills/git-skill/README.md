# Git Skill

## Purpose

Provide a self-contained, portable Python CLI for safe Git commits, branches, stashes, merges, and Azure DevOps pull requests. The installed skill resolves its own `scripts/git_skill.py` entrypoint and can operate on an explicitly supplied repository on Windows, macOS, or Linux.

## Pain Points

- Bare Git commits can bypass work-item, scoped-staging, and message conventions.
- Story branch IDs and child task commit IDs have different purposes and must not be conflated.
- Dirty default branches need an atomic stash, branch, and reapply workflow to keep work off the default branch.
- PR metadata needs commit-derived task links, preview, verification, and a safe no-work-item stop.
- Installed skills must not rely on a personal path, global PowerShell function, or platform-specific executable.

## Runtime Contract

Resolve the installed skill directory containing `SKILL.md`, then invoke `python "<SKILL_ROOT>/scripts/git_skill.py"`. The public subcommands are `doctor`, `context`, `commit`, `branch`, `merge`, `stash`, `branches`, and `pr`; use `--repository` for the target repo. The CLI outputs a structured header plus `RESULT:` JSON and returns stable success/failure exit codes.

Use `scripts/verify_output.py` with a CLI result JSON to check applicable repository postconditions, expected files, work-item links, or dry-run invariants. See [SKILL.md](SKILL.md) for intent routing and confirmation boundaries; see the references for PR and recovery detail.

## Changelog

### 2026-07-27 - Portable Python CLI contract

- Replaced PowerShell/global-script instructions with installed-skill-root invocation of the portable Python CLI.
- Documented public CLI commands, structured output, dry-run/preview, and self-verification without exposing implementation-only APIs.
- Preserved compound workflow autonomy, scoped session commits, story/task rules, dirty-default reapply, PR safeguards, and explicit destructive-action confirmation.

### 2026-06-17 - Validate and tighten workflow

- Added missing README documentation required by skill validation.
- Shortened frontmatter description below the 200-character limit.
- Tightened SKILL.md wording while preserving dirty-default-branch handling and PR finalization guidance.
