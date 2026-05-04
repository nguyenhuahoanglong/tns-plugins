# Interview Guide

Structured question bank for Phase 1. Ask questions across all five categories before locking requirements. Adapt questions to the specific feature — skip irrelevant ones, add domain-specific ones.

## Category 1: Functional

Goal: Understand what the feature does from the user's perspective.

- What is the primary purpose of this feature? What problem does it solve?
- Who uses this feature? What triggers it?
- What are the inputs? Where do they come from?
- What are the expected outputs? What format, where do they go?
- Walk me through the happy path — step by step, what happens?
- Are there alternative flows? (e.g., different inputs produce different behavior)

## Category 2: Design

Goal: Understand how to build it — architecture, patterns, placement.

- Where should this code live? New module, extend existing, or both?
- Are there existing patterns in the codebase I should follow? (e.g., similar features already built)
- What's the data flow? Where does data originate, transform, and persist?
- Are there API contracts to follow? (endpoints, request/response shapes)
- Should this integrate with external services? Which ones, and how?
- Any specific libraries, frameworks, or utilities to use (or avoid)?

## Category 3: Boundaries

Goal: Define explicit scope — what IS and IS NOT part of this feature.

- What is explicitly out of scope for this implementation?
- Are there related features that should NOT be touched?
- Should this feature handle edge cases like [specific scenario], or defer that?
- Is this a complete implementation or a first phase? What comes later?
- Are there any temporary workarounds acceptable for now?

## Category 4: Constraints

Goal: Identify technical and non-technical constraints.

- Are there performance requirements? (response time, throughput, memory)
- Must this be backward compatible with existing code/APIs/data?
- Are there security considerations? (auth, permissions, data sensitivity)
- Any deployment constraints? (environment, configuration, feature flags)
- Does this depend on other work in progress? Any blockers?
- Are there existing tests that must continue to pass?

## Category 5: Acceptance Criteria

Goal: Define concrete, testable conditions for "done."

- How will you verify this feature works correctly?
- What are the specific test scenarios — inputs and expected outputs?
- Are there error scenarios that must be handled gracefully?
- Should this include unit tests, integration tests, or both?
- Is there a build/lint/type-check that must pass?
- Any specific quality bar? (code coverage, no warnings, etc.)

## Interview Technique

**Round 1** — Ask the most important questions from each category (3-5 total). Listen for implicit assumptions and follow up.

**Round 2** — Fill gaps exposed by Round 1 answers. Probe edge cases and design decisions. Confirm your understanding of the architecture.

**Round 3** (if needed) — Resolve remaining ambiguities. Confirm acceptance criteria are concrete and testable. State your full understanding back to the user for validation.

**Completion check:** Can you answer ALL of the following?
- What does this feature do? (functional)
- How is it built? (design)
- What's NOT included? (boundaries)
- What limits exist? (constraints)
- How do we know it's done? (acceptance criteria)

If any answer is "I'm not sure" — ask another question.
