# Implement Plan

## Purpose

Explicitly invoked code-plan execution with early readiness decisions, task-specific delegation,
and verified outcomes. Plan approval remains meaningful; routine execution should need minimal user input.

## Pain Points

- Exact-field contracts and keyword checks created ceremony without proving outcomes.
- E2E account, data, browser, and expected-behavior gaps surfaced after implementation started.
- Automatic backbone handoffs and hardcoded review escalation could reopen planning mid-run.
- Fixed role/model mappings obscured task needs and platform override limitations.
- Progress did not have a reusable user-facing task/evidence format.

## Workflow

Adopt plan -> settle decisions and human dependencies -> show assignments/readiness -> approve once ->
execute dependency-ready work -> verify evidence -> report. Small tasks stay small. Host planning modes,
explicit invocation, code-only eligibility, and protection of unrelated work remain in force.

## Resources

- [SKILL.md](SKILL.md): compact workflow and boundaries.
- [Plan content](references/plan-contract.md) and [template](references/plan-template.md).
- [Readiness](references/autonomy-preflight.md): planning-time auth/E2E and bounded recovery.
- [Routing](references/model-routing.md): researched task/model/thinking choices and platform limits.
- [Delegation](references/agent-prompts.md): scoped implementation and independent QA/review briefs.
- [Reports](references/report-templates.md): assignment, progress, and completion output.

## Validation and compatibility

`scripts/verify_output.py` is an optional structured-template consistency helper. It checks relationships,
ownership and recorded evidence, not semantic quality or permission. Legacy decision values remain readable;
assessment provenance is preserved. Sequential shared-file tasks are allowed; exact unordered overlap fails.
Directory/glob scope still needs semantic review. Flexible host plans need not be rewritten for this parser.

`scripts/preflight.py` is unchanged: closed typed probes, read-only, secret-redacted. A script PASS is not
proof of authenticated app access or feature E2E. Missing checks remain visible. No live model-performance,
latency, or UI-taste improvement is claimed from static validation or policy smoke tests.

## Changelog

### 2026-10-02 - Planning readiness, flexible routing, and progress reports

- Active intent r2 records the user's current requested evolution; original intent and r1 remain unchanged.
- Replaced exact-field/prose-audit gates with minimum outcome requirements and an optional consistency helper.
- Moved foreseeable auth, E2E authority/cases, architecture and downstream consent discovery into planning.
- Added Claude Code, Codex, Copilot and Antigravity routing guidance with dated official sources and runtime limits.
- Added assignment/progress/completion templates; main can own tiny work and serialize shared-file tasks.
- Preserved explicit activation, code-only eligibility, scope protection, QA separation, and bounded recovery.
- Validation: 96 verifier/preflight tests passed; intent/history, YAML, local links and four-platform render
  checks passed (Antigravity format advisory retained). Three isolated policy smoke conditions compared
  candidate/old/no-skill responses; no live performance benchmark. No install, publish, commit or push.

### 2026-09-10 - v4.0.1 - Prompt-audit consistency fixes

- Hard rule 4 now points at the consolidated consent question instead of an "explicit `Yes`", which was
  not a well-formed answer to the four-option question in `plan-contract.md`.
- The `## Verify Output` recap no longer implies a preflight run after final updates; preflight keeps its
  two gates and `verify_output.py` keeps the post-status-update rerun.
- `simple-new` mode choreography names the main agent as the scaffold writer, matching the `scaffolded`
  status and the SKILL.md scaffold carve-out.
- `evals.json` `non_goals` updated to the new consent wording.
- Aligned edit against intent revision 1: purpose, activation, outputs, approval gates, and retry limits
  unchanged. Validated with both unittest suites, `guardrail_check.py`, and `quick_validate.py`.

### 2026-09-21 - Browser E2E routing

- Added a post-implementation routing hint for browser-visible acceptance
  criteria: use `browser-skill` and prefer `chrome-devtools` for headed live
  evidence while preserving project E2E runners and existing gates.

### 2026-09-01 - v4.0.0 - Host-plan-mode adoption and autonomy preflight (breaking)

- Reframed the skill as a plan contract plus autonomous execution engine; removed every planning-method
  rule (interview script, question bank, explorer/architect counts, exploration scaling).
- Added the `host-plan-mode` path origin: draft at the host plan file, promote a copy to
  `.plans/<feature>.md` as the first post-approval write, and never touch the host file again.
- Added `scripts/preflight.py` and `references/autonomy-preflight.md`: typed read-only probes for files,
  commands, auth, endpoints, and dependency state, with the three-state `Autonomy` aggregation.
- Split contract validity from approval readiness in `verify_output.py`: FAIL exits 1, BLOCK exits 3.
- Trimmed Context from fifteen fields to nine and tasks from twelve to seven-plus-conditionals; added one
  normalizer for legacy and pre-v4 input.
- Consolidated eight references into four; accepted `--tdd`/`--review` flags as consent; redefined
  `NEEDS_CONTEXT` so implementers never prompt the user.

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
