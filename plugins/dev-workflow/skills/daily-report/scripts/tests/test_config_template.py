"""Contract checks for the portable daily-report bootstrap config template."""
import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = SKILL_ROOT / "assets"
TEMPLATE_PATH = ASSETS_DIR / "config-template.json"
LEGACY_TEMPLATE_PATH = ASSETS_DIR / "config.template.json"
GUID_PATTERN = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)


def _walk_values(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_values(nested)
    else:
        yield value


def _walk_items(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key, nested
            yield from _walk_items(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_items(nested)


def test_tc_099_template_has_portable_identity_and_lookup_schema_contract():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    assert set(template) == {"excel", "ado", "timesheet"}
    assert set(template["excel"]) == {"path", "sheet"}
    assert set(template["ado"]) == {
        "organization", "projects", "teams", "member_identity", "active_states"
    }
    assert set(template["timesheet"]) == {
        "org_url", "tenant_id", "client_id", "header_entity_set",
        "detail_entity_set", "defaults"
    }
    assert set(template["timesheet"]["defaults"]) == {
        "task_days", "description_style", "location_option", "location_label",
        "travel_by_option", "from_hour_local", "to_hour_local", "timezone_offset_hours",
        "bindings"
    }

    bindings = template["timesheet"]["defaults"]["bindings"]
    assert set(bindings) == {"cr90e_ProjectCodeCD", "cr90e_ClientCD", "cr90e_JobTypeCD", "cr90e_StageCD", "xts_ProjectStage"}
    assert all(set(binding) == {"set", "code", "code_field", "id_field"} for binding in bindings.values())
    assert all(isinstance(binding[field], str) for binding in bindings.values() for field in ("set", "code", "code_field", "id_field"))


def test_bootstrap_template_requires_setup_time_identity_and_location_values():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    assert template["excel"]["path"] == ""
    assert template["ado"]["organization"] == ""
    assert template["ado"]["projects"] == []
    assert template["ado"]["teams"] == []
    assert template["ado"]["member_identity"] == ""
    assert template["timesheet"]["org_url"] == ""
    assert template["timesheet"]["tenant_id"] == ""
    assert template["timesheet"]["client_id"] == ""


def test_bootstrap_template_has_no_personal_markers_or_resolved_lookup_ids():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    rendered = TEMPLATE_PATH.read_text(encoding="utf-8")
    forbidden_markers = (
        "C:\\Users\\LN",
        "technosoftautomotive.com",
        "long.nguyen",
        "auth_cache",
        ".encrypted",
    )

    assert not GUID_PATTERN.search(rendered)
    assert not any(marker.lower() in rendered.lower() for marker in forbidden_markers)
    assert not any("email" in key.lower() for key, _ in _walk_items(template))
    assert not any(
        key == "id" for key, _ in _walk_items(template["timesheet"]["defaults"]["bindings"])
    )
    assert not any(
        isinstance(value, str) and ("/" in value or "\\" in value)
        for value in _walk_values(template)
    )


def test_template_uses_kebab_case_name_and_legacy_name_is_absent():
    assert TEMPLATE_PATH.name == "config-template.json"
    assert not LEGACY_TEMPLATE_PATH.exists()
