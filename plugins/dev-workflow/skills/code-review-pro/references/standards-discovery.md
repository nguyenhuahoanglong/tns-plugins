---
name: standards-discovery
description: How to discover project-specific coding standards and conventions before performing a code review
---

# Standards Discovery

Before reviewing code, discover what standards apply to this project. This ensures findings align with actual project conventions, not just generic best practices.

> **Token rule**: the orchestrator collects **file paths** here (standards docs + exemplar files) and passes them to the Standard Reviewer in the dispatch prompt. The agent reads the content itself â€” never paste standards or exemplar content into the dispatch.

## Discovery Steps

### 1. Search for Instruction Files

Use Glob/Grep to find project-specific standards:

```
Patterns to search:
- **/AGENTS.md
- **/CLAUDE.md
- **/.codex/AGENTS.md
- **/.github/copilot-instructions.md
- **/CONTRIBUTING.md
- **/.editorconfig
- **/*.instructions.md
- **/copilot-instructions.md
- **/coding-standard.md
- **/.eslintrc*
- **/.prettierrc*
- **/pyproject.toml
- **/tslint.json
```

### 2. Check Documentation Directories

Look for structured documentation:

```
Priority directories:
- .docs/domain/      â€” Domain terminology, business rules
- .docs/spec/        â€” Feature specifications, acceptance criteria
- .docs/convention/  â€” Coding standards, architecture decisions
- .github/           â€” PR templates, workflows
- docs/              â€” General project documentation
```

### 3. Examine Existing Code Patterns (Mandatory)

**Always run this step** â€” even when explicit standards exist. Use Glob/Grep to find 2â€“3 sibling files per changed file (same folder, same suffix, same feature folder) and read them for dominant patterns. This is the exemplar discovery step that feeds the Standard Reviewer.

Identify dominant patterns across these categories:
- Naming conventions (camelCase, PascalCase, snake_case)
- File organization and module structure
- Error-handling style (try/catch shape, Result<T> vs exceptions, error propagation)
- Async style (async/await patterns, Task.WhenAll, CancellationToken propagation)
- Logging style (log level conventions, structured logging fields, logger injection)
- DI registration (constructor injection vs service locator vs factory)
- Return-type idioms (Result<T> vs exceptions vs nullable returns)
- Test structure (Arrange/Act/Assert shape, mock framework conventions, test class organization)
- Layer/folder pattern (folder-by-feature vs folder-by-type, layer ownership)
- Import ordering conventions
- Comment style and documentation level

## Priority Order

Apply standards in this order (highest priority first):

1. `.docs/domain/` â€” Domain-specific rules always take precedence
2. `.docs/spec/` â€” Feature specifications for requirement validation
3. `AGENTS.md` / `CLAUDE.md` / `.codex/AGENTS.md` / `.github/copilot-instructions.md` â€” Project-level AI instructions
4. `*.instructions.md` â€” Language/technology-specific standards
5. `.editorconfig` / linter configs â€” Formatting rules
6. Language community conventions â€” Fallback defaults

## What to Extract

The Standard Reviewer (not the orchestrator) extracts these from the discovered files:

| Category | Examples |
|----------|----------|
| **Naming** | Variable, function, file, class naming conventions |
| **Formatting** | Indentation, line length, bracket style |
| **Architecture** | Layer boundaries, dependency rules, patterns |
| **Error Handling** | Try/catch conventions, logging requirements |
| **Testing** | Test naming, coverage expectations, test structure |
| **Domain** | Business terminology, abbreviations, workflow rules |
| **Security** | Input validation, auth patterns, secret handling |

## Fallback

Only applies when **no docs were found AND no neighbor signal exists** (brand-new folder, isolated file with no siblings):
- Use the language's official style guide (PEP 8, Google Style, Airbnb, etc.)
- Note in the review report that no project standards were discovered and no exemplars were available
- Focus review on universal principles (SOLID, DRY, KISS, security)
