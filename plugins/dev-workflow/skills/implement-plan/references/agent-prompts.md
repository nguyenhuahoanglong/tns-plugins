# Agent Prompt Index

Use `agent-prompts-planning.md` for read-only discovery/design and
`agent-prompts-implementation.md` only after approval.

Shared rules:

- Pass plan path, never inline the full plan or source files; point agents to applicable `AGENTS.md`.
- Main agent alone edits plan status; dependency order determines waves and parallelism never bypasses it.
- Before writable dispatch, record working-tree-aware status and scoped diff/file hashes; compare afterward.
- Every writable dispatch includes its exact task-file allowlist and mandatory stop/report footer.
- Quick-check/review receive Global Constraints verbatim. Selected review alone uses
  `Escalation Policy: ask`; never pre-rate findings or tell a reviewer what not to flag.
