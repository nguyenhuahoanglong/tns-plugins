# Design Principles for Scaffolding

The scaffold is where structural quality is decided — interfaces, responsibilities, and dependencies are cheap to shape now and expensive to change after implementation. Apply these throughout Phase 1 (approach) and Phase 2 (shape). They come from the project coding standard and the user's coding philosophy in `CLAUDE.md`.

## SOLID (shapes the structure)

- **Single Responsibility** — each class/module has one reason to change. If a type's name needs "and" to describe it, split it. Don't scaffold god classes.
- **Open/Closed** — extend behavior through abstractions (interfaces, strategy seams), not by editing existing types later. Put the seam in the scaffold where variation is expected.
- **Liskov Substitution** — every implementation must honor its interface/base contract; document the contract in the doc-comment so implementers can't violate it.
- **Interface Segregation** — prefer several small, focused interfaces over one fat one. A consumer should depend only on the methods it uses.
- **Dependency Inversion** — depend on abstractions, not concretions. Declare dependencies as injected interfaces (constructor params); the scaffold wires them by shape, not by `new`-ing concretes inside bodies.

## DRY

Don't repeat structure. If two scaffolded types share a contract, extract a shared interface, base type, or DTO rather than duplicating signatures. Watch for copy-pasted method groups — that's a missing abstraction.

## KISS & YAGNI (guards against over-scaffolding)

- **KISS** — the simplest structure that satisfies the locked design wins. Self-check: *"Would a senior engineer say this is overcomplicated?"* If yes, simplify before writing.
- **YAGNI** — scaffold only what the locked design requires. No speculative methods, interfaces, or extension points "just in case." Every signature must trace directly to a locked decision.

## User coding philosophy (from CLAUDE.md)

- **No silent guessing.** If multiple interpretations of the design exist, present them and let the user choose — don't pick one quietly. (This is why Phase 1 has a hard lock gate.)
- **Push back when warranted.** If a simpler structure exists than what the design implies, say so before scaffolding.
- **Match existing style.** Follow the project's naming, folder layout, and DI patterns even if you'd personally do it differently — read a neighboring file when unsure.
- **Trace every signature to the request.** Each interface/method exists because a locked decision calls for it.
- **Mention, don't fix, unrelated issues.** If you notice smells in surrounding code while scaffolding, note them for the user — don't expand scope.
- **Verifiable hand-off.** State what was produced and how it's checked (the `verify_output.py` guardrail), rather than claiming "done."

## How to use these

In Phase 1, let the principles inform the **approach** options you present (e.g. "a strategy interface here keeps it open/closed"). In Phase 2, sanity-check the proposed shape against SRP, ISP, and YAGNI before showing it. Briefly name the principle when it drives a non-obvious structural choice, so the user understands the rationale — LLMs and humans both reason better from the *why*.
