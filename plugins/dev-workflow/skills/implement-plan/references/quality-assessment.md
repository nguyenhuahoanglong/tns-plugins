# Project Quality Assessment

Run after Phase 0 exploration against nearest target project/module, not whole workspace. Read its
applicable `AGENTS.md`, manifest/build config, source type, test config, deployment surface, and
ownership signals. Use balanced threshold below.

## Precedence

1. Explicit current user instruction wins: source `user`; reason cites instruction.
2. Existing modern Context fields resolve decision when valid.
3. Existing legacy flag maps as described below.
4. Otherwise use repository evidence: source `auto-assessment`; reason cites concrete files/rules.
5. Missing or conflicting evidence means unresolved. Ask only affected multiple-choice question;
   answer becomes source `user`.

Never silently override explicit choice. If user selects tests despite missing harness, plan includes
minimum test setup needed within scope. If user skips project-mandated quality gate, surface conflict
and ask for resolution rather than silently violating project rule.

## Unit-test decision

Select when either condition holds:

- Project rules require new/updated unit tests for this change.
- Target is executable production code with meaningful unit-test seams **and** project has an
  established runnable unit-test framework/harness.

Skip when any clear condition holds and no rule requires tests:

- Documentation, config-only, generated-only, or metadata-only change.
- Target has no meaningful unit-test seam (for example deployment wiring verified by validation).
- Executable production project has no established runnable unit-test harness. Existing build/test
  verification still remains mandatory; do not create framework setup automatically.

Conflicting evidence example: runnable harness exists but applicable rules prohibit touching tests.
Missing evidence example: unclear whether nearest module's test project is runnable. Ask user only
for unit-test choice.

## Code-review decision

Select when any clear condition holds:

- Project rules require review.
- Change touches shared production code or public contracts.
- Change affects deployment/infra, security, persistent data, migrations, or destructive behavior.

Skip when low-risk scope is clear and no rule requires review:

- Documentation-only or generated-only change.
- Prototype/spike explicitly not intended for production.
- Clearly low-risk personal project change with no shared/deployment/data impact.

Conflicting/missing ownership or risk evidence leaves only code-review choice unresolved.

## Required Context fields

Write exactly:

```text
Unit tests: selected|skipped
Unit tests source: user|auto-assessment
Unit tests reason: <non-empty evidence or explicit instruction>
Code review: selected|skipped
Code review source: user|auto-assessment
Code review reason: <non-empty evidence or explicit instruction>
Depth: TDD|simplify
```

Depth must be `TDD` for selected unit tests and `simplify` for skipped unit tests.

## Legacy plan mapping

Accept existing exact flags without duplicate plan or new question:

| Legacy flag | Modern decision | Source | Reason |
|---|---|---|---|
| `Unit tests: requested` | `selected` | `user` | `Mapped from legacy Context flag: requested` |
| `Unit tests: not requested` | `skipped` | `user` | `Mapped from legacy Context flag: not requested` |
| `Code review: requested` | `selected` | `user` | `Mapped from legacy Context flag: requested` |
| `Code review: not requested` | `skipped` | `user` | `Mapped from legacy Context flag: not requested` |

Normalize fields next time main agent writes existing plan. Until then, downstream flow treats
legacy `requested` as selected and `not requested` as skipped.
