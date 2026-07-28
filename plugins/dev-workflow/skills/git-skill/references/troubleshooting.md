# Git Skill Troubleshooting

Invoke diagnostics from the installed skill root, never from an assumed working
directory:

```text
python -B "<skill-root>/scripts/git_skill.py" doctor --repository "<repo>"
python -B "<skill-root>/scripts/git_skill.py" context --repository "<repo>" --brief
```

The CLI returns a single header plus `RESULT:` JSON. Stop on a nonzero exit code
or `"status":"ERROR"`; retain that record when escalating.

| Symptom | Safe response |
|---|---|
| Python, Git, or Azure CLI unavailable | Install the missing prerequisite, then rerun `doctor`. Do not substitute a machine-local wrapper. |
| Azure CLI extension or sign-in fails | Run `az extension add --name azure-devops`, then `az login` with an account authorized for the remote project; rerun `doctor`. |
| `origin` cannot identify Azure DevOps | Set `origin` to a supported HTTPS or SSH Azure DevOps URL listed in [pr-workflow.md](pr-workflow.md); do not hand-enter org/project/repository into the Git CLI. |
| Target is surprising or default ref is missing | Use `pr --target-branch <branch> --preview`, confirm the plan, then create. Fetch/remote-ref failure intentionally falls back to the local target ref. |
| Dirty tree before changing branches | Use `context --brief`, then use the skill's `stash` or `branch --preserve-dirty-default` workflow. Do not force checkout over uncommitted work. |
| Merge conflict | Stop, inspect `git status`, resolve deliberately, stage the resolved files, and complete or abort the merge. Do not request PR completion while conflicts remain. |
| Stash apply conflict | Stop, inspect the conflict markers and `git status`, resolve and stage intentionally, then drop a stash only after verifying its changes are present. |
| No PR work-item links | Add valid task IDs to the source-branch commit subjects, push the corrected history according to team policy, preview again, and create. Use `--allow-no-work-items` only for a deliberately unlinked PR. |
| PR title, body, or links are wrong | Stop completion. Re-query all three, repair only the drift, and re-query all three again. A failed or malformed final query is a failure, not a warning. |
| Auto-complete reports conflicts/failure | Do not sync or clean up. Resolve the PR conflict, wait for a mergeable state, then obtain explicit approval before retrying completion. |
| Target synchronization fails | Do not delete the source branch. Restore a clean target checkout/pull first. |
| Cleanup requested | Require explicit confirmation after completed PR status and successful target checkout/pull; then remove local source and remote source. Without confirmation, leave both intact. |

## Fallback boundary

Use `pr --preview` and its structured result to diagnose planning. The public
`pr` command supports planning and creation only; it has no flags for metadata
repair, auto-complete, target synchronization, or branch deletion. Do not
replace it with ad hoc destructive commands. Escalate when those follow-up
operations are needed, carrying the PR ID and the final verification evidence.
