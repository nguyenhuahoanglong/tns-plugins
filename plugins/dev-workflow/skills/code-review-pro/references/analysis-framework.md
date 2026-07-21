---
name: analysis-framework
description: Evidence, severity, action classification, and synthesis rules for adaptive reviews
---

# Analysis Framework

## Evidence Standard

A finding must identify:

1. changed or affected `file:line` and symbol
2. base behavior and new behavior when behavior changed
3. concrete execution path through caller, consumer, event, state, or test
4. observable impact
5. actionable correction

Code presence is not proof of fulfillment. Speculation without an exposed path belongs in Notes or lower severity.

## Severity

| Severity | Required evidence |
|---|---|
| CRITICAL | proven crash/data loss/security exploit or existing contract/behavior break with exposed consumer |
| HIGH | direct requirement missing/partial, user-visible bug, public/API/schema/event mismatch |
| MEDIUM | maintainability or plausible runtime risk, benign unrelated scope, incomplete exposure evidence |
| LOW | style/documentation/hardening with no demonstrated runtime effect |

Security is not automatically CRITICAL; exploitability and impact must be shown. Build compilation/restore failures are CRITICAL.

Missing direct tests alone are never a finding. Record exactly `use-unit-testing` in Test Evidence; promote only a separately demonstrated behavior failure.

## Requirement Priority

Requirement Validator runs at high reasoning because correctness and behavior preservation outrank specialist style concerns. During synthesis:

- Re-check every Requirement CRITICAL/HIGH against direct AC or regression evidence.
- Re-run caller/consumer/event/state searches before accepting a regression.
- Keep parent context separate from direct scope.
- Downgrade unsupported claims.

### Scope Drift

Preventing unrelated breakage is the top priority, so verify the reverse mapping too: every changed hunk should trace to a direct AC or design-doc requirement. A change justified by no requirement is scope drift — HIGH when it touches shared/public/API/schema/state logic, MEDIUM when isolated/local. Scope-drift findings are advisories ("justify or revert") surfaced for author judgment; they are never Must Fix and never block merge, since the author may have a legitimate reason the requirement did not capture.

## Specialist Synthesis

- Security: require attack path or trust-boundary failure.
- Performance: require execution frequency/scale/resource impact.
- Philosophy: require concrete ownership, coupling, duplication, or complexity impact.
- Standard: cite explicit standard or dominant exemplar pattern.

## Action Classification

Must Fix includes CRITICAL findings and HIGH findings that break behavior, cause runtime failure, violate a direct requirement/contract, or expose material security/performance risk. Give each a stable `[mf:slug]`.

Other HIGH findings are Should Fix. MEDIUM/LOW are Consider unless evidence demonstrates stronger impact.

## Deduplication

Merge findings describing the same cause and affected path. Keep highest severity, combine owners, and preserve strongest evidence. Organize final details by file, never by severity heading.
