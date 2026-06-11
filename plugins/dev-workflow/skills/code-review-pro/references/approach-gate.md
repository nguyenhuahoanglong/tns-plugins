---
name: approach-gate
description: Orchestrator rubric for the Approach Gate (Phase 2a) — strict REJECT bar to prevent false-positive rejections, with PASS-with-concerns as the safe default
---

# Approach Gate

The orchestrator runs this gate **inline** during Phase 2a (before dispatching deep-dive agents). The goal is to catch architecturally broken PRs early so deep-dive tokens are not wasted on code that will be rejected anyway.

## Inputs

- Full diff with context (collected in Phase 1)
- Work item details — title, description, acceptance criteria, parent
- Discovered standards files — AGENTS.md, CLAUDE.md, .editorconfig, *.instructions.md

If no work item is available, the gate cannot reliably assess intent — auto-PASS with note "approach gate inconclusive — no work item context". Build Gate still runs.

## REJECT Bar — all 4 must hold

The bar is intentionally strict. Rejecting a valid PR wastes more time than running a wasted deep dive. When in doubt → PASS.

| # | Criterion | What it means |
|---|-----------|---------------|
| 1 | Named architectural violation | A specific layer or boundary is crossed — e.g., business logic in DTO, DB access from view, client-side validation when spec requires server-side |
| 2 | Structural problem | Cannot be fixed by tweaking lines inside the diff — would require a different design |
| 3 | Citable spec or convention | You can cite a specific acceptance criterion, AGENTS.md rule, or stated standard being violated |
| 4 | High confidence | You would push back if a senior engineer disagreed with the rejection |

If ALL four hold → REJECT. Otherwise → PASS.

## PASS Default

PASS does NOT mean "no concerns." It means "concerns are addressable inside the diff." Any approach concerns short of the REJECT bar should still surface — but as P1 findings during synthesis, not as a gate failure.

## Examples

**Should REJECT:**
- Spec says BE validation; PR adds client-side validation only
- Should be a Dataverse plugin; implemented as JS web resource
- Spec asks for an API integration; PR scrapes UI
- Business logic placed in PCF control; spec requires plugin

**Should NOT REJECT (flag during deep dive instead):**
- Naming inconsistency
- Missed edge case
- Suboptimal-but-functional algorithm
- Pattern violation that's reversible by editing the same lines
- Style preference

## Output

The orchestrator produces this structured decision (used downstream by `short-reports.md` and synthesis):

```
Gate: PASS | REJECT
Confidence: high | medium | low
Reason: {one sentence}
Recommendation: {refactor approach / restart from spec / proceed to deep dive}
Evidence:
- {file}:{line} — {what's wrong}
- AGENTS.md / standard: "{rule text}"
- AC \#{n}: "{criterion text}"
```

On PASS with concerns, append a "Pre-Findings (P1)" block listing approach observations the Requirement Validator should consider.

## REJECT Override

The orchestrator runs in conversation. If the user disputes a REJECT, they can reply directly — the orchestrator re-evaluates against the bar with the new context and may proceed to deep dive. No flag or restart needed.
