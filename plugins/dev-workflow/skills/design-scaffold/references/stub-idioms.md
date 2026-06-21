# Stub Idioms by Stack

Scaffold means **shape without behavior**. Each member declares its contract and throws/raises a not-implemented marker so the project compiles/imports but nothing runs yet. Match the surrounding project's conventions first; the patterns below are the defaults.

## C# / .NET

- **Stub body:** `throw new NotImplementedException();`
- **Contract doc:** XML doc comments (`/// <summary>`, `<param>`, `<returns>`).
- **Interfaces:** declare the interface fully; implementing classes get stubbed members.
- **DI/flow:** declare constructor-injected dependencies as readonly fields; assign them in the constructor (assignment is structural wiring, not logic — allowed).

```csharp
/// <summary>Posts a GL journal for the suggested stock order.</summary>
/// <param name="orderId">Identifier of the SSO to post.</param>
/// <returns>The created journal's id.</returns>
public Task<Guid> PostJournalAsync(Guid orderId)
{
    throw new NotImplementedException();
}
```

## Python

- **Stub body:** `raise NotImplementedError` (or `...` for abstract/protocol stubs).
- **Contract doc:** docstring stating responsibility, args, returns, raises.
- **Interfaces:** use `abc.ABC` + `@abstractmethod`, or `typing.Protocol` for structural typing.
- **Type hints are required** — they are part of the contract, not implementation.

```python
def post_journal(self, order_id: UUID) -> UUID:
    """Post a GL journal for the suggested stock order.

    Args:
        order_id: Identifier of the SSO to post.
    Returns:
        The created journal's id.
    """
    raise NotImplementedError
```

## TypeScript / React

- **Stub body:** `throw new Error("Not implemented");`
- **Contract doc:** JSDoc + precise TS types (interfaces/types are the contract).
- **React components:** declare props type and signature; body throws or returns `null` with a `// TODO: implement` note — no JSX logic, no hooks wiring beyond declarations.
- **Hooks/services:** declare signature and return type; body throws.

```typescript
/** Posts a GL journal for the suggested stock order. */
export function postJournal(orderId: string): Promise<string> {
  throw new Error("Not implemented");
}
```

## What counts as a violation

Scaffold must contain **no behavior**. These leak implementation and should be flagged:

- Control flow inside a body: `if`/`for`/`while`/`switch`/`try` doing real work.
- Computed returns: `return a + b`, `return items.filter(...)`, building objects from inputs.
- Data transformation, parsing, mapping, validation logic.
- Real external calls (HTTP, DB, file IO) executed rather than declared.

**Allowed structural wiring** (not logic):

- Field/property declarations and constructor assignment of injected dependencies.
- `return null` / `return default` *only* where a stub marker or `// TODO` makes intent explicit (prefer throwing).
- Interface/abstract declarations with no body.
- Enum/DTO/record shapes with fields but no methods carrying logic.
