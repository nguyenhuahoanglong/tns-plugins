# Plan Content and Decisions

Read when adopting or drafting a plan. These are outcome requirements, not a prompt-audit scoring rubric.
Use the host's planning method and the smallest structure that makes execution clear.

## Path resolution

| Input | Origin | Destination |
|---|---|---|
| Host-injected plan path | host-plan-mode | Draft there; promote a copy to `.plans/<feature>.md` after approval |
| User-supplied plan | existing-input | Keep that exact path |
| Explicit requirement under `.backlog/<feature>/` | backlog-requirement | `.backlog/<feature>/plan.md` |
| Inline or other input | generated-project-root | Nearest project-root `.plans/<feature>.md` |

Honor host write restrictions. If planning writes are forbidden, show the plan in-message and write its
approved copy first after approval. Never overwrite/delete the host draft. Discovered backlog context
does not redirect an explicit path. Main owns canonical status edits after promotion.

## Minimum useful content

- Goal, scope, non-goals, constraints, and observable ACs.
- Task outcome, implementation/E2E ownership, allowed files or bounded module, dependencies, and Done when.
- Quality choices and reasons: new unit tests, TDD where useful, E2E, review route, existing checks.
- Human prerequisites, current evidence, permitted recovery, and any accepted verification gaps.
- Role, intended model/effort, fallback, and why that task needs that level. Mark inherited/unknown honestly.

One small task can be one concise block. Large work benefits from a table and dependency waves. Do not
require scaffolds, named task modes, exact field counts, or ban harmless words/code syntax. A real
unresolved behavior decision matters; an existing TODO comment or JSON object does not block approval.

For the optional parser, retain `## Context`, `## Tasks`, `### Task N:`, `## Acceptance Criteria`, and
`## Verification`, with the labeled fields shown in the template. Other host formats receive semantic
review rather than forced conversion. Static validation is not evidence of runtime readiness.

## Quality and approval

Honor `--tdd`, `--review`, `--no-tdd`, `--no-review` and existing explicit choices. Otherwise propose a
risk-based choice in the plan, with provenance `assessment` or `project`. Never normalize an assessment
into `user` consent. Approval of an unchanged plan covers its concrete choices; do not ask again per task.
Silence is not a choice. If a project rule conflicts with an explicit decline, resolve it before execution.

Existing checks remain verification even when writing new tests is skipped. TDD should fail at a meaningful
behavior assertion before implementation, not at missing imports or scaffolding. Use characterization for
behavior that must remain stable. Resolve test ownership and material expected outcomes during planning;
approved cases satisfy downstream gates only where that skill explicitly supports this.

Review route can be a scoped independent reviewer or the selected review skill, according to user/project
requirements. Never replace an explicitly requested review skill with a lighter route. For
`code-review-lite`, `Escalation Policy: auto` requires actual explicit user consent, recorded with source.
Without it, retain `ask` and disclose the potential pause. A planned Pro review must also satisfy Pro's
invocation and session-consent rules; do not fabricate `direct-user` provenance. Inspect these gates while
planning and use a fresh eligible review session where supported.

`complex-backbone` is not an automatic workflow switch. Resolve architecture during planning. If the user
explicitly requested `design-backbone`, satisfy its decision/approval gates through its own workflow and
record the handoff before dependent detail work. Do not unexpectedly introduce it midway through execution.

## Execution discretion

Main may choose helper names, local algorithms, test fixtures, and sequencing within approved behavior and
scope. Reassignment and model escalation within the recorded fallback/cost envelope need no new approval.
New product behavior, architecture direction, external authority, or meaningful cost expansion does.

Independent tasks have disjoint write scopes. Tasks may touch the same file sequentially with an explicit
dependency and updated baseline. Assign coupled work to one owner. Main may refine an allowlist within an
already-approved module before dispatch, documenting why; a delegate may not expand it unilaterally.

Blocked work stays visible. An approved staged plan identifies exactly what can execute, which ACs remain
blocked, and what human action is outstanding. Do not turn a required E2E check into optional verification
or claim full delivery merely because local tests pass.
