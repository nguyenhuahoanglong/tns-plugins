---
name: implement-plan
description: "Gated code-development workflow. Use only when user explicitly runs `$implement-plan` or `/implement-plan`, or asks to run `implement-plan`; never auto-trigger."
---

# Implement Plan

Harden a plan into an unattended-executable contract, then delegate and verify code changes. Runs
alongside the host tool's plan mode: the host plans, this skill guarantees the plan can run. Main agent
owns the contract, plan status, and evidence; agents own only their allowlisted implementation files.

## Entry gate

Run only after explicit invocation: `$implement-plan`, `/implement-plan`, or a direct request to run or
use `implement-plan`. Similar implementation intent without that explicit call never activates this
skill. After invocation, require a code-development deliverable such as source code, executable scripts,
test code, or runtime/build code tied to a feature, fix, or refactor. For document-only, PRD, research,
planning, spreadsheet, release-note, AI-asset text/metadata, or config-only work, stop this workflow and
route the request normally. Supporting non-code files never establish eligibility.

## Hard rules

1. **This skill prescribes the contract, not the planning method.** No interview script, no question bank,
   no explorer or architect counts, no exploration scaling — the host's plan mode owns all of that. Cold
   invocation without plan mode stays fully supported: gather what the contract requires by ordinary means.
2. Before approval, work is read-only except the plan. Main agent never writes production logic after
   approval, except approved compile-ready TDD scaffolds without logic and trivial verification fixes.
   Explicit approval in the current request counts for an unchanged existing plan; ask again only after
   creating or materially revising the plan.
3. Resolve the plan path before anything else, per `references/plan-contract.md`. A host-injected plan path
   is the only writable file while plan mode is in force.
4. Only an invocation flag (`--tdd`, `--review`, `--no-tdd`, `--no-review`) or an explicit user `Yes`
   selects TDD or review.
5. **Autonomy boundary.** The guarantee covers execution through build and test verification. The only
   sanctioned interaction points are `code-review-lite` escalation, which pauses by design, and reporting a
   `blocked` task. Implementers never ask the user anything.

## Phase 1 — adopt

Detect a host-injected plan path and resolve the canonical path. Adopt the plan the host produced, an
existing plan file, or draft one by ordinary means. Read applicable `AGENTS.md`, requirements, standards,
and build/test configuration, and personally read the files each task will touch. Record consent from flags
when present; otherwise ask once, after the plan is drafted, per `references/plan-contract.md`.

## Phase 2 — harden

Write the plan to the contract in `references/plan-contract.md` using `references/plan-template.md`. Author
`## Preflight` for every external prerequisite; file probes are derived from `Files:`. Run
`python scripts/preflight.py <plan-path>`, transcribe its results and `Autonomy` into the plan, then run
`python scripts/verify_output.py <plan-path>` and fix every FAIL. A blocked probe is a valid recorded
result here, not a contract violation.

## Phase 3 — approve

Stop for approval only when the plan was created or materially revised; an explicitly approved unchanged
plan proceeds. The gate is zero FAIL and zero BLOCK. `Autonomy: verified-blocked` cannot be approved —
hand the plan over naming each blocked probe and what fixes it, resolve it with the user present, and
re-run preflight. Surface the `unverifiable` count so the user consents to the residual risk.

## Phase 4 — execute

In this order: promote the host draft to the canonical path, re-run preflight, then transcribe results into
the canonical file. Dispatch only through `references/agent-prompts.md`, recording working-tree-aware status
plus scoped diff and file hashes before each writable dispatch and comparing them after. Assign one
implementer per dependency-ready slice and cap concurrency at three. Main agent alone updates task Status,
and accepts DONE only after checking diff, file scope, and Done-when evidence. `qa-engineer` uses
`unit-testing` traceability and test-registry rules. One fresh blocker retry carries the decision and prior
progress; a second blocker marks the task `blocked`.

## Phase 5 — verify

Verify each Done-when, scoped diff, file scope, build, and existing suite. For selected review, invoke
`code-review-lite` with `Escalation Policy: ask` and Global Constraints verbatim; send all must-fix items
to one fresh implementer, re-verify and re-review, and cap at two loops. Skipped review is never offered,
run, or reported. Tick ACs only from evidence and rerun the verifier after status updates.

## Phase 6 — report

Report plan path, files changed, task/AC status, build/test evidence, the preflight summary, manual
follow-ups, and the review verdict only when selected. Update or offer supporting docs only when an AC,
project rule, or verified code impact requires them.

## References

- Contract, paths, consent, actionability: `references/plan-contract.md`
- Plan schema: `references/plan-template.md`
- Preflight probes and gates: `references/autonomy-preflight.md`
- Post-approval dispatch: `references/agent-prompts.md`

## Verify Output

Run `python scripts/preflight.py <plan-path>` and `python scripts/verify_output.py <plan-path>` before
approval and after final updates; zero FAIL, and zero BLOCK before approval.
