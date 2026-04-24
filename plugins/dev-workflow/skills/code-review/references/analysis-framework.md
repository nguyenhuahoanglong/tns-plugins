---
name: analysis-framework
description: Shared priority levels and review aspect definitions used across the multi-agent review pipeline and during synthesis
---

# Analysis Framework

> **Note**: Individual agent review criteria are in `agents/`. This framework defines the shared priority levels and review aspects used by the orchestrator during the synthesis phase (Phase 3).

For each changed file, the following aspects are covered by specialized agents:

## Changes Overview

| Field | Value |
|-------|-------|
| **File** | `{relative/path}` |
| **Type** | New / Modified / Deleted / Renamed |
| **Lines** | +{added} / -{removed} |

## Behavior Analysis

- **Before**: Previous behavior (or "N/A - New file")
- **After**: Current behavior after change

Understanding behavioral changes is critical — it reveals whether changes are intentional and whether side effects exist.

## Review Aspects

| Aspect | What to Check |
|--------|---------------|
| **Standards** | Naming conventions, formatting, documentation, consistency with project patterns |
| **Performance** | Algorithm efficiency, resource management, async patterns, redundant operations, N+1 queries |
| **Security** | Input validation, secrets exposure, injection risks (SQL, XSS, command), auth/authz checks |
| **Requirements** | Business logic correctness, edge cases, acceptance criteria fulfillment |
| **Domain** | Business terminology accuracy, architectural pattern compliance, workflow correctness |
| **Maintainability** | Readability, testability, appropriate abstraction level, clear intent |

## Principle Violations

Flag violations of these principles:

| Principle | Focus |
|-----------|-------|
| **SOLID** | Single responsibility, dependency inversion, interface segregation |
| **DRY** | Duplicated logic, copy-paste code, repeated patterns that should be extracted |
| **KISS** | Unnecessary complexity, over-engineering, premature optimization |
| **YAGNI** | Unused code, speculative features, dead code paths |
| **Separation of Concerns** | Layer boundaries, mixing business logic with infrastructure |
| **Fail Fast** | Input validation at boundaries, early error detection, defensive programming |

When flagging a violation:
- Identify the specific code location
- Explain why it's a violation
- Suggest a concrete fix
- Assess the impact (does it cause bugs, or just reduce maintainability?)

## Priority Levels

| Level | Description | Action Required |
|-------|-------------|-----------------|
| **Critical** | Security vulnerabilities, data loss risks, breaking changes, crashes | Must fix before merge |
| **High** | Bugs, significant functional issues, requirement gaps | Should fix before merge |
| **Medium** | Code quality, maintainability, minor logic concerns | Recommended to fix |
| **Low** | Style suggestions, minor improvements, nitpicks | Consider fixing |

### Priority Guidelines
- Security issues are always Critical
- Data loss risks are always Critical
- Bugs that affect users are High
- Performance issues depend on impact (High if user-facing, Medium otherwise)
- Code style issues are Low unless they affect readability significantly

## Priority Tiers (P1-P5)

Tiers reflect **how hard the orchestrator works to verify a finding** during synthesis — they are independent of severity (Critical/High/Medium/Low above). A LOW finding from the Requirement Validator (P1) gets more verification effort than a CRITICAL finding from Convention (P5) gets.

| Tier | Source Agent | Why this tier |
|------|--------------|---------------|
| P1 | Requirement Validator | Did the change actually solve the user's problem? Highest leverage. |
| P2 | Performance Reviewer | Runtime / cost issues that ship to users. |
| P3 | Security Reviewer | Risk surface; must catch before merge. |
| P4 | Philosophy Reviewer | Long-term maintainability. |
| P5 | Convention Checker | Style and project conventions. |

Build Validator findings are not tiered — errors map to CRITICAL, warnings to MEDIUM, and a build failure gates the entire deep-dive phase.

## Synthesis Effort Scaling

For each tier the orchestrator does (scaled — most rigor on P1):

| Action | P1 (Requirement) | P2-P3 (Perf, Security) | P4-P5 (Philosophy, Convention) |
|--------|------------------|------------------------|--------------------------------|
| **Verification** — re-read flagged code | Re-read every flagged file | Spot-check the highest-severity ones | Trust the agent unless finding looks off |
| **Impact analysis** — trace consequences | Trace callers and dependents | Note immediate impact only | Skip |
| **Fix suggestion quality** | Concrete patch sketch | Describe fix with example pattern | One-line note |
| **Cross-checking against spec/standards** | Re-quote the relevant criterion | Check standards doc if cited | Skip |

This is why sub-agents downgraded from opus to sonnet — sonnet handles the broad scan, and the orchestrator (opus) does the heavy verification on what matters most.

## Action Classification

During synthesis, the orchestrator maps individual findings into action buckets for the report. The mapping is NOT a simple priority-to-action translation — it uses business-impact criteria.

### Must Fix (Before Merge)

A finding is "Must Fix" only if it meets one of these criteria:

| # | Criterion | Example |
|---|-----------|---------|
| 1 | **Breaks existing behavior** — code regresses or breaks a function that is out of scope from the current requirement | Refactored shared utility now returns different format, breaking callers |
| 2 | **Causes runtime errors or exceptions** — code will throw on expected execution paths | Unguarded `[0]` on empty list, null reference on expected not-found path |
| 3 | **Does not meet the design requirement** — code fails to fulfill what the task/US specifies | Hardcoded mock value bypassing real routing, missing required feature |
| 4 | **Very critical security or performance** — exploitable vulnerability or guaranteed resource exhaustion | SQL injection, unbounded memory growth per request with no limit |

> **Rationale**: Must Fix is the gate for proceeding to the next step without breaking existing functions. It is about production safety and correctness, not code quality.

### Should Fix

Everything else that is HIGH or has functional impact but does not meet Must Fix criteria:
- Convention violations (even if they may cause build warnings)
- Code quality issues (DRY, SRP, duplicate assignments)
- Security hardening (missing size limits when defaults exist, defense-in-depth)
- Performance improvements (memory optimization, query parallelization)

### Consider

Remaining MEDIUM and LOW findings:
- Style preferences, minor optimizations, documentation gaps
- Suggestions that improve code but have no functional impact
