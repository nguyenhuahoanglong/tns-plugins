---
name: feedback-reception
description: Protocol for receiving code review feedback with technical rigor — verify before implementing, no performative agreement
---

# Feedback Reception

Code review feedback is evaluated technically: verify before implementing, ask before assuming.

## Response Pattern

Read the feedback through before responding to any of it, restate the requirement in your own words
(or ask), and check it against what the codebase actually does. Judge whether it is sound for *this*
codebase, answer with a technical acknowledgment or reasoned pushback, then implement one item at a
time, testing each.

## Responding

Answer feedback with substance: restate the technical requirement, ask a clarifying question, or
push back with reasoning. Agreement on its own is not a response; verification is.

## Handling Unclear Feedback

Ask about every unclear item before implementing any of them: review items are often related, and a
partial reading produces the wrong implementation. Given six items with two unclear, say which four
you understood and ask about the other two rather than starting on the four.

## Source-Specific Handling

Feedback from the user is implemented once understood; still ask when the scope is unclear.

For an external reviewer, check before implementing whether the suggestion is correct for this
codebase, whether it breaks existing functionality, whether the current implementation exists for a
reason, whether it holds on every supported platform and version, and whether the reviewer had the
full context. Push back with technical reasoning where it does not hold. Where you cannot verify it,
say so and name what you would need. Where it conflicts with the user's prior decisions, stop and
discuss it with the user first.

## YAGNI Check for "Professional" Features

When a reviewer asks for something to be "implemented properly", search the codebase for actual
usage first. If nothing calls it, propose removing it instead; if something does, implement it
properly.

## Implementation Order

Clarify the unclear items first, then work blocking issues (breaks, security) before simple fixes
(typos, imports) before complex ones (refactoring, logic). Test each fix individually and confirm no
regressions.

## When to Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with the user's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve the user if architectural

## Acknowledging Correct Feedback

Report the fix and where it landed — `Fixed {what changed} in {location}` — and let the code carry
the rest.

## The Bottom Line

External feedback is a set of suggestions to evaluate, not orders to follow.
