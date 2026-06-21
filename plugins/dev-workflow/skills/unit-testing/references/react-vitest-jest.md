# React / TypeScript Unit & Component Tests

React 18 + Ant Design 5 + TypeScript. Frameworks: **Vitest OR Jest** (detect — never assume), React Testing Library (RTL) + `@testing-library/user-event` v14, MSW v2 at the network boundary. SKILL.md covers AAA, mock-at-boundary, naming, determinism, requirement→test mapping — apply those; below is React/TS-specific syntax only.

## Detect the runner — match it, don't migrate

| Signal | Vitest | Jest |
|---|---|---|
| Config file | `vitest.config.*` / `vite.config.*` with `test:` | `jest.config.*` / `jest.preset.*` |
| `package.json` | `vitest` dep, `"test": "vitest"` | `jest` dep, `"jest": {...}` key |
| Imports in tests | `import { vi } from 'vitest'` | globals `jest` |
| Run | `npx vitest run` (CI) / `npx vitest` (watch) | `npx jest` |

API is near-identical: `describe` / `it` / `expect` / `beforeEach`. Differences: mock fn `vi.fn()` vs `jest.fn()`, module mock `vi.mock()` vs `jest.mock()`, timers `vi.useFakeTimers()` vs `jest.useFakeTimers()`. **Use whichever is installed.** Examples below show Vitest; swap `vi`→`jest` for Jest.

## Pure function / reducer / hook (unit)

```ts
// reducer — plain input → output
it('increments count on INCREMENT', () => {
  const next = counterReducer({ count: 1 }, { type: 'INCREMENT' }); // Act
  expect(next.count).toBe(2);                                       // Assert
});

// hook — renderHook from RTL
import { renderHook, act } from '@testing-library/react';
it('toggles open state', () => {
  const { result } = renderHook(() => useToggle(false));
  expect(result.current.open).toBe(false);
  act(() => result.current.toggle());
  expect(result.current.open).toBe(true);
});
```

## Component test (RTL + userEvent v14)

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from 'antd';

it('calls onSubmit when the user clicks Save', async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();                 // v14: setup() once per test
  render(<Button onClick={onSubmit}>Save</Button>);

  await user.click(screen.getByRole('button', { name: /save/i })); // always await

  expect(onSubmit).toHaveBeenCalledTimes(1);
});
```

- Query the way users do: `getByRole`, `getByLabelText`, `getByText`. Avoid `getByTestId` unless no accessible handle exists.
- `getBy*` throws if absent; `queryBy*` returns null (assert absence); **`findBy*`** is async (returns Promise) — use for content that appears after an await/effect: `expect(await screen.findByText(/saved/i)).toBeVisible()`.

### Ant Design 5 gotchas

- **Portals**: `Modal`, `Select`, `Dropdown`, `DatePicker`, `Tooltip` render into `document.body`, not your component subtree. Query `screen.*`, never `container.querySelector`. Modal → `screen.getByRole('dialog')`; Select option → open then `screen.getByText('Option')` or `getByRole('option', { name })`.
- `Select`/`Dropdown` may ignore `userEvent` pointer checks — pass `userEvent.setup({ pointerEventsCheck: 0 })` if clicks no-op.
- AntD reads `matchMedia` / `ResizeObserver` on render — stub them in setup (below) or render throws.

## Mock the API boundary with MSW v2

Prefer MSW over stubbing `fetch`/axios — tests exercise real request code. **v2 API** (changed from v1's `rest`): import `http` + `HttpResponse` from `'msw'`, `setupServer` from `'msw/node'`.

```ts
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  http.get('/api/users', () => HttpResponse.json([{ id: 1, name: 'Ada' }])),
  http.post('/api/users', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());   // drop per-test overrides
afterAll(() => server.close());

it('shows an error row when the list call 500s', async () => {
  server.use(http.get('/api/users', () => new HttpResponse(null, { status: 500 }))); // override
  render(<UserList />);
  expect(await screen.findByText(/failed to load/i)).toBeVisible();
});
```

Use `vi.mock('./module')` / `jest.mock(...)` only for **non-HTTP** modules (clock wrappers, analytics, feature flags) — not for HTTP, which MSW owns.

## Determinism

```ts
// fake timers — wire userEvent to advance them, else clicks hang
const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
vi.useFakeTimers();
vi.setSystemTime(new Date('2026-01-01T00:00:00Z')); // freeze Date
// ... act ...
vi.advanceTimersByTime(1000);
vi.useRealTimers();                                  // restore in afterEach
```

jsdom lacks browser APIs AntD needs — stub once in the test setup file (`vitest.config` `setupFiles` / Jest `setupFilesAfterEach`):

```ts
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (q: string) => ({ matches: false, media: q, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn() }),
});
global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
```

Rules: deterministic fixtures (no `Date.now()`/`Math.random()` in expectations), no real network (MSW `onUnhandledRequest: 'error'` catches leaks), reset mocks/handlers/timers in `afterEach`.

## Legacy React (characterization)

Pinning untested legacy output before a refactor? Snapshot the current render as a regression baseline:

```tsx
it('matches the current rendered output', () => {
  const { asFragment } = render(<LegacyPanel data={fixture} />);
  expect(asFragment()).toMatchSnapshot();
});
```

Caveat: snapshots are brittle and rot fast — keep them **small and targeted** (one component/subtree), never whole-page. They lock in current behavior including bugs, so treat as a temporary safety net, then replace with behavioral assertions. See `references/legacy-characterization.md`.
