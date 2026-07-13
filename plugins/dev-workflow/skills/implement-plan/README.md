# Implement Plan

## Purpose

Self-contained planning and implementation workflow. It explores nearest target project, assesses
unit-test and review needs, writes plan, stops for approval, delegates work, then verifies evidence.

## Pain Points

- Repetitive preference questions even when project evidence is decisive.
- Quality choices inferred from whole workspace instead of target module.
- Plans with missing reasons, inconsistent TDD/review flows, or unresolved placeholders.
- Implementation accepted from agent claims without scoped diff and Done-when evidence.

## Workflow

```text
Phase 0  explore -> quality assessment -> unresolved-only interview
Phase 1  design -> actionable tasks -> write/verify plan
Gate     explicit user approval
Phase 2  optional TDD -> delegated implementation -> verify before accept
Phase 3  mandatory build/existing tests -> selected review -> AC evidence
Phase 4  report -> optional structural docs sync
```

## Quality assessment

Explicit user choice wins. Otherwise Phase 0 evaluates nearest target project/module:

- Unit tests selected for executable production code with meaningful seams and established runnable
  harness, or when project rules require them.
- Unit tests skipped for docs/config/generated-only work, missing meaningful seams, or no established
  harness. Existing suite and build still run.
- Code review selected for shared production code, public contracts, deployment/infra/data/security
  risk, or project mandate.
- Code review skipped for docs/generated-only work, prototypes, or clearly low-risk personal work.
- Missing/conflicting evidence asks only unresolved choice.

Plans record selected/skipped, user/auto-assessment source, reason, and TDD/simplify depth. Legacy
requested/not requested flags map without duplicate questions and normalize on next write.

## Verification contract

`scripts/verify_output.py` checks exact quality fields, non-empty reasons, depth consistency,
TDD/qa-engineer consistency, review flow consistency, placeholders, and legacy compatibility.
Project build and existing tests remain mandatory regardless of new-test decision.

## Design notes

- Planning stays read-only except plan file until approval.
- Main agent reads critical source files and reconciles one design.
- Tasks are feature slices with isolated files, explicit dependencies, and mechanical Done-when.
- Agent count scales by files; dependencies determine waves.
- Main agent compares task diff to base SHA before recording completion.
- Review uses `code-review-lite` only when selected; rework capped at two loops.

## Changelog

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
