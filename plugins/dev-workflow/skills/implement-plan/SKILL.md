---
name: implement-plan
description: "Plan and execute approved code changes with minimal user interruption. Use only on explicit `$implement-plan`, `/implement-plan`, or a request to run this skill; never auto-trigger."
---

# Implement Plan

Turn an agreed code plan into verified changes. Resolve predictable human dependencies during planning,
then execute with minimal interruption. Support the host's planning mode; do not impose a second planning
method or promise that authentication and external services can never change.

## Activation and boundaries

- Activate only when explicitly asked to run this skill. Reviewing or improving the skill is not invocation.
- Require a code-development outcome: source, executable scripts, tests, or runtime/build code for a
  feature, fix, or refactor. Route document-only, PRD, research, AI-asset text, and config-only work normally.
- Before implementation approval, inspect and plan. Follow host write restrictions. Authentication or
  environment setup needed for planning uses existing authorization; otherwise resolve it with the user
  before execution. A plan never grants new external-write, destructive, or publication authority.
- Preserve unrelated work. Main owns decisions, integration, status, and acceptance evidence. Delegate
  when useful; main may implement a small coupled task when delegation adds cost without benefit.
- Respect explicit test/review choices and project requirements. Surface conflicts during planning.
  Existing approval remains valid; only material scope, behavior, architecture, or authority changes
  need a new decision. Routine implementation details do not.

## 1. Prepare the plan

Resolve the path and adopt an existing plan or draft through the host's normal workflow. Read applicable
instructions, requirements, affected behavior, and test configuration. Reuse scoped exploration evidence;
main need not reread every file inspected by a competent delegate.

Read [plan-contract.md](references/plan-contract.md) for paths, approval boundaries, and minimum content.
Use [plan-template.md](references/plan-template.md) when useful; headings and field count are not goals.
Split by independently verifiable outcomes and ownership, keeping coupled changes together. Record
dependencies, allowed writes, observable acceptance, and verification. Serialize shared-file work.

Select unit tests/TDD, E2E, and review from project rules, explicit choices, and actual risk. Put choices
and reasons in the plan for approval; ask only unresolved consequential questions. No mandatory separate
quality interview. TDD is useful for changed behavior and regressions, not every edit.

## 2. Resolve human dependencies before approval

Read [autonomy-preflight.md](references/autonomy-preflight.md) for relevant prerequisites. In planning:

- Establish E2E target identity, runner/browser access, account/role, test cases and expected outcomes,
  permitted test data/mutations, cleanup, and environment recovery. Test read-only access through the
  actual execution channel. Complete required user login/MFA while the user is present; never save secrets
  in the plan. A reachable URL or listed account alone does not prove authenticated application access.
- Resolve UI direction and references before delegating taste-sensitive work. Lock consequential
  architecture, test ownership, and any selected downstream skill's approval requirements now.
- Inspect selected downstream skills for interaction gates. Carry actual prior consent and provenance;
  plan approval must not be relabeled as a user-authored flag. For Lite-to-Pro escalation, get explicit
  advance consent if wanted. Otherwise record the possible pause; do not promise unattended review.
- Record expected blockers, permitted recovery, and fallback. Prerequisites repairable through approved
  noninteractive setup may be execution dependencies. Unknown credentials or test authority may not.

Use the typed preflight helper for supported checks, or record direct read-only tool evidence. Both are
valid. Mechanical probes supplement judgment. Unresolved human prerequisites block their dependent work;
an explicitly approved staged plan may still run independent tasks with incomplete acceptance visible.

## 3. Show and approve

Read [model-routing.md](references/model-routing.md) before assigning roles/models. Discover live tools,
model choices, effort controls, role pins, and concurrency. Show task assignments and the readiness summary
using [report-templates.md](references/report-templates.md). Include any model fallback and potential pause.

Ask once for the concrete plan when not already approved. Bundle remaining decisions into that planning
interaction. Do not interpret silence as consent. Execution starts only for approved scope with resolved
human prerequisites, or the explicitly approved runnable stage.

## 4. Execute and keep progress visible

Promote a host draft if required. Recheck volatile prerequisites before dispatch/use, especially auth and
environment identity; do not replay an entire questionnaire. Follow [agent-prompts.md](references/agent-prompts.md)
for ownership and evidence handoff. Dispatch dependency-ready tasks within actual capacity, using disjoint
write scopes. Reuse a productive agent; use a fresh one for independent review or a failed approach.

Main resolves NEEDS_CONTEXT from evidence and approved decisions. Repair ordinary build/test failures
within scope. Default to one fresh retry after a substantive blocker, optionally informed by an advisor;
do not retry the same failed approach without new evidence. A second substantive blocker pauses that
task, not independent work. Selected review rework stays bounded to two loops unless approved otherwise.

Report task starts/completions, changed evidence, routing changes, and blockers. Separate implementation
from verification. Never claim completion from an agent's DONE message alone.

## 5. Verify and close

Check scoped diff, ownership, each acceptance criterion, build, and relevant existing tests. Add meaningful
tests when selected; unit/component work belongs to implementation ownership, E2E to independent QA.
Use the planned review route and consent. Preserve downstream gates; do not silently bypass them.

Missing tools, access, or checks mean NOT RUN/BLOCKED, never PASS. Unexpected MFA or a new material
decision may need the user: finish independent work, then send one concise request with impact and evidence.
Do not mark unfinished acceptance complete to avoid interaction.

Report the plan, task/AC status, observed model/effort when available, changes, checks, and any remaining
action using the reporting template. Supporting docs follow actual code impact, project rules, or ACs.

## Optional structured checks

For the structured template, run `python <skill>/scripts/verify_output.py <plan-path>` before approval
and after final status edits. Run `python <skill>/scripts/preflight.py <plan-path> --repo-root <project-root>`
when using typed probes. Resolve reported inconsistencies; never rewrite a sound host plan merely to
satisfy this helper. Equivalent evidence may be recorded directly. Static validity proves neither
authorization nor successful implementation.
