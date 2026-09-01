# Implement Plan

## Purpose

Explicitly invoked code-development workflow that runs **alongside** the host tool's plan mode. The host
plans; this skill turns that plan into an unattended-executable contract, proves its prerequisites with
real probes, then delegates allowlisted code work and verifies the evidence. Similar intent never
auto-triggers it; non-code primary deliverables route elsewhere.

## Pain Points

- A second planning method competing with Claude Code and Codex plan mode: duplicated interview scripts,
  question banks, and explorer/architect counts.
- A plan path that collides with the host's single-editable-file constraint during plan mode.
- Plans that look complete and then stall mid-run on an expired PAT, an unauthenticated CLI, an
  unreachable endpoint, or a `node_modules` that never had its devDependencies.
- A verifier that only read plan prose and never touched the filesystem, so "executable" meant "well
  worded".
- Contract bloat: fifteen Context fields with two duplicated pairs, and twelve fields on every task
  including a routine one.
- Implementation accepted from claims rather than scoped diffs and Done-when evidence.

## Workflow

```text
Entry    explicit invocation -> code-development eligibility
Phase 1  adopt host or existing plan -> resolve canonical path -> flags as consent
Phase 2  harden to contract -> declare probes -> preflight -> verifier, zero FAIL
Phase 3  approve -> zero FAIL and zero BLOCK -> unverifiable count surfaced
Phase 4  promote -> re-run preflight -> dependency waves -> scoped evidence
Phase 5  build/existing tests -> selected ask-policy review -> AC evidence
Phase 6  report -> evidence-required supporting docs only
```

## Contract, not method

This skill prescribes what a plan must contain, never how the agent arrives at it. Cold invocation
outside plan mode still works: gather what the contract requires by ordinary means.

Context is nine fields — canonical path, origin, evidence, and a decision/source/reason triple for unit
tests and for code review. Tasks carry seven fields always (Status, Depends on, Files, Mode, Description,
Done when, ACs); `Depth` appears only when unit tests are selected, and `TDD reason`, `Existing-method
baseline`, and `Scaffold` only at TDD depth. `Mode` is mandatory at every depth because
`complex-backbone` routes to `design-backbone` regardless. Legacy `requested`/`not requested` and pre-v4
recommendation fields are normalized on read.

`--tdd`, `--review`, `--no-tdd`, and `--no-review` are explicit consent. Without flags, one consolidated
question is asked once after the plan is drafted; silence skips both.

## Autonomy preflight

`scripts/preflight.py` probes prerequisites read-only through a **closed set of probe kinds with typed
arguments and keyed auth commands, never free-form shell** — the plan can declare `auth pac-org`, never a
command line. Kinds: `path` (derived automatically from every task's `Files:`), `command`,
`command-version`, `auth`, `env`, `url`, `node-deps`, `dotnet-restore`, and `manual`. Executables are
resolved with `shutil.which` and invoked by absolute path, because Windows `.CMD` shims otherwise read as
"not installed". Secrets are redacted and output is capped; the script never writes the plan.

States aggregate to `Autonomy`: `verified-ready`, `unverifiable-with-fallback` (every unverifiable probe
needs a `Fallback` that stops and blocks the task rather than prompting), or `verified-blocked`. A blocked
probe is a valid recorded result — `verify_output.py` reports it as **BLOCK** (exit 3), not FAIL (exit 1) —
but it cannot be approved. Preflight runs twice: once to gate approval, once after promotion to gate
fan-out. No freshness field, no TTL.

## Delegation and verification

The autonomy guarantee covers execution through build and test verification. The only sanctioned
interaction points are `code-review-lite` escalation, which pauses by design, and reporting a `blocked`
task; implementers never prompt the user, and `NEEDS_CONTEXT` returns to the main agent. Every writable
dispatch carries an exact allowlist and destructive-operation bans; the main agent compares a
working-tree-aware scoped baseline, alone updates status, and accepts DONE only after diff, file scope, and
Done-when evidence. Implementers map to independent dependency-ready slices, coupled files stay together,
and concurrency caps at three. `qa-engineer` follows `unit-testing` traceability and test-registry rules.
Selected review uses `code-review-lite` with `Escalation Policy: ask`, receives Global Constraints verbatim,
and has at most two rework loops.

## Changelog

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
