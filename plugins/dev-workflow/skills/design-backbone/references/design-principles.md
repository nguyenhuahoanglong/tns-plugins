# Design Principles for Runtime Backbones

Use this reference while exploring existing code and choosing touchpoints. Backbone quality comes from correct ownership and executable flow, not file count.

## Trace before design

Trace both directions around every proposed symbol:

1. Find production entrypoint and caller chain.
2. Follow orchestration into services, repositories/adapters, and external boundaries.
3. Find all implementations, DI registrations, configuration, and tests.
4. Trace outputs forward to consumers and later workflow steps.
5. Compare analogous workflows for established patterns.

Record evidence as paths and symbols. An interface without a production caller or registration is not runtime-ready.

## Map responsibility owners

For each required behavior, answer:

- Which existing type/function owns this responsibility?
- Which callers depend on that owner?
- Which current seam supports variation or test replacement?
- Would a new abstraction duplicate ownership or reverse dependency direction?

Do not create a parallel service because existing code looks inconvenient. Modify the correct owner when responsibility already belongs there. Extract only when doing so clarifies an existing mixed responsibility. Add new ownership only for a genuinely new responsibility.

## Touchpoint decision rules

| Action | Use when | Evidence required |
|---|---|---|
| `reuse` | Existing contract and behavior already satisfy backbone need | Owner, caller, and registration/test evidence |
| `modify` | Existing owner is correct but contract/wiring needs change | Current responsibility plus impacted consumers |
| `extract` | Existing owner mixes separable responsibilities required by design | Current coupling and resulting dependency direction |
| `new` | No existing owner or seam can represent a new responsibility | Searches performed, alternatives rejected, intended consumers |

Every `extract` and `new` decision needs concrete justification in the design document. File-tree symmetry, naming preference, or future flexibility alone are insufficient.

## SOLID and DRY checks

- **SRP:** keep responsibility with the type that has one coherent reason to change; do not build a new god orchestrator.
- **OCP:** use an existing variation seam first; add one only when the locked design requires variation.
- **LSP:** mock and production providers must honor the same contract, including valid data shape and failure semantics.
- **ISP:** expand only contracts used by identified consumers; avoid broad convenience interfaces.
- **DIP:** production orchestration depends on stable abstractions; runtime composition selects providers.
- **DRY:** one business-rule owner. Reuse shared DTOs, validators, sequence providers, and lookup services before adding copies.

## KISS and YAGNI checks

- Choose the smallest change set that runs the locked workflow.
- Do not add a method, interface, factory, provider, or config switch without a requirement and consumer.
- Prefer modifying one correct method over adding a parallel pipeline.
- Keep local mock infrastructure narrow and removable; do not model hypothetical production variants.

## Plan review checklist

- Full current and proposed call chains are named.
- Every touchpoint has an owner and consumer.
- Every new symbol has rejected reuse alternatives.
- DI/config and production entrypoint are included.
- Later workflow steps receive contract-valid deterministic data.
- Tests map to requirements, not implementation details.
- Unrelated smells are reported but unchanged.
