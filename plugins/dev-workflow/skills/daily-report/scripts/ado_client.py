"""Small Azure DevOps CLI boundary used by the daily task report."""
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse

# workitemsbatch accepts at most 200 ids per request.
_BATCH_LIMIT = 200
_WANTED_FIELDS = ["System.Id", "System.Title", "System.State", "System.WorkItemType"]


def _resolve_argv(argv):
    """Resolve argv[0] to a real path so Windows console shims stay launchable.

    On Windows the Azure CLI is ``az.CMD``; CreateProcess does not apply PATHEXT,
    so a bare ``az`` raises WinError 2. ``shutil.which`` performs that lookup on
    every platform, which keeps the call portable without resorting to a shell.
    """
    if not argv:
        return argv
    resolved = shutil.which(argv[0])
    return [resolved, *argv[1:]] if resolved else argv


def _default_runner(argv):
    return subprocess.run(_resolve_argv(argv), capture_output=True, text=True, encoding="utf-8")


def _failure(code, project, team, message):
    return {"code": code, "project": project, "team": team, "message": message}


def _load_json(result, project, team):
    if result.returncode:
        message = (result.stderr or result.stdout or "Azure CLI request failed").strip()
        return None, _failure("ADO_QUERY_FAILED", project, team, message)
    try:
        return json.loads(result.stdout or "null"), None
    except (TypeError, json.JSONDecodeError) as error:
        return None, _failure("MALFORMED_JSON", project, team, str(error))


def _project_context(organization, project):
    """Context accepted by every project-scoped command. ``az boards query`` rejects --team."""
    return ["--org", organization, "--project", project, "--output", "json"]


def _team_context(organization, project, team):
    return [*_project_context(organization, project), "--team", team]


def _rest_argv(organization, project, resource, in_file):
    """Build a Work Item Tracking REST call.

    ``az boards query`` is used instead of this only where it works; on some Azure CLI
    builds it exits 0 with no output, so the query path goes through ``az devops invoke``,
    which returns the documented payload.
    """
    return ["az", "devops", "invoke", "--org", organization,
            "--area", "wit", "--resource", resource,
            "--route-parameters", f"project={project}",
            "--http-method", "POST", "--in-file", in_file,
            "--api-version", "7.0", "--output", "json"]


def _post_rest(run, organization, project, resource, body, team):
    """POST a JSON body through the CLI, which accepts a request body only via --in-file."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(body, handle)
        handle.close()
        return _load_json(run(_rest_argv(organization, project, resource, handle.name)), project, team)
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def _hydrate(run, organization, project, team, ids):
    """Resolve ids to field-bearing work items; WIQL alone returns ids without fields."""
    items, failure = [], None
    for start in range(0, len(ids), _BATCH_LIMIT):
        chunk = ids[start:start + _BATCH_LIMIT]
        payload, failure = _post_rest(run, organization, project, "workitemsbatch",
                                      {"ids": chunk, "fields": _WANTED_FIELDS}, team)
        if failure:
            return items, failure
        items.extend((payload or {}).get("value", []))
    return items, None


def _query_without_temp_files(run, organization, project, team, wiql):
    """Query and hydrate with read-only CLI commands that never create request files."""
    encoded_project = urllib.parse.quote(project, safe="")
    url = (
        f"{organization.rstrip('/')}/{encoded_project}"
        "/_apis/wit/wiql?api-version=7.0"
    )
    query_argv = [
        "az", "rest", "--method", "post", "--url", url,
        "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
        "--body", json.dumps({"query": wiql}, separators=(",", ":")),
        "--output", "json",
    ]
    payload, failure = _load_json(run(query_argv), project, team)
    if failure:
        return [], failure
    rows = payload if isinstance(payload, list) else (payload or {}).get("workItems", [])
    items = []
    for row in rows:
        if row.get("fields"):
            items.append(row)
            continue
        identifier = row.get("id")
        if not identifier:
            continue
        show_argv = [
            "az", "boards", "work-item", "show", "--id", str(identifier),
            "--org", organization, "--output", "json",
        ]
        item, failure = _load_json(run(show_argv), project, team)
        if failure:
            return items, failure
        if item:
            items.append(item)
    return items, None


def _teams(ado):
    """Yield (project, team, organization); an entry may override the root organization.

    Projects can live in different Azure DevOps organizations, so each team entry may
    carry its own ``organization``. Entries without one inherit the root value, which
    keeps single-organization configuration working unchanged.
    """
    configured = ado.get("teams", [])
    by_project = {entry["project"]: entry for entry in configured}
    root_organization = ado.get("organization")
    resolved = []
    for project in ado.get("projects", []):
        entry = by_project.get(project)
        if entry is None:
            continue
        resolved.append((project, entry["team"], entry.get("organization") or root_organization))
    return resolved


def _record(item, project):
    fields = item.get("fields") or {}
    return {
        "id": item.get("id"),
        "title": (fields.get("System.Title") or "").strip(),
        "state": fields.get("System.State"),
        "project": project,
        "type": fields.get("System.WorkItemType"),
    }


def gather_current_tasks(config, *, runner=None, no_temp_files=False):
    """Gather configured-team tasks without relying on ambient CLI defaults."""
    ado = config["ado"]
    organization = ado["organization"]
    active_states = {state.lower() for state in ado.get("active_states", [])}
    identity = ado.get("member_identity") or "@Me"
    run = runner or _default_runner
    tasks, skipped, failures = [], [], []

    for project, team, project_organization in _teams(ado):
        # --timeframe current is required: an unfiltered list returns every iteration ever
        # defined, oldest first, so the first path-bearing entry is a years-old sprint.
        iteration_argv = ["az", "boards", "iteration", "team", "list", "--timeframe", "current",
                          *_team_context(project_organization, project, team)]
        try:
            iterations, failure = _load_json(run(iteration_argv), project, team)
        except OSError as error:
            failures.append(_failure("ADO_QUERY_FAILED", project, team, str(error)))
            continue
        if failure:
            failures.append(failure)
            continue
        current = next((item for item in (iterations or []) if item.get("path")), None)
        if current is None:
            failures.append(_failure("ADO_QUERY_FAILED", project, team, "Current iteration was not returned"))
            continue
        wiql = (
            "SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType] "
            "FROM WorkItems WHERE [System.TeamProject] = @project "
            "AND [System.IterationPath] = '" + str(current["path"]).replace("'", "''") + "' "
            "AND [System.AssignedTo] = '" + str(identity).replace("'", "''") + "'"
        )
        try:
            if no_temp_files:
                items, failure = _query_without_temp_files(
                    run, project_organization, project, team, wiql
                )
            else:
                queried, failure = _post_rest(
                    run, project_organization, project, "wiql", {"query": wiql}, team
                )
                if failure is None:
                    identifiers = [
                        row.get("id")
                        for row in (queried or {}).get("workItems", [])
                        if row.get("id")
                    ]
                    items, failure = _hydrate(
                        run, project_organization, project, team, identifiers
                    )
        except OSError as error:
            failures.append(_failure("ADO_QUERY_FAILED", project, team, str(error)))
            continue
        if failure:
            failures.append(failure)
            continue
        for item in items or []:
            record = _record(item, project)
            if record["type"] == "Task" and (record["state"] or "").lower() in active_states:
                tasks.append(record)
            else:
                skipped.append(record)

    tasks.sort(key=lambda record: record["id"] or 0, reverse=True)
    return {"tasks": tasks, "skipped": skipped, "failures": failures}
