# Timesheet schema and write rules

Names below are logical Dataverse names. Confirm entity sets, navigation
properties, option values, and permissions in the target environment.

## Identity and period

`WhoAmI` returns `UserId`; this is runtime identity. The writer queries the
configured header entity set for active headers whose period contains the task
date and whose employee lookup matches that user. It requires exactly one:

- none: return `PERIOD_NOT_FOUND`, enqueue current work, do not commit;
- many: return `PERIOD_AMBIGUOUS`, enqueue current work, do not guess;
- one: use its primary ID for the detail relationship.

## Lookup resolution

Each `defaults.bindings` entry has a navigation-property key plus `set`,
`code`, `code_field`, and `id_field`. The writer queries:

```text
{set}?$filter={code_field} eq '{code}'&$select={id_field}
```

Missing fields return `LOOKUP_CONFIG_INVALID`; no result returns
`LOOKUP_NOT_FOUND`; multiple results return `LOOKUP_AMBIGUOUS`. Only a single
resolved business-code match may be written.

## Detail payload

The writer builds a normal detail payload with task date, days, description,
location, travel mode, and UTC hours. Relationships are real OData bindings:

```text
cr90e_RefNbr@odata.bind: /{header_entity_set}({header_id})
xts_Employee@odata.bind: /systemusers({WhoAmI.UserId})
{navigation_property}@odata.bind: /{binding.set}({resolved_id})
```

No pseudo relationship fields belong in the payload. Dry-run returns this exact
plan without mutation. Commit uses the same payload for create or update.

## Idempotency and queue

Before mutation, the writer detects an existing detail for current header,
current task date, and current user. It plans `CREATE` when absent or `UPDATE`
when present. Mutation happens only with explicit commit.

If authentication, period, lookup, or write work cannot complete, enqueue the
current report atomically by date. Do not retry old pending records first.
Successful old retries are marked synced; pruning removes only old synced
records. Workbook verification must succeed before pending
sync begins.
