# Implement Plan

## Purpose

Explicitly invoked planning and implementation workflow for code development. It explores the nearest
target project, assesses quality needs, writes or validates an approved plan, delegates allowlisted code
work, and verifies evidence. Similar intent never auto-triggers it; non-code primary deliverables route
elsewhere.

## Pain Points

- Unexpected activation for documentation, planning, and other non-code work.
- Repetitive preference questions when routine/risky evidence is decisive.
- Quality choices inferred from a whole workspace instead of the target module.
- Plans missing reasons, modes, executable tasks, or resolved placeholders.
- Implementation accepted from claims rather than scoped diffs and Done-when evidence.
- Agent count inferred from file count instead of real dependency and coupling boundaries.

## Workflow

```text
Entry    explicit invocation -> code-development eligibility
Phase 0  scaled exploration -> advisory assessment -> unresolved-only consent
Phase 1  design -> dependency waves -> verifier -> approval
Phase 2  TDD/simplify -> delegated implementation -> scoped evidence
Phase 3  build/existing tests -> selected ask-policy review -> AC evidence
Phase 4  report -> evidence-required supporting docs only
```

## Quality and task contract

New/re-written plans record path origin/evidence; separate recommendations from decisions, sources, and
reasons; and use only `recommended|not-recommended`. Routine work skips both practices without asking.
Risky recommendations state evidence, workflow/regression risk, and effort; only user `Yes` selects TDD
or review. Old-modern auto selections are accepted as input but confirmed/normalized before execution;
legacy requested/not-requested maps to explicit user decisions.

At least one task must deliver source, executable, test, or runtime/build code tied to a feature, fix, or
refactor. Supporting non-code files may accompany eligible code work only when an AC, project rule, or
verified code impact requires them; they never activate the skill or form a standalone task.

Each new task records Risk, Risk reason, Depth, Mode, Existing-method baseline, and Scaffold. Existing
method TDD proves baseline/characterization GREEN then changed RED/GREEN. Simple-new starts only with a
compile-ready no-logic scaffold. Complex backbones pause for unchanged `design-backbone`, retain its own
approval locks, verify handoff, and resume without duplicate tests.

## Delegation, verification, and design

Planning is read-only except the plan. The main agent does not write production logic except an approved
compile-ready TDD scaffold or trivial verification fix. Explorers/architects scale from zero with actual
uncertainty; complex scope or three or more risky tasks receive a fresh-eyes executability gate.
Implementers map to independent dependency-ready slices, keep coupled files together, and cap concurrent
writers at three. Every writable dispatch has an exact allowlist and destructive-operation bans; the main
agent compares a working-tree-aware scoped baseline and alone updates status.

`qa-engineer` follows `unit-testing` traceability/test-registry rules. Implementers return `DONE`,
`DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`; blockers get one fresh retry, then become blocked.
Build and existing tests are mandatory. Selected review uses `code-review-lite` with `Escalation Policy:
ask`, receives Global Constraints verbatim, and has at most two rework/re-review loops. The verifier checks
new, old-modern, and legacy shapes; Phase 4 reports evidence and only selected-review verdicts.

## Changelog

### 2026-08-09 - v3.6.0 - Explicit code-only activation

- Restricted activation to explicit user invocation and added a code-development eligibility gate.
- Removed document-only handling, corrected consent option labels, and honored unchanged-plan approval.
- Replaced file-count delegation with dependency/coupling scaling and limited supporting docs to proven
  code impact.

### 2026-07-21 - v3.5.0 - Consent-first paths and task modes

- Added deterministic path origins, consent-first recommendations, task modes, backbone handoff, safety,
  and selected-review `ask` integration while retaining input compatibility.

### 2026-07-12 - v3.4.0 - Project quality assessment

- Replaced mandatory unit-test/review questions with balanced target-project assessment.
- Added explicit override precedence, unresolved-only questions, evidence reasons, and legacy mapping.
- Added deterministic plan verifier and assessment eval cases.
- Split agent prompts and reduced SKILL/reference files below 150 lines.

### 2026-07-11 - v3.3.0 - Explicit choices

- Added independent unit-test and code-review controls while preserving mandatory verification.

### 2026-07-10 - v3.2.0 - Plan-mode parity

- Added scaled architects, Actionability Gate, plan quick-check, and verify-before-accept.

### 2026-06-29 - v3.0.0 - Unified gated workflow

- Merged lite variant, added approval gate, auto-scaling, TDD option, and flat `.plans/` plans.
