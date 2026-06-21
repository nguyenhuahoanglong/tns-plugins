# Unit Testing

## Purpose

Generates best-practice unit and component tests for the team's stacks — C# (.NET 8 Azure Functions, Dataverse plugins, class libs) via xUnit, and React/TypeScript + PCF via Vitest/Jest + React Testing Library. It leads with *strategy* (what to test, how to protect existing behavior) rather than syntax: it detects the project's existing framework, maps each test to a requirement or observed behavior, supports spec-first generation so tests can be written in parallel while code is implemented, and — most importantly — produces **characterization tests** that pin the current behavior of legacy code so future changes can't silently break it. End-to-end browser testing is intentionally out of scope (handled by `qa-engineer`'s `e2e` phase + `browser-skill`).

## Pain Points Addressed

- **Legacy regressions:** no safety net before refactoring untested code → characterization tests pin current behavior.
- **Framework guessing:** tests written for the wrong runner (Jest vs Vitest) → `detect_test_framework.py` reads the project and matches it.
- **Untraceable coverage:** tests that don't map to requirements → enforced requirement→test mapping.
- **Sequential bottleneck:** waiting for code before tests can start → spec-first/parallel mode generates red tests from acceptance criteria.
- **Thin guidance:** the prior qa-engineer agent had ~15 lines on unit testing → deep per-stack references with current-API examples.

## Design Notes

- **Skill, not a new agent.** Decided with the user: this is the reusable "how"; the existing `qa-engineer` agent is the executor and now invokes this skill in its `unit-tests` phase. Avoids a competing agent (DRY).
- **Scope = unit + component only.** E2E/Playwright stays in `qa-engineer`/`browser-skill` to prevent duplication.
- **Legacy = characterization (golden master), Feathers' method.** Chosen over pure snapshot testing as the primary path; snapshots offered as a faster variant for complex output.
- **Stack references grounded against current docs:** FakeXrmEasy v3 (`MiddlewareBuilder`, license required), FluentAssertions v8 licensing caveat, MSW v2 `http` API, userEvent v14, PCF `ComponentFramework-Mock` helper.
- Integrates automatically with `implement-feature` / `implement-plan` because those already dispatch `qa-engineer`.

## Changelog

### 2026-06-21 - Initial
- Created skill: Unit Testing (SKILL.md + 5 references + 2 scripts + evals).
- Motivation: user wanted requirement-covering unit tests for backend + frontend, runnable in parallel with implementation, with a concrete strategy for protecting legacy code from future regressions.
- References: `best-practices.md`, `csharp-xunit.md`, `react-vitest-jest.md`, `pcf-testing.md`, `legacy-characterization.md`.
- Scripts: `detect_test_framework.py` (stack/framework detection), `verify_output.py` (output guardrail).
- Companion edit: `qa-engineer` agent updated to invoke this skill and to add legacy + spec-first modes.

### 2026-06-21 - Add existing-suite maintenance
- Added SKILL.md **Step 2: Audit existing tests** — locate existing tests for the target, baseline the suite, then decide per behavior leave/update/add/flag (so the skill maintains the suite instead of duplicating or leaving stale tests).
- Added `best-practices.md` → *Maintaining an existing suite* (don't weaken passing tests, treat red as evidence, no duplicates, characterization tests are load-bearing).
- Extended `verify_output.py` with `--existing <dir>` to WARN on generated test names that collide with existing ones; added best-effort C#/JS test-name extraction.
- Renumbered subsequent SKILL.md steps (Write→4, Spec-first→5, Verify Output→6).
- Why: user asked whether the skill checks existing tests to maintain the right ones — it didn't explicitly; this closes that gap.
