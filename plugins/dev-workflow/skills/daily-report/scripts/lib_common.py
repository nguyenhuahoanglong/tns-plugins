"""Shared helpers for portable daily-report state, configuration, and Web API access.

Authentication is delegated at runtime to the encrypted cross-platform token-cache
boundary. This module retains a compatibility token-provider function for existing
daily-report callers without handling token persistence itself.
"""
import json, os as _stdlib_os, platform, urllib.request
from pathlib import Path


class _OsFacade:
    """Allow platform behavior to be simulated without mutating process-global os."""

    def __init__(self, module):
        self._module = module

    def __getattr__(self, name):
        return getattr(self._module, name)


os = _OsFacade(_stdlib_os)

_STATE_SUFFIX = ("rd-team", "dev-workflow", "daily-report")


def _environment(env=None):
    """Return the process environment, or the injected test environment."""
    return os.environ if env is None else env


def _home_path(home=None):
    return Path.home() if home is None else Path(home)


def resolve_state_paths(home=None, platform_name=None, env=None, create=False):
    """Resolve mutable daily-report state without depending on the caller cwd."""
    values = _environment(env)
    platform_name = platform_name or platform.system()
    user_home = _home_path(home)
    override = values.get("DAILY_REPORT_HOME")

    if override:
        state_dir = Path(override).expanduser()
    elif platform_name in ("Windows", "win32"):
        local_app_data = values.get("LOCALAPPDATA")
        base = Path(local_app_data).expanduser() if local_app_data else user_home / "AppData" / "Local"
        state_dir = base.joinpath(*_STATE_SUFFIX)
    elif platform_name in ("Darwin", "macOS"):
        state_dir = user_home / "Library" / "Application Support" / Path(*_STATE_SUFFIX)
    else:
        xdg_data_home = values.get("XDG_DATA_HOME")
        base = Path(xdg_data_home).expanduser() if xdg_data_home else user_home / ".local" / "share"
        state_dir = base.joinpath(*_STATE_SUFFIX)

    paths = {
        "state_dir": state_dir,
        "config_path": state_dir / "daily-report.config.json",
        "queue_path": state_dir / "pending-timesheets.json",
        "auth_cache_path": state_dir / "auth-cache.bin",
    }
    if create:
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def resolve_config_path(path=None, env=None):
    """Resolve config with explicit argument, environment, then state-root precedence."""
    values = _environment(env)
    if path is not None:
        return Path(path).expanduser()
    if values.get("DAILY_REPORT_CONFIG"):
        return Path(values["DAILY_REPORT_CONFIG"]).expanduser()
    return resolve_state_paths(env=values)["config_path"]


def _tighten_permissions(path):
    if os.name == "posix":
        os.chmod(path, 0o600)


def save_json_atomic(path, payload):
    """Durably replace a JSON document while preserving its prior valid version on failure."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _tighten_permissions(temporary)
        os.replace(temporary, target)
        _tighten_permissions(target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def load_config(path=None):
    config_path = resolve_config_path(path)
    if not config_path.is_file():
        raise SystemExit(f"ERROR: config not found at {config_path}. Copy assets/config-template.json and fill it in, "
                         "or set DAILY_REPORT_CONFIG.")
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as error:
        raise SystemExit(f"ERROR: config is not valid JSON at {config_path}: {error.msg}.")


def get_access_token(cfg, interactive=True):
    """Return a Dataverse token through the portable encrypted-cache boundary."""
    from auth_cache import acquire_access_token

    cache_path = resolve_state_paths()["auth_cache_path"]
    return acquire_access_token(cfg, cache_path=cache_path, interactive=interactive)


def who_am_i(config, token, http_get=None):
    """Return the authenticated Dataverse user id without exposing bearer material."""
    org = config["timesheet"]["org_url"].rstrip("/")
    url = org + "/api/data/v9.2/WhoAmI"
    headers = {"Authorization": "Bearer " + token}
    try:
        if http_get is not None:
            response = http_get(url, headers)
        else:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request) as response_handle:
                response = json.load(response_handle)
        if isinstance(response, dict) and response.get("UserId"):
            return response["UserId"]
        raise RuntimeError("WhoAmI returned no UserId; confirm the Dataverse account has user access.")
    except Exception as error:
        message = str(error).replace(token, "[REDACTED]")
        if "401" in message or "403" in message or "unauthorized" in message.lower() or "forbidden" in message.lower():
            raise RuntimeError("WhoAmI authorization failed (401/403). Sign in again and confirm Dataverse user permissions: " + message) from None
        raise RuntimeError("WhoAmI request failed: " + message) from None


# ---------- Dataverse Web API ----------
class Dataverse:
    def __init__(self, cfg, token):
        self.org = cfg["timesheet"]["org_url"].rstrip("/")
        self.token = token
        self.base = self.org + "/api/data/v9.2/"

    def _req(self, method, path, body=None, prefer=None):
        url = self.base + path.replace(" ", "%20")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Accept", "application/json")
        req.add_header("OData-MaxVersion", "4.0")
        req.add_header("OData-Version", "4.0")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if prefer:
            req.add_header("Prefer", prefer)
        try:
            resp = urllib.request.urlopen(req)
            raw = resp.read().decode("utf-8")
            entity_id = None
            loc = resp.headers.get("OData-EntityId") or resp.headers.get("Location")
            if loc and "(" in loc:
                entity_id = loc.rsplit("(", 1)[1].rstrip(")")
            return {"status": resp.status, "json": json.loads(raw) if raw else None, "entity_id": entity_id}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8")[:600]
            raise RuntimeError(f"Dataverse {method} {path} -> HTTP {e.code}: {detail}")

    def get(self, path, prefer=None):
        return self._req("GET", path, prefer=prefer)

    def create(self, entity_set, body):
        return self._req("POST", entity_set, body=body, prefer="return=representation")

    def update(self, entity_set, guid, body):
        return self._req("PATCH", f"{entity_set}({guid})", body=body)

    def delete(self, entity_set, guid):
        return self._req("DELETE", f"{entity_set}({guid})")
