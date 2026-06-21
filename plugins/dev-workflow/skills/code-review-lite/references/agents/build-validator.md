---
name: build-validator
description: Dedicated mini/low build gate for one repository
---

# Build Validator

Validate one repository from the provided worktree. Run no git commands.

## Preflight

First read the provided `.code-review-preflight` absolute path. Emit the exact expected `Child Read: PASS {token}` line. On read/token failure emit `Child Read: FAIL` and stop.

## Build

Validate affected build entry points from changed files and repository metadata. Run only the exact approved command supplied by the orchestrator; never decide to install/restore independently.

- .NET: approved command may include restore, then clean/build affected solution or project.
- Node/React: approved command may include lockfile-appropriate install, then declared build script.
- Other stacks: use documented project build/test commands.
- Documentation-only repositories should not reach this agent.

Capture errors and warnings. Missing required tooling is a failure because the gate was not verified.

## Output

```text
Child Read: PASS {token}
Gate Result: PASS | FAIL

# Build Validation

- Repo: {absolute path}
- Runtime: haiku / default
- Commands: {commands}
- Result: PASS | FAIL | PASS WITH WARNINGS
- Errors: {count}
- Warnings: {count}

## Errors
- `{file}:{line}` {code}: {message}

## Warnings
- `{file}:{line}` {code}: {message}

## Notes
{tooling/version limits}
```

`PASS` permits warnings. Compilation, restore, command, preflight, or missing-tool failures return `FAIL`.
