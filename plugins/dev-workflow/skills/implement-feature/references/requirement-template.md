# Requirement Template

Use this template when writing `{artifact-folder}/requirement.md` at the end of Phase 1.

---

```markdown
# Requirement: {Feature Name}

## Source
- **Type**: {work-item | file | inline}
- **Reference**: {Work item ID / file path / "conversation"}
- **Date**: {YYYY-MM-DD}

## Summary

{2-5 paragraphs describing the feature. Written clearly enough that a developer with no prior context can understand what to build. Include the "why" — what problem this solves.}

## Functional Requirements

### FR-1: {Name}
{Description of the functional behavior. Include inputs, processing, and outputs.}

### FR-2: {Name}
{...}

## Design Decisions

Decisions made during the interview that constrain implementation.

| Decision | Rationale |
|----------|-----------|
| {e.g., "Extend existing OrderService"} | {e.g., "Follows existing pattern, avoids new module"} |
| {e.g., "Use React Hook Form for validation"} | {e.g., "Already used in the project"} |

## Boundaries

### In Scope
- {What this feature includes}

### Out of Scope
- {What this feature explicitly excludes}

## Constraints

- {Performance, compatibility, security, deployment constraints}

## Acceptance Criteria

- [ ] AC-1: {Concrete, testable criterion — a qa-engineer must be able to verify this}
- [ ] AC-2: {Include expected inputs and outputs where applicable}
- [ ] AC-3: {...}

## Interview Notes

{Key points from the user interview that provide additional context. Include any ambiguities that were resolved and the user's stated preference.}
```

---

## Writing Guidelines

- **Acceptance criteria must be testable**: "Works correctly" is not testable. "Given input X, returns Y with status 200" is testable.
- **Design decisions must include rationale**: Sub-agents need to understand WHY, not just WHAT.
- **Boundaries must be explicit**: If something is ambiguous, it should be listed in either "In Scope" or "Out of Scope."
- **Interview notes preserve context**: Record decisions that might seem arbitrary without the conversation context.
