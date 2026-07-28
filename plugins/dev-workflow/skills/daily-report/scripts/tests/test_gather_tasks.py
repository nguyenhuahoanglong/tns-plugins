"""TDD contracts for the portable Azure DevOps daily-task gatherer.

Test registry: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Subject: gather_tasks.py and the future ado_client.py boundary
Design: .plans/portable-git-daily-report-dev-workflow.md (Task 10; AC-1, AC-8, AC-12)

TC-022 and TC-023 characterize observable legacy behavior.  TC-024 onward
specify the portable Azure CLI contract and are intentionally RED until Task
10 implementation supplies ``ado_client.py`` and the injected runner seam.
No test makes an Azure DevOps, PowerShell, or network call.
"""
import ast
import importlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_tasks  # noqa: E402


def _legacy_config() -> dict:
    return {
        "ado": {
            "sprint_script": "legacy-sprint.ps1",
            "projects": ["Project One"],
            "member_email": "dev@example.test",
            "active_states": ["Active", "In Progress"],
        }
    }


def _portable_config(member_identity: str = "dev@example.test") -> dict:
    return {
        "ado": {
            "organization": "https://dev.azure.com/example-org",
            "projects": ["Project One", "Project Two"],
            "teams": [
                {"project": "Project One", "team": "Team One"},
                {"project": "Project Two", "team": "Team Two"},
            ],
            "member_identity": member_identity,
            "active_states": ["Active", "In Progress"],
        }
    }


def _portable_client():
    """Load the Task 10 public boundary, failing clearly while it is absent."""
    try:
        return importlib.import_module("ado_client")
    except ModuleNotFoundError as error:
        pytest.fail(
            "Task 10 must provide ado_client.py with gather_current_tasks(config, *, runner). "
            "The portable Azure CLI boundary is not implemented yet."
        )
        raise error  # pragma: no cover - pytest.fail raises


def _completed(argv, payload, returncode=0, stderr=""):
    return subprocess.CompletedProcess(
        argv,
        returncode,
        stdout=json.dumps(payload, ensure_ascii=False),
        stderr=stderr,
    )


def _current_iteration(project: str) -> list[dict]:
    return [{"id": f"{project}-iteration", "path": f"{project}\\Sprint 42"}]


def _work_items(*items: dict) -> list[dict]:
    return list(items)


def _item(identifier: int, title: str, state: str, work_item_type: str = "Task") -> dict:
    return {
        "id": identifier,
        "fields": {
            "System.Title": title,
            "System.State": state,
            "System.WorkItemType": work_item_type,
        },
    }


# ---- REST boundary helpers -------------------------------------------------
# The query path uses `az devops invoke` because `az boards query` exits 0 with no
# output on some Azure CLI builds. WIQL returns ids only, so field values come from a
# second `workitemsbatch` call, and the request body travels via --in-file.


def _is_iteration(argv: list[str]) -> bool:
    return argv[1:5] == ["boards", "iteration", "team", "list"]


def _resource(argv: list[str]) -> str | None:
    return argv[argv.index("--resource") + 1] if "--resource" in argv else None


def _route_project(argv: list[str]) -> str:
    return argv[argv.index("--route-parameters") + 1].split("=", 1)[1]


def _request_body(argv: list[str]) -> dict:
    return json.loads(Path(argv[argv.index("--in-file") + 1]).read_text(encoding="utf-8"))


def _fake_ado(items_for, *, iteration=_current_iteration, on_call=None):
    """Model the three real calls: team iteration list, WIQL ids, then batch hydrate."""

    def runner(argv):
        assert isinstance(argv, list) and all(isinstance(part, str) for part in argv)
        if on_call is not None:
            on_call(argv)
        if _is_iteration(argv):
            return _completed(argv, iteration(argv[argv.index("--project") + 1]))
        project = _route_project(argv)
        if _resource(argv) == "wiql":
            return _completed(argv, {"workItems": [{"id": item["id"]} for item in items_for(project)]})
        if _resource(argv) == "workitemsbatch":
            wanted = set(_request_body(argv)["ids"])
            return _completed(argv, {"value": [i for i in items_for(project) if i["id"] in wanted]})
        raise AssertionError(f"unexpected Azure CLI invocation: {argv}")

    return runner


# TC-022: Legacy-export normalization filters configured active states and sorts active IDs newest first.
# Steps:
#   1. Supply legacy PowerShell-export JSON containing active and non-active items.
#   2. Normalize those in-memory exported records through the portable pure seam.
#   3. Verify active records are descending by ID and the other record is skipped.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
def test_tc_022_characterize_exported_items_filters_states_and_sorts_newest_first():
    # Arrange
    items = [
        {"Id": 102, "Title": "  Newer active  ", "State": "Active", "ProjectName": "Project One", "WorkItemType": "Task"},
        {"Id": 98, "Title": "In progress", "State": "In Progress", "ProjectName": "Project One", "WorkItemType": "Task"},
        {"Id": 101, "Title": "Closed", "State": "Closed", "ProjectName": "Project One", "WorkItemType": "Task"},
    ]
    normalizer = getattr(gather_tasks, "normalize_exported_items", None)
    assert callable(normalizer), (
        "Task 10 must expose normalize_exported_items(items, active_states) so the captured "
        "legacy export behavior remains pure and does not retain a shell execution path."
    )

    # Act
    tasks, skipped = normalizer(items, ["Active", "In Progress"])

    # Assert
    assert [task["id"] for task in tasks] == [102, 98]
    assert tasks[0]["title"] == "Newer active"
    assert [task["id"] for task in skipped] == [101]


# TC-023: Legacy bullet output keeps the current Teams-compatible line format.
# Steps:
#   1. Supply normalized active-task records.
#   2. Format bullets through the existing public helper.
#   3. Verify each task is emitted as a numbered Markdown bullet.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
def test_tc_023_characterize_legacy_format_bullets_uses_id_and_title():
    # Arrange
    tasks = [{"id": 102, "title": "Newer active"}, {"id": 98, "title": "In progress"}]

    # Act
    bullets = gather_tasks.format_bullets(tasks)

    # Assert
    assert bullets == "- #102 Newer active\n- #98 In progress"


# TC-024: Every portable Azure CLI request carries configured organization/project/team context.
# Steps:
#   1. Configure two project/team pairs and inject a fake Azure CLI runner.
#   2. Gather each pair's current iteration and work items.
#   3. Verify argv arrays, explicit context, and no shell executable or shell string.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-1, AC-8, AC-12.
def test_tc_024_uses_argv_arrays_with_explicit_organization_project_and_team_for_each_pair():
    # Arrange
    client = _portable_client()
    received = []
    expected_team = {"Project One": "Team One", "Project Two": "Team Two"}

    def observe(argv):
        assert argv[0] == "az"
        assert "powershell" not in " ".join(argv).lower()
        received.append(argv)

    runner = _fake_ado(lambda project: [_item(100, f"{project} active", "Active")], on_call=observe)

    # Act
    result = client.gather_current_tasks(_portable_config(), runner=runner)

    # Assert
    assert [task["id"] for task in result["tasks"]] == [100, 100]
    # Three calls per project: team iteration list, WIQL ids, batch hydrate.
    assert len(received) == 6
    iterations = [argv for argv in received if _is_iteration(argv)]
    assert len(iterations) == 2
    for argv in iterations:
        project = argv[argv.index("--project") + 1]
        assert argv[argv.index("--team") + 1] == expected_team[project]
        # An unfiltered list returns every iteration ever defined, oldest first.
        assert argv[argv.index("--timeframe") + 1] == "current"
    for argv in received:
        assert "--org" in argv
        assert argv[argv.index("--org") + 1] == "https://dev.azure.com/example-org"
        assert not any(argument == "-Command" for argument in argv)
    # `az boards query` rejects --team, so it must never be sent on a query.
    for argv in (argv for argv in received if not _is_iteration(argv)):
        assert "--team" not in argv
        assert _route_project(argv) in expected_team


# TC-024b: A team entry may override the root organization so projects in different
# Azure DevOps organizations are gathered in one run.
# Steps:
#   1. Configure two projects whose team entries name different organizations.
#   2. Gather both pairs through the injected runner.
#   3. Verify each project's calls carry its own organization and both results survive.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8.
def test_tc_024b_team_entry_organization_overrides_root_for_cross_organization_projects():
    # Arrange
    client = _portable_client()
    config = _portable_config()
    config["ado"]["organization"] = "https://dev.azure.com/root-org"
    config["ado"]["teams"] = [
        {"project": "Project One", "team": "Team One"},  # inherits the root organization
        {"project": "Project Two", "team": "Team Two",
         "organization": "https://dev.azure.com/other-org"},
    ]
    seen = []

    runner = _fake_ado(
        lambda project: [_item(7 if project == "Project One" else 9, f"{project} work", "Active")],
        on_call=lambda argv: seen.append(
            (argv[argv.index("--project") + 1] if _is_iteration(argv) else _route_project(argv),
             argv[argv.index("--org") + 1])
        ),
    )

    # Act
    result = client.gather_current_tasks(config, runner=runner)

    # Assert
    assert sorted(task["id"] for task in result["tasks"]) == [7, 9]
    assert result["failures"] == []
    organizations = dict(seen)
    assert organizations["Project One"] == "https://dev.azure.com/root-org"
    assert organizations["Project Two"] == "https://dev.azure.com/other-org"
    # Every call for a project must use that project's organization, not a mix.
    assert {org for project, org in seen if project == "Project Two"} == {"https://dev.azure.com/other-org"}


# TC-025: The WIQL query uses configured identity, or @Me when identity is empty.
# Steps:
#   1. Gather once with a configured identity and once with an empty identity.
#   2. Capture the injected runner's Azure CLI query arguments.
#   3. Verify the query targets the configured identity or Azure DevOps @Me.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
@pytest.mark.parametrize("identity, expected_identity", [("dev@example.test", "dev@example.test"), ("", "@Me")])
def test_tc_025_queries_configured_identity_or_current_user(identity, expected_identity):
    # Arrange
    client = _portable_client()
    queries = []
    config = _portable_config(identity)
    config["ado"]["projects"] = ["Project One"]
    config["ado"]["teams"] = [{"project": "Project One", "team": "Team One"}]

    def observe(argv):
        if _resource(argv) == "wiql":
            queries.append(_request_body(argv))

    # Act
    client.gather_current_tasks(config, runner=_fake_ado(lambda project: [], on_call=observe))

    # Assert
    wiql = queries[0]["query"]
    assert f"'{expected_identity}'" in wiql
    assert "System.AssignedTo" in wiql


# TC-026: Portable gathering filters active Task items, keeps Unicode, and sorts IDs newest first.
# Steps:
#   1. Supply active, inactive, and non-Task Azure DevOps work items through the fake runner.
#   2. Gather the configured project/team.
#   3. Verify active Task records retain Unicode and are newest-first; all others are SKIPPED.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
def test_tc_026_filters_active_task_items_preserves_unicode_and_sorts_newest_first():
    # Arrange
    client = _portable_client()
    config = _portable_config()
    config["ado"]["projects"] = ["Project One"]
    config["ado"]["teams"] = [{"project": "Project One", "team": "Team One"}]

    runner = _fake_ado(lambda project: _work_items(
        _item(41, "Đồng bộ báo cáo", "Active"),
        _item(88, "Newest task", "In Progress"),
        _item(75, "Closed task", "Closed"),
        _item(66, "Story, not a task", "Active", "User Story"),
    ))

    # Act
    result = client.gather_current_tasks(config, runner=runner)

    # Assert
    assert [(task["id"], task["title"]) for task in result["tasks"]] == [
        (88, "Newest task"),
        (41, "Đồng bộ báo cáo"),
    ]
    assert [(task["id"], task["state"]) for task in result["skipped"]] == [
        (75, "Closed"),
        (66, "Active"),
    ]


# TC-027: Empty active work has stable ACTIVE, SKIPPED, and TASKS_JSON sections.
# Steps:
#   1. Provide no active Task records and one inactive record.
#   2. Gather through the portable boundary and render the report.
#   3. Verify the exact human-readable sections and structured JSON payload.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
def test_tc_027_renders_empty_active_and_skipped_sections_with_exact_tasks_json():
    # Arrange
    renderer = getattr(gather_tasks, "format_gather_output", None)
    assert callable(renderer), "Task 10 must expose format_gather_output(result) for stable report output."
    result = {
        "tasks": [],
        "skipped": [{"id": 7, "title": "Finished", "state": "Closed", "project": "Project One", "type": "Task"}],
        "failures": [],
    }

    # Act
    output = renderer(result)

    # Assert
    expected_json = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    assert output == (
        "=== ACTIVE TASKS (in-progress) ===\n"
        "(none found in active states)\n\n"
        "=== SKIPPED (other states: Closed) ===\n"
        "- #7 Finished  [Closed]\n\n"
        "=== TASKS_JSON ===\n"
        f"{expected_json}\n"
    )


# TC-028: One project/team failure does not discard successfully gathered tasks.
# Steps:
#   1. Make one injected current-iteration Azure CLI request fail and the other succeed.
#   2. Gather both configured project/team pairs.
#   3. Verify success remains available and failure contains actionable project/team context.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-8 and AC-12.
def test_tc_028_returns_partial_results_and_structured_project_team_failure():
    # Arrange
    client = _portable_client()

    healthy = _fake_ado(lambda project: _work_items(_item(15, "Available", "Active")))

    def runner(argv):
        project = argv[argv.index("--project") + 1] if _is_iteration(argv) else _route_project(argv)
        if project == "Project Two":
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="Team not found")
        return healthy(argv)

    # Act
    result = client.gather_current_tasks(_portable_config(), runner=runner)

    # Assert
    assert result["tasks"] == [{"id": 15, "title": "Available", "state": "Active", "project": "Project One", "type": "Task"}]
    assert result["failures"] == [{
        "code": "ADO_QUERY_FAILED",
        "project": "Project Two",
        "team": "Team Two",
        "message": "Team not found",
    }]


# TC-029: Malformed Azure CLI JSON becomes a structured failure without a decoding fallback.
# Steps:
#   1. Return malformed UTF-8 JSON text from the fake Azure CLI iteration request.
#   2. Gather the configured project/team.
#   3. Verify a MALFORMED_JSON failure names the affected project/team and no task is invented.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-1, AC-8, AC-12.
def test_tc_029_reports_malformed_json_without_windows_codepage_fallback():
    # Arrange
    client = _portable_client()
    config = _portable_config()
    config["ado"]["projects"] = ["Project One"]
    config["ado"]["teams"] = [{"project": "Project One", "team": "Team One"}]

    def runner(argv):
        return subprocess.CompletedProcess(argv, 0, stdout="{not-json", stderr="")

    # Act
    result = client.gather_current_tasks(config, runner=runner)

    # Assert
    assert result["tasks"] == []
    assert result["skipped"] == []
    assert result["failures"][0]["code"] == "MALFORMED_JSON"
    assert result["failures"][0]["project"] == "Project One"
    assert result["failures"][0]["team"] == "Team One"


# TC-030: The portable implementation has no PowerShell or legacy-script dependency.
# Steps:
#   1. Parse the portable gatherer source as Python AST.
#   2. Inspect imports and the public gather function's names/constants.
#   3. Verify process/filesystem execution stays out of the renderer and legacy compatibility keys are absent.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-1, AC-8, AC-12.
def test_tc_030_gatherer_ast_has_no_process_filesystem_or_legacy_compatibility_boundary():
    # Arrange
    gatherer_path = Path(gather_tasks.__file__)

    # Act
    tree = ast.parse(gatherer_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    gather_function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "gather"
    )
    gather_names = {node.id for node in ast.walk(gather_function) if isinstance(node, ast.Name)}
    gather_literals = {node.value.lower() for node in ast.walk(gather_function)
                       if isinstance(node, ast.Constant) and isinstance(node.value, str)}

    # Assert
    assert not ({"os", "tempfile", "subprocess"} & imported_modules)
    assert not ({"os", "tempfile", "subprocess"} & gather_names)
    assert not ({"sprint_script", "member_email"} & gather_literals)


# TC-031: Legacy-only configuration fails closed through a domain validation error before any process boundary is called.
# Steps:
#   1. Supply a legacy-only ADO config and install sentinels for direct and injected runners.
#   2. Attempt to gather tasks.
#   3. Verify an actionable ValueError-style portable-config error, not SystemExit, and zero calls to either process boundary.
# Design: portable-git-daily-report-dev-workflow.md Task 10, AC-1, AC-8, AC-12.
def test_tc_031_rejects_legacy_only_config_without_any_external_call(monkeypatch):
    # Arrange
    injected_calls = []
    direct_calls = []

    def injected_runner(argv):
        injected_calls.append(argv)
        raise AssertionError("legacy configuration must fail before injected runner use")

    def direct_runner(*args, **kwargs):
        direct_calls.append((args, kwargs))
        raise AssertionError("legacy configuration must not use a direct process boundary")

    # The sentinel prevents a retained legacy branch from executing an external process during this RED test.
    monkeypatch.setattr(gather_tasks, "subprocess", types.SimpleNamespace(run=direct_runner), raising=False)

    # Act / Assert
    error_type = getattr(gather_tasks, "PortableConfigurationError", None)
    assert isinstance(error_type, type), "Task 10 must expose PortableConfigurationError for invalid portable ADO config."
    assert issubclass(error_type, ValueError)
    assert not issubclass(error_type, SystemExit), "Domain configuration errors must not inherit SystemExit."
    with pytest.raises(error_type, match="portable.*organization|organization.*portable"):
        gather_tasks.gather(_legacy_config(), runner=injected_runner)
    assert injected_calls == []
    assert direct_calls == []
