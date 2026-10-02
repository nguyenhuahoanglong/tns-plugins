# Delegation and Handoffs

Read before dispatch. Choose role and supported model/effort through `model-routing.md`; a role's purpose
and permissions remain binding regardless of model. Templates are editable briefs, not verbatim ceremonies.

## Ownership

Main owns approval, plan status, integration, and evidence acceptance. Give each worker a bounded outcome,
relevant plan sections, allowed writes, constraints, dependencies, and Done when. A path reference is useful
when shared files are readable; a compact self-contained brief is valid when they are not.

Before writable dispatch, capture current status and scoped diff, including relevant untracked files.
Use file hashes when concurrent changes or reliable baseline comparison require them. Preserve existing
dirty work. Compare afterward; unexpected changes require investigation, not automatic rollback.

Tell every worker:

```text
You are not alone in this workspace. Preserve others' work and adapt to current changes.
Own only: <allowed files/module and permitted create/modify/delete actions>.
Do not change plan status, expand scope, or reset/restore/revert/stash others' work.
No stage, commit, push, publish, external writes, or installation unless this brief explicitly authorizes
that exact action within the approved plan and applicable permissions.
Send missing context or blockers to main, not the user. Return changed files and actual check results.
```

Do not use blanket deletion bans to prevent a planned rename/refactor. Specify permitted actions and
exact scope; main verifies them. Unapproved destructive or external actions remain prohibited.

## Implementation brief

```text
Role: implementation owner, including selected unit/component tests.
Task: <ID, outcome, approved plan/section or compact brief>.
Read: <applicable instructions, scoped sources, interfaces, tests>.
Constraints: <compatibility and settled decisions>.
Writes: <exact scope and permitted actions>.
Test approach: <direct implementation, characterization, or meaningful RED -> GREEN>.
Done when: <observable behavior and commands/checks>.
Return: complete | needs-context | blocked; changed files; checks/results; remaining concerns.
<ownership rules>
```

Prefer `code-implementer` when its runtime fits. A supported general worker can carry the same implementation
contract at a task-specific model; do not use a restricted research, QA, or reviewer role to write production
code. Main can own a tiny task directly. Reuse the implementer for normal fixes; use a fresh approach for
one substantive blocker retry. Do not force separate scaffold/test/implementation agents for routine work.

## QA brief

```text
Role: independent requirements-based QA; <test-cases | e2e | verify>.
Requirements/public contracts: <scoped sources and approved cases only>.
Target and expected identity: <environment, app, account role>.
Access: <verified browser/runner channel and safe auth reference; no credentials>.
Allowed test mutations/data and cleanup: <approved boundaries>.
Writes: <E2E assets and evidence paths only>.
Expected outcomes: <requirement -> case -> observable result>.
Return: cases run, environment identity, evidence, defects, and NOT RUN/BLOCKED gaps.
<ownership rules>
```

Use fresh isolated QA context, without production source, unit tests, or inherited implementation history.
Do not pass the entire implementation plan if it includes those internals; prepare a requirement-only
packet. Cases can be designed during planning. Live execution waits for approved mutations and ready target.
Choose the project E2E runner for repeatability; use an available browser skill/tool for observed UI evidence.
Verify the intended deployed/local build identity so testing the wrong build cannot become PASS.

## Review and blockers

Give an independent reviewer the scoped diff, requirements, Global Constraints, and relevant evidence.
Invoke a selected review skill with its real consent/provenance; do not add an automatic `ask` gate to every
review or silently replace its required approval with orchestrator text. Keep implementation ownership out
of the review session. Send actionable findings to implementation, then verify corrections, at most two
review rework loops by default.

Main resolves missing details from the plan, code evidence, and recorded decisions. A new consequential
choice or expired human-auth requirement pauses only dependent work. Consolidate the necessary user action;
do not hide it behind a false autonomy guarantee. An advisor may investigate a hard blocker before the
single fresh retry; advice does not approve scope changes or add retry loops.
