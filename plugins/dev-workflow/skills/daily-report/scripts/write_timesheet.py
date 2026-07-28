"""Write today's timesheet detail line to the Dynamics 365 portal (Dataverse Web API).

Resolves the CURRENT period's header dynamically (the header GUID is period-specific —
never hardcode it), then upserts one detail line for today: if a line already exists for
(this header, today, me) it is updated; otherwise a new line is created.

Defaults to --dry-run (prints the resolved header + payload, writes nothing).
Pass --commit to actually write.

Usage:
  python write_timesheet.py --description "- #414982 ..." [--date YYYY-MM-DD]
                            [--commit] [--config PATH]
"""
import argparse, datetime, sys
from lib_common import load_config, get_access_token, Dataverse, who_am_i


def resolve_timesheet_identity(cfg, token_provider=get_access_token, whoami=who_am_i):
    """Resolve the resource-tenant user; deliberately never return the access token."""
    token = token_provider(cfg)
    result = whoami(cfg, token)
    user_id = result.get("user_id") if isinstance(result, dict) else result
    return {"tenant": cfg["timesheet"]["tenant_id"], "user_id": user_id}


def resolve_business_lookups(dv, bindings):
    """Resolve configured business codes to ids, refusing missing or ambiguous matches."""
    resolved = {}
    for name, binding in bindings.items():
        code = binding.get("code")
        field = binding.get("code_field")
        id_field = binding.get("id_field")
        if not isinstance(field, str) or not field.strip() or not isinstance(id_field, str) or not id_field.strip():
            return {"status": "FAIL", "code": "LOOKUP_CONFIG_INVALID", "lookup": name}
        escaped = str(code).replace("'", "''")
        rows = dv.get(f"{binding['set']}?$filter={field} eq '{escaped}'&$select={id_field}").get("json", {}).get("value", [])
        if not rows:
            return {"status": "FAIL", "code": "LOOKUP_NOT_FOUND", "lookup": name, "business_code": code}
        if len(rows) != 1:
            return {"status": "FAIL", "code": "LOOKUP_AMBIGUOUS", "lookup": name, "business_code": code}
        resolved[name] = rows[0].get(id_field)
    return {"status": "OK", "lookups": resolved}


def _portable_header(dv, cfg, today, employee_id):
    ts = cfg["timesheet"]
    flt = (f"_xts_employee_value eq {employee_id} and cr90e_fromperiod le {today.isoformat()} "
           f"and cr90e_toperiod ge {today.isoformat()} and statecode eq 0")
    return dv.get(f"{ts['header_entity_set']}?$filter={flt}").get("json", {}).get("value", [])


def write_timesheet(cfg, today, today_block, *, commit=False, dry_run=False,
                    token_provider=get_access_token, whoami=who_am_i, dataverse_factory=Dataverse,
                    existing_detail=None, lookup_resolver=resolve_business_lookups, mutate=None):
    """Plan an injected timesheet write; mutation is impossible unless ``commit`` is true."""
    # The token is transient: use it for WhoAmI/client construction only, never in a result.
    token = token_provider(cfg)
    who = whoami(cfg, token)
    employee_id = who.get("user_id") if isinstance(who, dict) else who
    identity = {"tenant": cfg["timesheet"]["tenant_id"], "user_id": employee_id}
    dv = dataverse_factory(cfg, token)
    headers = _portable_header(dv, cfg, today, identity["user_id"])
    if not headers:
        return {"status": "FAIL", "action": "PERIOD_NOT_FOUND", "date": today.isoformat(), "mutated": False}
    if len(headers) != 1:
        return {"status": "FAIL", "action": "PERIOD_AMBIGUOUS", "date": today.isoformat(), "mutated": False}
    header = headers[0]
    header_id = header.get("id") or header.get("cr90e_xts_timesheet_timesheetheaderid")
    if existing_detail:
        existing = existing_detail(dv, cfg, header_id, today)
    else:
        candidate = find_existing_detail(dv, cfg, header_id, today, employee_id=identity["user_id"])
        # A real detail query selects one of these detail-specific fields.  This
        # guard also keeps a minimal injected header-only client from becoming a
        # false UPDATE plan.
        existing = candidate if candidate and any(key in candidate for key in (
            "cr90e_xts_timesheet_timesheetdetailid", "cr90e_linenbr", "line")) else None
    lookup_result = lookup_resolver(dv, cfg["timesheet"]["defaults"].get("bindings", {}))
    lookups = lookup_result.get("lookups", lookup_result) if isinstance(lookup_result, dict) else lookup_result
    if isinstance(lookup_result, dict) and lookup_result.get("status") == "FAIL":
        return {"status": "FAIL", "action": lookup_result["code"], "date": today.isoformat(), "mutated": False}
    d = cfg["timesheet"]["defaults"]
    description = format_description(today_block, d.get("description_style", "semicolon"))
    payload = {"cr90e_taskdate": today.isoformat(), "cr90e_taskdays": float(d["task_days"]),
               "cr90e_taskdescription": description, "xts_location": d["location_option"],
               "xts_travelby": d["travel_by_option"],
               "xts_fromhours": local_hour_to_utc(today, d["from_hour_local"], d["timezone_offset_hours"]),
               "xts_tohours": local_hour_to_utc(today, d["to_hour_local"], d["timezone_offset_hours"]),
               "cr90e_RefNbr@odata.bind": f"/{cfg['timesheet']['header_entity_set']}({header_id})",
               "xts_Employee@odata.bind": f"/systemusers({identity['user_id']})"}
    for navprop, binding in d["bindings"].items():
        payload[f"{navprop}@odata.bind"] = f"/{binding['set']}({lookups[navprop]})"
    action = "UPDATE" if existing else "CREATE"
    result = {"status": "DRY_RUN", "action": action, "date": today.isoformat(), "description": description,
              "mutated": False, "payload": payload}
    if not commit:
        return result
    if mutate is None:
        def mutate(action, payload):
            if action == "UPDATE":
                return dv.update(cfg["timesheet"]["detail_entity_set"], existing.get("id") or existing.get("cr90e_xts_timesheet_timesheetdetailid"), payload)
            return dv.create(cfg["timesheet"]["detail_entity_set"], payload)
    result["mutation"] = mutate(action, payload)
    result["status"], result["mutated"] = "COMMITTED", True
    return result


def format_description(today_block, style="semicolon"):
    """Transform the bulleted Today block into the Dynamics cr90e_taskdescription style.

    The portal convention (see references/timesheet-schema.md) joins items with '; ' and drops
    the leading '- '. Bullets are kept for the Excel memo + Teams report, not here.
    """
    if style == "verbatim":
        return today_block.strip()
    lines = [line.strip() for line in today_block.splitlines() if line.strip()]
    lines = [line[2:].strip() if line.startswith("- ") else line for line in lines]
    return "; ".join(lines)


def local_hour_to_utc(date, hhmm, offset_hours):
    h, m = map(int, hhmm.split(":"))
    dt = datetime.datetime(date.year, date.month, date.day, h, m) - datetime.timedelta(hours=offset_hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_header(dv, cfg, today):
    ts = cfg["timesheet"]
    flt = (f"_xts_employee_value eq {ts['employee_id']} "
           f"and cr90e_fromperiod le {today.isoformat()} "
           f"and cr90e_toperiod ge {today.isoformat()} and statecode eq 0")
    r = dv.get(f"{ts['header_entity_set']}?$filter={flt}"
               f"&$select=cr90e_refnbr,cr90e_fromperiod,cr90e_toperiod")
    rows = r["json"].get("value", [])
    if not rows:
        raise SystemExit(f"ERROR: no active timesheet period header found for {today.isoformat()}. "
                         f"Create/open the period in the portal first.")
    if len(rows) > 1:
        listing = "\n".join(
            f"  - {h.get('cr90e_refnbr')} ({h.get('cr90e_fromperiod')} .. {h.get('cr90e_toperiod')})"
            for h in rows)
        raise SystemExit(
            f"AMBIGUOUS_PERIOD: {len(rows)} active timesheet period headers match {today.isoformat()}. "
            f"Cannot pick the right one automatically:\n{listing}\n"
            f"Resolve the overlap in the portal (or narrow the period), then retry.")
    return rows[0]


def find_existing_detail(dv, cfg, header_id, today, employee_id=None):
    ts = cfg["timesheet"]
    employee_id = employee_id or ts["employee_id"]
    flt = (f"_cr90e_refnbr_value eq {header_id} and cr90e_taskdate eq {today.isoformat()} "
           f"and _xts_employee_value eq {employee_id}")
    r = dv.get(f"{ts['detail_entity_set']}?$filter={flt}"
               f"&$select=cr90e_xts_timesheet_timesheetdetailid,cr90e_taskdescription,cr90e_linenbr")
    rows = r["json"].get("value", [])
    return rows[0] if rows else None


def build_payload(cfg, header, today, description):
    ts = cfg["timesheet"]
    d = ts["defaults"]
    header_id = header["cr90e_xts_timesheet_timesheetheaderid"]
    payload = {
        "cr90e_taskdate": today.isoformat(),
        "cr90e_taskdays": float(d["task_days"]),
        "cr90e_taskdescription": description,
        "xts_location": d["location_option"],
        "xts_travelby": d["travel_by_option"],
        "xts_fromhours": local_hour_to_utc(today, d["from_hour_local"], d["timezone_offset_hours"]),
        "xts_tohours": local_hour_to_utc(today, d["to_hour_local"], d["timezone_offset_hours"]),
        f"cr90e_RefNbr@odata.bind": f"/{ts['header_entity_set']}({header_id})",
        f"xts_Employee@odata.bind": f"/systemusers({ts['employee_id']})",
    }
    for navprop, b in d["bindings"].items():
        payload[f"{navprop}@odata.bind"] = f"/{b['set']}({b['id']})"
    return payload


def main(argv=None, config_loader=load_config, execute=write_timesheet, auth_checker=get_access_token):
    """Route CLI requests through portable authentication and write boundaries."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--description", help="Task Description for the timesheet line "
                                          "(required unless --check-auth)")
    ap.add_argument("--date", help="override date (YYYY-MM-DD)")
    ap.add_argument("--commit", action="store_true", help="actually write (default is dry-run)")
    ap.add_argument("--check-auth", action="store_true",
                    help="preflight: exit 0 if a token can be acquired silently, "
                         "else exit non-zero with AUTH_REQUIRED (never prompts)")
    ap.add_argument("--config")
    args = ap.parse_args(argv)

    cfg = config_loader(args.config)

    if args.check_auth:
        auth_checker(cfg, interactive=False)
        print("AUTH_OK")
        return {"status": "AUTH_OK"}

    if not args.description:
        ap.error("--description is required unless --check-auth is given")

    today = (datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
             if args.date else datetime.date.today())

    result = execute(
        cfg,
        today,
        args.description,
        commit=args.commit,
        dry_run=not args.commit,
    )
    print(f"TIMESHEET: {result.get('status', 'UNKNOWN') if isinstance(result, dict) else 'COMPLETE'}")
    return result


if __name__ == "__main__":
    main()
