# Implement Plan

## Purpose

Self-contained planning and implementation workflow. It explores the nearest target project, assesses
quality needs, writes an approved plan, delegates allowlisted work, and verifies evidence.

## Pain Points

- Repetitive preference questions when routine/risky evidence is decisive.
- Quality choices inferred from a whole workspace instead of the target module.
- Plans missing reasons, modes, executable tasks, or resolved placeholders.
- Implementation accepted from claims rather than scoped diffs and Done-when evidence.

## Workflow

```text
Phase 0  explore -> advisory assessment -> unresolved-only consent
Phase 1  design -> dependency waves -> verifier -> approval
Phase 2  TDD/simplify -> delegated implementation -> scoped evidence
Phase 3  build/existing tests -> selected ask-policy review -> AC evidence
Phase 4  report -> optional structural docs sync
```

## Quality and task contract

New/re-written plans record path origin/evidence; separate recommendations from decisions, sources, and
reasons; and use only `recommended|not-recommended`. Routine work skips both practices without asking.
Risky recommendations state evidence, workflow/regression risk, and effort; only user `Yes` selects TDD
or review. Old-modern auto selections are accepted as input but confirmed/normalized before execution;
legacy requested/not-requested maps to explicit user decisions.

Each new task records Risk, Risk reason, Depth, Mode, Existing-method baseline, and Scaffold. Existing
method TDD proves baseline/characterization GREEN then changed RED/GREEN. Simple-new starts only with a
compile-ready no-logic scaffold. Complex backbones pause for unchanged `design-backbone`, retain its own
approval locks, verify handoff, and resume without duplicate tests.

## Delegation, verification, and design

Planning is read-only except the plan. The main agent does not write production logic except an approved
compile-ready TDD scaffold or trivial verification fix. Explorers/architects scale with complexity; 3+
tasks receive a fresh-eyes executability gate; implementers scale by files in dependency waves. Every
writable dispatch has an exact allowlist and destructive-operation bans; the main agent compares a
working-tree-aware scoped baseline and alone updates status.

`qa-engineer` follows `unit-testing` traceability/test-registry rules. Implementers return `DONE`,
`DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`; blockers get one fresh retry, then become blocked.
Build and existing tests are mandatory. Selected review uses `code-review-lite` with `Escalation Policy:
ask`, receives Global Constraints verbatim, and has at most two rework/re-review loops. The verifier checks
new, old-modern, and legacy shapes; Phase 4 reports evidence and only selected-review verdicts.

## Changelog

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
