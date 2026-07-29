"""Offline Task 12 contracts for portable timesheets and the pending queue.

Test registry: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Subject: Task 12 timesheet writer, Dataverse identity/lookups, and queue.

TC-063 through TC-066 characterize currently observable behavior.  The other
cases deliberately remain RED until the portable, injected-boundary contract is
implemented.  No test creates a Dataverse client that can contact a service.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import lib_common  # noqa: E402
import pending_timesheets as pending  # noqa: E402
import write_timesheet as writer  # noqa: E402


def _cfg():
    return {
        "timesheet": {
            "org_url": "https://example.crm.dynamics.com",
            "tenant_id": "example-resource-tenant",
            "header_entity_set": "timesheetheaders",
            "detail_entity_set": "timesheetdetails",
            "defaults": {
                "task_days": 1.0, "location_option": 1, "travel_by_option": 2,
                "from_hour_local": "00:30", "to_hour_local": "09:00", "timezone_offset_hours": 7,
                "bindings": {
                    "project": {
                        "set": "projects", "code": "EXAMPLE-PROJECT",
                        "code_field": "cr90e_code", "id_field": "projectid",
                    },
                },
            },
        }
    }


class _Rows:
    def __init__(self, rows): self.rows, self.paths = rows, []
    def get(self, path, prefer=None):
        self.paths.append(path)
        return {"json": {"value": self.rows}}


# TC-063: Current description/date conversion remains stable.
# Steps: 1. Format a bullet block and local midnight-plus-30 date. 2. Read pure results. 3. Verify portal text and UTC rollover.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_063_characterize_description_and_timezone_conversion():
    assert writer.format_description("- #101 First\n- Review") == "#101 First; Review"
    assert writer.local_hour_to_utc(dt.date(2026, 7, 2), "00:30", 7) == "2026-07-01T17:30:00Z"


# TC-064: Current period selection distinguishes one, none, and many matches.
# Steps: 1. Use canned header rows. 2. Resolve for one date. 3. Verify row or actionable stop.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
@pytest.mark.parametrize("rows, outcome", [
    ([{"cr90e_refnbr": "PERIOD-A"}], "PERIOD-A"), ([], "no active timesheet period header"),
    ([{"cr90e_refnbr": "PERIOD-A"}, {"cr90e_refnbr": "PERIOD-B"}], "AMBIGUOUS_PERIOD"),
])
def test_tc_064_characterize_period_selection(rows, outcome):
    cfg = _cfg(); cfg["timesheet"]["employee_id"] = "legacy-example-employee"
    if len(rows) == 1:
        assert writer.resolve_header(_Rows(rows), cfg, dt.date(2026, 7, 2))["cr90e_refnbr"] == outcome
    else:
        with pytest.raises(SystemExit, match=outcome):
            writer.resolve_header(_Rows(rows), cfg, dt.date(2026, 7, 2))


# TC-065: Current detail detection returns its first matching record or none.
# Steps: 1. Query canned detail rows. 2. Detect today’s detail. 3. Verify idempotency choice.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_065_characterize_existing_detail_detection():
    cfg = _cfg(); cfg["timesheet"]["employee_id"] = "legacy-example-employee"
    existing = {"cr90e_xts_timesheet_timesheetdetailid": "example-detail", "cr90e_linenbr": "LINE-1"}
    assert writer.find_existing_detail(_Rows([existing]), cfg, "example-header", dt.date(2026, 7, 2)) is existing
    assert writer.find_existing_detail(_Rows([]), cfg, "example-header", dt.date(2026, 7, 2)) is None


# TC-066: Existing queue retry and prune semantics remain observable.
# Steps: 1. Enqueue then dry/commit through a fake runner. 2. Prune an old synced record. 3. Verify status changes only as expected.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_066_characterize_queue_sync_and_prune(tmp_path):
    queue = tmp_path / "pending.json"
    pending.enqueue(queue, "2026-07-02", "- #101 First", "period unavailable")
    def run(command, cwd):
        if "--check-auth" in command:
            output = '{"status": "AUTH_OK"}'
        elif "--commit" in command:
            output = '{"status": "COMMITTED", "post_write_verification": {"ok": true}}'
        else:
            output = '{"status": "DRY_RUN"}'
        return SimpleNamespace(returncode=0, stdout=output, stderr="")
    assert pending.sync(queue, runner=run, script_path=SCRIPTS_DIR / "write_timesheet.py")["synced"] == 1
    data = pending.load_queue(queue); data["records"][0]["syncedAt"] = "2020-01-01T00:00:00"
    pending.save_queue(queue, data)
    assert [record["date"] for record in pending.prune(queue, 30)] == ["2026-07-02"]


def _portable_writer():
    function = getattr(writer, "write_timesheet", None)
    assert callable(function), "Task 12 must expose write_timesheet with injected auth/Dataverse/time boundaries."
    return function


# TC-019: Use configured resource-org WhoAmI with the Task 8 token.
# Steps: 1. Inject an HTTP response. 2. Resolve identity. 3. Verify exact resource endpoint, bearer use, and user id.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-7, AC-12.
def test_tc_019_uses_resource_org_whoami_and_returns_current_user_id():
    calls = []
    identity = getattr(lib_common, "who_am_i", None)
    assert callable(identity), "Task 12 must expose who_am_i."
    assert identity(_cfg(), "example-access-token", http_get=lambda url, headers: calls.append((url, headers)) or {"UserId": "example-user"}) == "example-user"
    assert calls == [("https://example.crm.dynamics.com/api/data/v9.2/WhoAmI", {"Authorization": "Bearer example-access-token"})]


# TC-020: Permission/auth errors are actionable and never reveal bearer tokens.
# Steps: 1. Inject a forbidden response containing a sentinel token. 2. Resolve WhoAmI. 3. Verify redacted actionable failure.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-7, AC-12, AC-13.
def test_tc_020_redacts_token_when_whoami_permission_is_denied():
    identity = getattr(lib_common, "who_am_i", None)
    assert callable(identity), "Task 12 must expose who_am_i."
    with pytest.raises(RuntimeError) as error:
        identity(_cfg(), "example-access-token", http_get=lambda *_args: (_ for _ in ()).throw(RuntimeError("403 forbidden example-access-token")))
    assert "403" in str(error.value) and "example-access-token" not in str(error.value)


# TC-067: Resolve the Task 8 token, tenant/org identity, and redact it from returned status/errors.
# Steps: 1. Inject Task 8 token and WhoAmI seams. 2. Plan a write. 3. Verify no returned text contains the token.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-7, AC-10, AC-12.
def test_tc_067_consumes_task8_identity_without_token_leakage():
    resolver = getattr(writer, "resolve_timesheet_identity", None)
    assert callable(resolver), "Task 12 must expose resolve_timesheet_identity."
    result = resolver(_cfg(), token_provider=lambda *_args: "example-access-token",
        whoami=lambda cfg, token: {"tenant": cfg["timesheet"]["tenant_id"], "user_id": "example-user"})
    assert result == {"tenant": "example-resource-tenant", "user_id": "example-user"}
    assert "example-access-token" not in json.dumps(result)


@pytest.mark.parametrize("rows, code", [([], "LOOKUP_NOT_FOUND"), ([{"projectid": "one"}], None), ([{"projectid": "one"}, {"projectid": "two"}], "LOOKUP_AMBIGUOUS")])
def test_tc_068_resolves_configured_business_lookup_code_or_returns_actionable_result(rows, code):
    """TC-068: Resolve configured codes only; none/many are actionable and no GUID is configured."""
    resolver = getattr(writer, "resolve_business_lookups", None)
    assert callable(resolver), "Task 12 must expose resolve_business_lookups."
    result = resolver(_Rows(rows), _cfg()["timesheet"]["defaults"]["bindings"])
    if code: assert result["status"] == "FAIL" and result["code"] == code
    else: assert result == {"status": "OK", "lookups": {"project": "one"}}


@pytest.mark.parametrize("headers, expected", [([], "PERIOD_NOT_FOUND"), ([{"id": "header-one"}], "CREATE"), ([{"id": "a"}, {"id": "b"}], "PERIOD_AMBIGUOUS")])
def test_tc_069_plans_header_none_one_many_with_business_identity(headers, expected):
    """TC-069: Header selection is driven by WhoAmI identity, never a configured employee GUID."""
    plan = _portable_writer()(_cfg(), dt.date(2026, 7, 2), "- #101 First", dry_run=True,
        token_provider=lambda *_args: "example-access-token", whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows(headers))
    assert plan["action"] == expected


@pytest.mark.parametrize("existing, action", [(None, "CREATE"), ({"id": "detail-one", "line": "LINE-1"}, "UPDATE")])
def test_tc_070_builds_create_or_update_payload_with_utc_dates(existing, action):
    """TC-070: A date conversion and detected detail produce the exact CREATE/UPDATE dry-run plan."""
    plan = _portable_writer()(_cfg(), dt.date(2026, 7, 2), "- #101 First", dry_run=True,
        token_provider=lambda *_args: "example-access-token", whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows([{"id": "header-one", "projectid": "lookup-one"}]), existing_detail=lambda *_args: existing,
        lookup_resolver=lambda *_args: {"project": "lookup-one"})
    assert plan["action"] == action
    assert plan["payload"]["cr90e_taskdate"] == "2026-07-02"
    assert plan["payload"]["xts_fromhours"] == "2026-07-01T17:30:00Z"


# TC-071: Dry-run returns the exact plan and invokes no create/update mutation.
# Steps: 1. Supply a complete fake Dataverse boundary. 2. Dry-run. 3. Verify plan and no mutation calls.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_071_dry_run_returns_exact_plan_without_mutation():
    mutations = []
    plan = _portable_writer()(_cfg(), dt.date(2026, 7, 2), "- #101 First", dry_run=True,
        token_provider=lambda *_args: "example-access-token", whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows([{"id": "header-one", "projectid": "lookup-one"}]),
        mutate=lambda *args: mutations.append(args))
    assert plan == {
        "status": "DRY_RUN", "action": "CREATE", "date": "2026-07-02",
        "description": "#101 First", "mutated": False,
        "payload": {
            "cr90e_taskdate": "2026-07-02", "cr90e_taskdays": 1.0,
            "cr90e_taskdescription": "#101 First", "xts_location": 1, "xts_travelby": 2,
            "xts_fromhours": "2026-07-01T17:30:00Z", "xts_tohours": "2026-07-02T02:00:00Z",
            "cr90e_RefNbr@odata.bind": "/timesheetheaders(header-one)",
            "xts_Employee@odata.bind": "/systemusers(example-user)",
            "project@odata.bind": "/projects(lookup-one)",
        },
    }
    assert mutations == []


# TC-072: Commit is explicit; only commit=True may pass a CREATE/UPDATE plan to the mutation boundary.
# Steps: 1. Plan a successful write. 2. Commit explicitly. 3. Verify exactly one intended mutation.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_072_commits_only_after_explicit_request():
    mutations = []
    result = _portable_writer()(_cfg(), dt.date(2026, 7, 2), "- #101 First", commit=True,
        token_provider=lambda *_args: "example-access-token", whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows([{"id": "header-one", "projectid": "lookup-one"}]),
        mutate=lambda action, payload: mutations.append((action, payload)) or {"id": "created-one"},
        lookup_resolver=lambda *_args: {"project": "lookup-one"},
        post_write_verifier=lambda *_args: {"ok": True, "count": 1})
    assert result["status"] == "COMMITTED" and [call[0] for call in mutations] == ["CREATE"]


# TC-097: Commit receives exact Dataverse OData relationship payload, never portable pseudo keys.
# Steps: 1. Build a dry-run and commit with identical offline inputs. 2. Capture mutation. 3. Compare exact payload.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_097_commit_mutation_receives_same_valid_odata_payload_without_pseudo_keys():
    mutations = []
    result = _portable_writer()(_cfg(), dt.date(2026, 7, 2), "- #101 First", commit=True,
        token_provider=lambda *_args: "example-access-token", whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows([{"id": "header-one", "projectid": "lookup-one"}]),
        mutate=lambda action, payload: mutations.append((action, payload)) or {"id": "created-one"},
        post_write_verifier=lambda *_args: {"ok": True, "count": 1})
    payload = mutations[0][1]
    assert result["payload"] == payload
    assert payload["cr90e_RefNbr@odata.bind"] == "/timesheetheaders(header-one)"
    assert payload["xts_Employee@odata.bind"] == "/systemusers(example-user)"
    assert payload["project@odata.bind"] == "/projects(lookup-one)"
    assert not {"header_id", "employee_id", "lookups"} & set(payload)


def test_commit_fails_when_post_write_query_finds_no_exact_row():
    result = _portable_writer()(
        _cfg(),
        dt.date(2026, 7, 2),
        "- #101 First",
        commit=True,
        token_provider=lambda *_args: "example-access-token",
        whoami=lambda *_args: "example-user",
        dataverse_factory=lambda *_args: _Rows(
            [{"id": "header-one", "projectid": "lookup-one"}]
        ),
        mutate=lambda *_args: {"id": "created-one"},
        lookup_resolver=lambda *_args: {"project": "lookup-one"},
        post_write_verifier=lambda *_args: {"ok": False, "count": 0},
    )

    assert result["status"] == "FAIL"
    assert result["code"] == "POST_WRITE_VERIFICATION_FAILED"
    assert result["mutated"] is True


# TC-098: Lookups require explicit configured query/id fields and return actionable outcomes.
# Steps: 1. Resolve configured lookup with a fake client. 2. Verify filter/select fields. 3. Check missing/none/many stops.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_098_lookup_resolver_requires_explicit_fields_and_uses_them_in_query():
    resolver = getattr(writer, "resolve_business_lookups", None)
    assert callable(resolver), "Task 12 must expose resolve_business_lookups."
    rows = _Rows([{"projectid": "lookup-one"}])
    valid = {"project": {"set": "projects", "code": "P-01", "code_field": "cr90e_code", "id_field": "projectid"}}
    assert resolver(rows, valid) == {"status": "OK", "lookups": {"project": "lookup-one"}}
    assert rows.paths == ["projects?$filter=cr90e_code eq 'P-01'&$select=projectid"]
    for binding in (
        {"set": "projects", "code": "P-01", "id_field": "projectid"},
        {"set": "projects", "code": "P-01", "code_field": "cr90e_code"},
        {"set": "projects", "code": "P-01", "code_field": " ", "id_field": "projectid"},
    ):
        assert resolver(_Rows([]), {"project": binding}) == {
            "status": "FAIL", "code": "LOOKUP_CONFIG_INVALID", "lookup": "project"
        }
    assert resolver(_Rows([]), valid)["code"] == "LOOKUP_NOT_FOUND"
    assert resolver(_Rows([{"projectid": "one"}, {"projectid": "two"}]), valid)["code"] == "LOOKUP_AMBIGUOUS"


# TC-073: Queue persistence is atomic JSON and same-date enqueue is idempotent.
# Steps: 1. Enqueue twice at the same date with injected local boundaries. 2. Read JSON. 3. Verify one current record and schema.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-10, AC-12.
def test_tc_073_queue_is_atomic_schema_and_same_date_idempotent(tmp_path):
    manager = getattr(pending, "enqueue_current", None)
    assert callable(manager), "Task 12 must expose enqueue_current with injected atomic JSON boundaries."
    queue, writes = tmp_path / "pending.json", []

    def atomic_writer(path, payload):
        writes.append(Path(path))
        lib_common.save_json_atomic(path, payload)

    manager(queue, "2026-07-02", "- #101 First", "AUTH_REQUIRED",
        now=lambda: "2026-07-02T10:00:00", json_reader=pending.load_queue,
        atomic_json_writer=atomic_writer)
    manager(queue, "2026-07-02", "- #102 Replacement", "PERIOD_NOT_FOUND",
        now=lambda: "2026-07-02T10:05:00", json_reader=pending.load_queue,
        atomic_json_writer=atomic_writer)

    data = pending.load_queue(queue)
    assert writes == [queue, queue]
    assert data["version"] == 1 and len(data["records"]) == 1
    assert data["records"] == [{
        "id": "2026-07-02", "date": "2026-07-02", "todayBlock": "- #102 Replacement",
        "description": "#102 Replacement", "reason": "PERIOD_NOT_FOUND", "status": "pending",
        "attempts": 0, "createdAt": "2026-07-02T10:00:00", "updatedAt": "2026-07-02T10:05:00",
        "lastError": "PERIOD_NOT_FOUND", "syncedAt": None,
    }]


def test_tc_074_enqueues_current_before_retrying_old_pending_and_on_auth_failure(tmp_path):
    """TC-074: Current failure enqueues before old retries; auth/current failures do not lose current work."""
    flow = getattr(pending, "sync_after_current", None)
    assert callable(flow), "Task 12 must expose sync_after_current."
    events = []
    result = flow(tmp_path / "pending.json", current=lambda: {"status": "AUTH_REQUIRED"}, enqueue=lambda: events.append("enqueue"), retry=lambda: events.append("retry"))
    assert result["status"] == "QUEUED" and events == ["enqueue"]


def test_tc_075_partial_retry_keeps_pending_attempts_and_error_and_success_marks_synced(tmp_path):
    """TC-075: A failed old retry remains pending; a later success becomes synced through injected writer/time."""
    retry = getattr(pending, "retry_records", None)
    assert callable(retry), "Task 12 must expose retry_records."
    records = [{"date": "2026-07-01", "status": "pending", "attempts": 0}]
    failed = retry(records, submit=lambda *_args: (_ for _ in ()).throw(RuntimeError("period unavailable")), now=lambda: "2026-07-02T10:00:00")
    assert failed[0]["status"] == "pending" and failed[0]["attempts"] == 1 and "period unavailable" in failed[0]["lastError"]
    synced = retry(failed, submit=lambda *_args: {"status": "COMMITTED"}, now=lambda: "2026-07-03T10:00:00")
    assert synced[0]["status"] == "synced" and synced[0]["syncedAt"] == "2026-07-03T10:00:00"


def test_tc_076_prunes_only_old_synced_and_lists_records_in_stable_order():
    """TC-076: Prune cannot remove pending/recent records and list output is date-stable."""
    list_records = getattr(pending, "list_records", None); prune_records = getattr(pending, "prune_records", None)
    assert callable(list_records) and callable(prune_records), "Task 12 must expose pure list/prune seams."
    records = [{"date": "2026-07-02", "status": "pending"}, {"date": "2026-06-01", "status": "synced", "syncedAt": "2026-06-01T00:00:00"}, {"date": "2026-07-01", "status": "synced", "syncedAt": "2026-07-01T00:00:00"}]
    kept = prune_records(records, now=lambda: dt.datetime(2026, 7, 27), days=30)
    assert [record["date"] for record in kept] == ["2026-07-02", "2026-07-01"]
    assert [record["date"] for record in list_records(kept)] == ["2026-07-01", "2026-07-02"]


# TC-079: The public CLI uses the portable execution/auth seams, not legacy config GUID helpers.
# Steps: 1. Load config with no employee ID or binding IDs. 2. Invoke dry-run, commit, or auth-preflight. 3. Verify one intended injected boundary and stable result.
# Design: portable-git-daily-report-dev-workflow.md Task 12, AC-7, AC-10, AC-12.
@pytest.mark.parametrize(
    ("argv", "expected_execute", "expected_auth", "expected_result"),
    [
        (["--description", "- #101 First", "--date", "2026-07-02"],
         {"date": dt.date(2026, 7, 2), "description": "- #101 First", "commit": False, "dry_run": True},
         [], {"status": "DRY_RUN"}),
        (["--description", "- #101 First", "--date", "2026-07-02", "--commit"],
         {"date": dt.date(2026, 7, 2), "description": "- #101 First", "commit": True, "dry_run": False},
         [], {"status": "COMMITTED"}),
        (["--check-auth"], None, [False], {"status": "AUTH_OK"}),
    ],
    ids=["dry-run", "commit", "auth-preflight"],
)
def test_tc_079_cli_routes_only_through_portable_execute_or_auth_checker(
    argv, expected_execute, expected_auth, expected_result
):
    config = _cfg()  # Deliberately has no legacy employee_id or lookup binding id.
    execute_calls, auth_calls = [], []

    def execute(received_config, date, description, *, commit, dry_run):
        execute_calls.append({
            "config": received_config, "date": date, "description": description,
            "commit": commit, "dry_run": dry_run,
        })
        return {"status": "COMMITTED" if commit else "DRY_RUN"}

    def auth_checker(received_config, *, interactive):
        auth_calls.append((received_config, interactive))
        return {"status": "AUTH_OK"}

    result = writer.main(
        argv=argv, config_loader=lambda _path: config, execute=execute, auth_checker=auth_checker,
    )

    assert result == expected_result
    if expected_execute is None:
        assert execute_calls == []
        assert auth_calls == [(config, expected_auth[0])]
    else:
        assert auth_calls == []
        assert execute_calls == [{"config": config, **expected_execute}]
