# Agent Prompt Index

Use focused references; both are directly linked from `SKILL.md`.

- Phase 0 exploration, Phase 1 architecture, plan quick-check:
  `agent-prompts-planning.md`
- TDD tests, implementation, blockers, verification rework, review rework, docs sync:
  `agent-prompts-implementation.md`

Shared rules:

- Pass plan path, never inline full plan or source files.
- Point agents to applicable `AGENTS.md`.
- Main agent owns plan status writes.
- Dispatch ordering follows `Depends on`; parallelism never replaces dependency correctness.
- Reviewer and quick-check prompts receive Global Constraints verbatim. Never pre-rate findings or
  tell reviewer what not to flag.
