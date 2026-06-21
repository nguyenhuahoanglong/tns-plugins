# PCF (TypeScript) Unit Tests

PCF-specific patterns. AAA, mock-at-boundary, naming, determinism, requirement→test mapping live in `SKILL.md`. There is **no first-party unit-test harness** — `pcf-scripts` / `pac pcf` ships only the visual `npm start watch` harness (and it can't exercise `webAPI`). So you **mock `ComponentFramework.Context` yourself** (factory below) or with a helper lib.

## Setup (ts-jest + jsdom)

```bash
npm i -D jest ts-jest jest-environment-jsdom @types/jest \
  @testing-library/react @testing-library/dom @testing-library/jest-dom @testing-library/user-event
```

```js
// jest.config.js
module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"], // import "@testing-library/jest-dom";
  testMatch: ["**/__tests__/**/*.test.ts?(x)"],
};
```

- Tests live next to source: `Core.Component.PCF/__tests__/*.test.tsx`. Run: `npx jest` (add `"test": "jest"` to `package.json`).
- Community helpers (optional): `Shko-Online/ComponentFramework-Mock` (mocks the whole framework; best maintained), `jest-mock-extended` for `mock<Context>()`. `pcf-react` exists but is unmaintained — prefer the hand-rolled factory below.

## `mockContext()` factory

Build a partial context, typed-cast to satisfy the interface. Stub only what the test touches.

```ts
import { IInputs } from "../generated/ManifestTypes";

export function mockContext(over: Partial<ComponentFramework.Context<IInputs>> = {}) {
  const ctx: Partial<ComponentFramework.Context<IInputs>> = {
    parameters: { /* see dataset stub below */ } as IInputs,
    mode: { isControlDisabled: false, isVisible: true, allocatedWidth: 800, allocatedHeight: 600 } as any,
    factory: {} as any,
    formatting: { formatCurrency: (n) => `$${n}`, formatDecimal: (n) => `${n}` } as any,
    resources: { getString: (k: string) => k, getResource: jest.fn() } as any,
    webAPI: {
      retrieveMultipleRecords: jest.fn().mockResolvedValue({ entities: [] }),
      retrieveRecord: jest.fn().mockResolvedValue({}),
      createRecord: jest.fn().mockResolvedValue({ id: "new-id" }),
      updateRecord: jest.fn().mockResolvedValue({}),
      deleteRecord: jest.fn().mockResolvedValue({}),
    } as any,
    ...over,
  };
  return ctx as unknown as ComponentFramework.Context<IInputs>;
}
```

### Dataset stub (editable grid)

```ts
export function mockDataset(records: Record<string, any>[]) {
  const ids = records.map((_, i) => `r${i}`);
  return {
    columns: [
      { name: "name", displayName: "Name", dataType: "SingleLine.Text", alias: "name", order: 0, visualSizeFactor: 1 },
      { name: "qty",  displayName: "Qty",  dataType: "Whole.None",       alias: "qty",  order: 1, visualSizeFactor: 1 },
    ],
    sortedRecordIds: ids,
    records: Object.fromEntries(ids.map((id, i) => [id, {
      getRecordId: () => id,
      getValue: (c: string) => records[i][c],
      getFormattedValue: (c: string) => String(records[i][c]),
      setValue: jest.fn(),                 // assert grid edits write here
      getNamedReference: () => ({ id: { guid: id } }),
    }])),
    paging: { totalResultCount: ids.length, hasNextPage: false, loadNextPage: jest.fn() },
    loading: false, error: false, refresh: jest.fn(),
  } as unknown as ComponentFramework.PropertyTypes.DataSet;
}
// usage: mockContext({ parameters: { gridDataset: mockDataset([{name:"A",qty:1}]) } as any })
```

## Test the control class directly

```ts
it("init+updateView renders rows and getOutputs reflects edits", () => {
  const control = new EditableGrid();
  const notifyOutputChanged = jest.fn();
  const container = document.createElement("div");
  const ctx = mockContext({ parameters: { gridDataset: mockDataset([{ name: "A", qty: 1 }]) } as any });

  control.init(ctx, notifyOutputChanged, {} as ComponentFramework.Dictionary, container);
  control.updateView(ctx);

  expect(container.querySelectorAll("[role='row']").length).toBeGreaterThan(0);
  control.notifyOutputChanged?.(); // if control exposes; else trigger via interaction
  expect(notifyOutputChanged).toHaveBeenCalled();
  expect(control.getOutputs()).toMatchObject({ /* expected IOutputs */ });
  control.destroy();
});
```

## Test the inner React component (RTL)

Render the component directly with props derived from the mocked dataset — faster and less brittle than driving the class.

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

it("editing a cell propagates the new value", async () => {
  const onCellChange = jest.fn();
  const rows = [{ id: "r0", name: "A", qty: 1 }];
  render(<GridComponent rows={rows} columns={["name", "qty"]} onCellChange={onCellChange} />);

  const cell = screen.getByDisplayValue("1");
  await userEvent.clear(cell);
  await userEvent.type(cell, "5");
  await userEvent.tab(); // commit on blur

  expect(onCellChange).toHaveBeenCalledWith("r0", "qty", "5");
});
```

## Determinism & boundary

- `webAPI` and the host `context` are **the boundary** — always mocked. **Never** call real Dataverse / network from a unit test.
- Pin nondeterminism: `jest.useFakeTimers()`, mock `Date.now`, stub GUID/ID generators. Reset between tests: `afterEach(() => jest.clearAllMocks())`.
- Assert against the mock spies (`setValue`, `webAPI.updateRecord`, `notifyOutputChanged`) — not against side effects you can't observe.

## Legacy PCF (characterization)

No tests yet? Pin current behavior before refactoring: render with a representative `mockDataset` and snapshot the output (`expect(container.innerHTML).toMatchSnapshot()` or RTL `asFragment()`). Snapshots lock the as-is grid render so a refactor that changes output fails loudly. See `references/legacy-characterization.md`.
