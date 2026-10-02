# User-Facing Reports

Read when presenting the plan, during execution, and at completion. Render these in the user's language;
persist repository artifacts in its required language. Adapt columns to task size. No empty ceremony.

## Before approval: work and readiness

```markdown
Plan: <link>. Outcome: <one sentence>.
Execution readiness: <ready / staged / blocked>. User actions remaining: <exact action or none>.

| Task | Result / owned scope | Depends on | Owner | Model · thinking | Done when |
|---|---|---|---|---|---|
| T1 | <outcome and files/module> | — | <role> | <planned model/effort> | <evidence> |
| T2 | <outcome and files/module> | T1 | <role> | <planned model/effort> | <evidence> |

Quality: <new tests/TDD, existing checks, E2E, review and reasons>.
Access/E2E: <target, account role, real access check, data/cleanup authority>.
Autonomy: <routine choices and recovery allowed; exact circumstances that still require user>.
Routing fallback: <approved equivalent/escalation and cost boundary, or none>.
Approval needed: <concrete plan plus only unresolved consequential choices>.
```

Distinguish proposed selection from an observed runtime. If a role pins another model, show that effective
selection before approval. Never label model/effort verified from a prompt instruction alone.

## During execution: useful updates

```markdown
Progress: <verified complete>/<total tasks>; <running> running; <blocked> blocked.
Current result: <what changed and what evidence establishes it>.

| Task | Owner · actual model/effort | Status | Evidence / next step |
|---|---|---|---|
| T1 | <role · observed model, or inherited/unknown> | Verified | <check/result> |
| T2 | <role · observed model> | Implemented; verifying | <remaining check> |
| T3 | <role · model> | Blocked | <cause; independent work continuing> |

Routing change: <only if changed; reason, old -> new, scope/cost effect>.
User action: <none, or minimum required action and what it unblocks>.
```

Send updates at meaningful task/wave transitions, a new blocker, or changed verification result. Follow
host cadence during long work; no repetitive unchanged tables. For short tasks, two lines suffice.
Use counts, not invented percentages, token costs, or ETAs. Report failure and recovery candidly.

## Completion: result and limits

```markdown
Result: <complete / partial / blocked>. Plan: <link>.

| Task / AC | Result | Evidence |
|---|---|---|
| T1 / AC-1 | <PASS / FAIL / NOT RUN / BLOCKED> | <file, command, observed behavior> |

Changed: <focused summary and important file links>.
Verification: <build/tests/E2E and selected review results; target/build identity where relevant>.
Routing: <effective model/effort and material fallback; unknown values stay unknown>.
Remaining: <unverified acceptance, required human action, or none>.
```

Do not report a review verdict if review was skipped. Do not claim unattended success while leaving
required checks unrun. List publication/deployment state only when it is within requested scope.
