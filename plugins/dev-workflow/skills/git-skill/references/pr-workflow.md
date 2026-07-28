# Git Skill PR Workflow

Run the installed skill script by absolute path; it does not depend on the
current directory. Replace `<skill-root>` with the directory that contains the
installed `SKILL.md`.

```text
python -B "<skill-root>/scripts/git_skill.py" pr --repository "<repo>" --preview
```

`python -B "<skill-root>/scripts/git_skill.py" doctor --repository "<repo>"` is
the read-only prerequisite check.
Git, Python 3.11+, Azure CLI, and an authenticated Azure DevOps account are
required for creation. Install the Azure DevOps extension once with
`az extension add --name azure-devops`, then authenticate with `az login` to an
account that can create PRs in the remote project. Do not rely on mutable Azure
CLI defaults: the creator supplies organization, project, and repository from
`origin`.

## Preview and creation

Preview before a live PR. It reads Git state but does not create, update, link,
merge, synchronize, or delete anything.

```text
python -B "<skill-root>/scripts/git_skill.py" pr --repository "<repo>" --preview
python -B "<skill-root>/scripts/git_skill.py" pr --repository "<repo>" --target-branch dev --description "Summary and test evidence"
```

The only PR flags are `--repository`, `--target-branch`, `--description`,
`--allow-no-work-items`, `--preview`, and `--dry-run`. `--dry-run` has the same
non-mutating behavior as `--preview`; use one, not an invented legacy flag.
The script prints one `=== PR ===` header and one `RESULT:` JSON object. Stop on
a nonzero exit code or `"status":"ERROR"`; inspect its `message` and `details`
before retrying.

Commit subjects supply links: `#<task-id> summary` (or `<task-id>- summary`)
between the comparison ref and source branch are deduplicated and linked. If no
task ID is found, creation stops before Azure CLI runs. Use
`--allow-no-work-items` only when an unlinked PR is intentional, and record why.

## Remote, target, title, and body

Supported `origin` forms are:

- `https://dev.azure.com/<organization>/<project>/_git/<repository>`
- `https://<user>@dev.azure.com/<organization>/<project>/_git/<repository>`
- `git@ssh.dev.azure.com:v3/<organization>/<project>/<repository>`

Percent-encoded project and repository names are decoded. Any other remote is a
creation stop; correct `origin` rather than manually supplying Azure identity.

`--target-branch` wins. Without it, source `dev` targets `master` when present,
otherwise `main`; every other source prefers remote `dev`, then `master`, then
`main`, and finally uses `master`. The comparison normally uses
`origin/<target>` after fetch; it falls back to `<target>` when that remote ref
cannot be fetched or verified.

The title comes from a numeric/`US/` branch segment (for example,
`US/1878-pr-metadata` becomes `#1878 pr metadata`); otherwise it is
`Merge <source>`. `--description` is the explicit body. Otherwise body
precedence is `.CodeReview/<sanitized-source>.md`, then
`.azuredevops/pull_request_template.md`, `.github/pull_request_template.md`,
or `.github/PULL_REQUEST_TEMPLATE.md`, then `Merge <source> into <target>`.

## Mandatory post-create verification

Creation returning a PR ID is not completion. Re-query the created PR's title,
description, and linked work items with Azure CLI. If any differs, repair it,
then re-query all three again; stop if the second query is missing, malformed,
or still differs. The portable module's metadata routine follows that exact
repair-and-re-query rule, but the public `pr` command currently creates only.
Do not claim verification happened from the create result alone.

## Completion and cleanup boundaries

Auto-complete is optional and must stop on `mergeStatus` `conflicts` or
`failure`. Only after Azure reports `status` `completed` may the target be
checked out and pulled. Source cleanup requires separate explicit confirmation;
without it, local and remote source deletion are refused. If checkout or pull
fails, delete neither branch. These completion helpers are not public `pr`
flags, so perform them only through an approved workflow that preserves these
stops. See [troubleshooting.md](troubleshooting.md) for failures and fallback
boundaries.
