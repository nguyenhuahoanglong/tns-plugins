"""Cross-platform encrypted Dataverse authentication contracts.

Test cases: .plans/portable-git-daily-report-dev-workflow.daily.test-cases.md
Design: .plans/portable-git-daily-report-dev-workflow.md (Task 8; AC-5, AC-7,
AC-12, AC-13).

TC-011, TC-012, and TC-078 specify the integration from legacy callers to the
portable ``auth_cache`` boundary. TC-013 onward cover the encrypted cache
itself. No test uses real MSAL, OAuth, a browser, the network, or an OS key
store.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import lib_common  # noqa: E402
import write_timesheet  # noqa: E402


def _auth_module():
    """Return the Task 8 module without turning its absence into collection error."""
    try:
        return importlib.import_module("auth_cache")
    except ModuleNotFoundError as error:
        if error.name == "auth_cache":
            return None
        raise


def _task_8_auth():
    module = _auth_module()
    assert module is not None, "Task 8 must provide importable auth_cache.py."
    return module


def _config():
    return {
        "timesheet": {
            "tenant_id": "resource-tenant-id",
            "client_id": "public-client-id",
            "org_url": "https://resource.crm.dynamics.com",
            "auth_cache": "unused.bin",
        }
    }


# TC-011: The legacy public helper delegates to portable encrypted authentication.
# Steps:
#   1. Configure a deliberately personal legacy cache path and an isolated portable state path.
#   2. Inject the portable auth-cache boundary with a deterministic token.
#   3. Verify configured resource settings, explicit interactive mode, and portable cache path are delegated.
# Design: portable-git-daily-report-dev-workflow.md Task 8, AC-7 and AC-12.
def test_tc_011_delegates_to_portable_auth_cache_with_resource_settings_and_state_cache(monkeypatch, tmp_path):
    calls = []
    config = _config()
    config["timesheet"]["auth_cache"] = r"C:\\Users\\example\\auth-cache.bin"
    portable_cache = tmp_path / "portable" / "auth-cache.bin"
    auth = _task_8_auth()
    monkeypatch.setattr(lib_common, "resolve_state_paths", lambda: {"auth_cache_path": portable_cache})
    monkeypatch.setattr(
        auth,
        "acquire_access_token",
        lambda received_config, *, cache_path, interactive: calls.append(
            (received_config, cache_path, interactive)
        ) or "portable-access-token",
    )
    monkeypatch.setattr(
        lib_common, "_load_refresh_token", lambda *_args: pytest.fail("legacy cache must not load"), raising=False
    )

    token = lib_common.get_access_token(config, interactive=False)

    assert token == "portable-access-token"
    assert calls == [(config, portable_cache, False)]


# TC-012: Non-interactive execution propagates the portable typed sign-in failure.
# Steps:
#   1. Inject a portable auth-cache boundary that requires interactive sign-in.
#   2. Attempt token acquisition with interactive sign-in disabled.
#   3. Verify the typed actionable failure propagates before any legacy auth operation.
# Design: portable-git-daily-report-dev-workflow.md Task 8, AC-12 and AC-13.
def test_tc_012_propagates_portable_authentication_required_before_legacy_device_flow(monkeypatch, tmp_path):
    auth = _task_8_auth()
    portable_cache = tmp_path / "portable" / "auth-cache.bin"
    monkeypatch.setattr(lib_common, "resolve_state_paths", lambda: {"auth_cache_path": portable_cache})
    monkeypatch.setattr(
        auth,
        "acquire_access_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            auth.AuthenticationRequired("Dataverse sign-in is required; rerun with interactive sign-in enabled.")
        ),
    )
    monkeypatch.setattr(
        lib_common, "_load_refresh_token", lambda *_args: pytest.fail("legacy cache must not load"), raising=False
    )

    with pytest.raises(auth.AuthenticationRequired, match="sign-in is required"):
        lib_common.get_access_token(_config(), interactive=False)


def test_tc_078_removes_windows_auth_internals_and_uses_portable_default_from_timesheet_writer(monkeypatch, tmp_path):
    """TC-078: Legacy callers use only portable encrypted authentication.

    Steps:
      1. Inspect the legacy helper source for obsolete Windows cache and OAuth helpers.
      2. Inject the portable auth-cache module and isolated portable cache location.
      3. Resolve the timesheet identity through its default token provider.
      4. Verify the default reaches the portable boundary, not a bound legacy implementation.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-5, AC-7, AC-12, AC-13.
    """
    source = Path(lib_common.__file__).read_text(encoding="utf-8")
    forbidden_legacy_symbols = (
        "win32crypt",
        "_dpapi_protect",
        "_dpapi_unprotect",
        "_save_refresh_token",
        "_load_refresh_token",
        "_token_endpoint",
        "_post_form",
        "_device_code_flow",
    )
    assert not [symbol for symbol in forbidden_legacy_symbols if symbol in source]

    auth = _task_8_auth()
    portable_cache = tmp_path / "portable" / "auth-cache.bin"
    calls = []
    monkeypatch.setattr(lib_common, "resolve_state_paths", lambda: {"auth_cache_path": portable_cache})
    monkeypatch.setattr(
        auth,
        "acquire_access_token",
        lambda received_config, *, cache_path, interactive: calls.append(
            (received_config, cache_path, interactive)
        ) or "portable-access-token",
    )

    assert write_timesheet.resolve_timesheet_identity.__defaults__[0] is lib_common.get_access_token
    identity = write_timesheet.resolve_timesheet_identity(_config(), whoami=lambda _config, _token: "user-id")

    assert identity == {"tenant": "resource-tenant-id", "user_id": "user-id"}
    assert calls == [(_config(), portable_cache, True)]


def test_tc_013_builds_encrypted_persistence_without_plaintext_fallback(tmp_path):
    """TC-013: Build encrypted persistence through the MSAL Extensions boundary.

    Steps:
      1. Inject a fake ``build_encrypted_persistence`` boundary.
      2. Build persistence for an isolated cache path.
      3. Verify plaintext fallback is explicitly refused; no OS key store is contacted.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-5 and AC-13.
    """
    calls = []
    auth = _task_8_auth()

    cache_path = tmp_path / "auth-cache.bin"
    result = auth.create_encrypted_persistence(
        cache_path,
        encrypted_persistence_builder=lambda location, *, fallback_to_plaintext: (
            calls.append((Path(location), fallback_to_plaintext)) or object()
        ),
    )

    assert result is not None
    assert calls == [(cache_path, False)]


def test_tc_014_fails_closed_when_encrypted_persistence_is_unavailable_without_plaintext_or_token_leakage(tmp_path):
    """TC-014: Fail closed if secure persistence cannot be initialized.

    Steps:
      1. Inject a persistence factory that reports secure storage unavailable.
      2. Request a token using a distinctive secret-like value in mocked dependencies.
      3. Verify an actionable secure-storage error, no plaintext cache, and no token in status output.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-5, AC-12, AC-13.
    """
    auth = _task_8_auth()
    cache_path = tmp_path / "auth-cache.bin"
    emitted = []

    with pytest.raises(auth.SecureStorageUnavailable, match="secure.*storage"):
        auth.acquire_access_token(
            _config(), cache_path=cache_path, interactive=False,
            encrypted_persistence_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("libsecret unavailable")),
            persisted_token_cache_factory=lambda *_args: pytest.fail("cache wrapper must not be created"),
            public_client_factory=lambda *_args, **_kwargs: pytest.fail("MSAL must not be created"),
            status=emitted.append,
        )

    assert not cache_path.exists()
    assert "access-secret" not in "\n".join(emitted)
    assert "refresh-secret" not in "\n".join(emitted)


def test_tc_015_rejects_corrupt_encrypted_cache_without_device_fallback_or_secret_output(tmp_path):
    """TC-015: Treat corrupt encrypted cache data as a security failure.

    Steps:
      1. Provide a fake encrypted persistence boundary that cannot load its cache.
      2. Request a non-interactive token.
      3. Verify corruption is reported, device login is not started, and details are redacted.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-12 and AC-13.
    """
    auth = _task_8_auth()
    emitted = []
    app_calls = []
    with pytest.raises(auth.TokenCacheCorrupt, match="cache"):
        auth.acquire_access_token(
            _config(), cache_path=tmp_path / "auth-cache.bin", interactive=False,
            encrypted_persistence_builder=lambda *_args, **_kwargs: object(),
            persisted_token_cache_factory=lambda *_args: (_ for _ in ()).throw(ValueError("blob refresh-secret corrupt")),
            public_client_factory=lambda *_args, **_kwargs: app_calls.append(True),
            status=emitted.append,
        )

    assert app_calls == []
    assert "refresh-secret" not in "\n".join(emitted)


def test_tc_016_starts_device_code_login_once_and_reports_safe_status_on_first_login(tmp_path):
    """TC-016: Acquire a first-login token through the injected MSAL device flow.

    Steps:
      1. Supply an empty encrypted cache and a fake public client application.
      2. Request an interactive token.
      3. Verify resource-tenant authority, Dataverse scope, one device flow, and safe status output.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-7, AC-12, AC-13.
    """
    auth = _task_8_auth()
    calls = []
    emitted = []
    persistence = object()
    token_cache = object()

    class FakeApp:
        def acquire_token_silent(self, scopes, account=None):
            calls.append(("silent", scopes, account))
            return None

        def initiate_device_flow(self, scopes):
            calls.append(("initiate", scopes))
            return {"user_code": "SAFE-CODE", "message": "Use SAFE-CODE to sign in"}

        def acquire_token_by_device_flow(self, flow):
            calls.append(("complete", flow))
            return {"access_token": "access-secret"}

    def app_factory(client_id, authority, token_cache_argument):
        calls.append(("factory", client_id, authority, token_cache_argument))
        return FakeApp()

    token = auth.acquire_access_token(
        _config(), cache_path=tmp_path / "auth-cache.bin", interactive=True,
        encrypted_persistence_builder=lambda *_args, **_kwargs: persistence,
        persisted_token_cache_factory=lambda received: (calls.append(("cache", received)) or token_cache),
        public_client_factory=app_factory, status=emitted.append,
    )

    assert token == "access-secret"
    assert ("cache", persistence) in calls
    assert ("factory", "public-client-id", "https://login.microsoftonline.com/resource-tenant-id", token_cache) in calls
    assert ("initiate", ["https://resource.crm.dynamics.com/.default"]) in calls
    assert any("AUTH_REQUIRED" in message for message in emitted)
    assert "access-secret" not in "\n".join(emitted)


def test_tc_017_uses_silent_token_then_persists_rotated_cache_without_interactive_prompt(tmp_path):
    """TC-017: Prefer a silent token and persist its rotated encrypted cache.

    Steps:
      1. Provide an existing encrypted cache and a client that returns a silent token.
      2. Request a non-interactive token.
      3. Verify no device flow occurs and the cache persistence boundary saves the updated state once.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-7 and AC-12.
    """
    auth = _task_8_auth()
    calls = []
    persistence = object()
    token_cache = object()

    class FakeApp:
        def acquire_token_silent(self, scopes, account=None):
            calls.append(("silent", scopes, account))
            return {"access_token": "rotated-access"}

        def initiate_device_flow(self, _scopes):
            pytest.fail("silent success must not start device code")

    token = auth.acquire_access_token(
        _config(), cache_path=tmp_path / "auth-cache.bin", interactive=False,
        encrypted_persistence_builder=lambda *_args, **_kwargs: persistence,
        persisted_token_cache_factory=lambda received: (calls.append(("cache", received)) or token_cache),
        public_client_factory=lambda *_args, **_kwargs: FakeApp(), status=lambda _message: None,
    )

    assert token == "rotated-access"
    assert calls == [("cache", persistence), ("silent", ["https://resource.crm.dynamics.com/.default"], None)]


def test_tc_018_rejects_wrong_resource_tenant_and_never_requests_a_token(tmp_path):
    """TC-018: Reject a token result associated with a tenant other than the resource tenant.

    Steps:
      1. Configure the resource tenant and simulate a silent token for another tenant.
      2. Request a non-interactive token.
      3. Verify a tenant-boundary error and no interactive fallback.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-7, AC-12, AC-13.
    """
    auth = _task_8_auth()
    app = SimpleNamespace(
        acquire_token_silent=lambda *_args, **_kwargs: {
            "access_token": "wrong-tenant", "id_token_claims": {"tid": "home-tenant"},
        },
        initiate_device_flow=lambda *_args, **_kwargs: pytest.fail("wrong tenant must not fall back interactively"),
    )

    with pytest.raises(auth.ResourceTenantMismatch, match="resource.*tenant"):
        auth.acquire_access_token(
            _config(), cache_path=tmp_path / "auth-cache.bin", interactive=False,
            encrypted_persistence_builder=lambda *_args, **_kwargs: object(),
            persisted_token_cache_factory=lambda *_args: object(),
            public_client_factory=lambda *_args, **_kwargs: app, status=lambda _message: None,
        )
def test_tc_021_wraps_encrypted_persistence_once_and_passes_wrapper_to_public_client(tmp_path):
    """TC-021: Delegate cache reload and locking to ``PersistedTokenCache``.

    Steps:
      1. Inject encrypted persistence and a persisted-token-cache factory.
      2. Acquire a silent token.
      3. Verify the wrapper is built once and passed to the public client without manual persistence locking.
    Design: portable-git-daily-report-dev-workflow.md Task 8, AC-12 and AC-13.
    """
    auth = _task_8_auth()
    persistence = object()
    token_cache = object()
    cache_calls = []
    app_calls = []
    app = SimpleNamespace(acquire_token_silent=lambda *_args, **_kwargs: {"access_token": "access"})

    assert auth.acquire_access_token(
        _config(), cache_path=tmp_path / "auth-cache.bin", interactive=False,
        encrypted_persistence_builder=lambda *_args, **_kwargs: persistence,
        persisted_token_cache_factory=lambda received: (cache_calls.append(received) or token_cache),
        public_client_factory=lambda client_id, authority, received: (app_calls.append((client_id, authority, received)) or app),
        status=lambda _message: None,
    ) == "access"
    assert cache_calls == [persistence]
    assert app_calls == [("public-client-id", "https://login.microsoftonline.com/resource-tenant-id", token_cache)]


# TC-106: Device flow exposes MSAL's usable verification message but never OAuth tokens in status.
# Steps: 1. Inject an offline MSAL client/device flow. 2. Acquire interactively. 3. Inspect status messages only.
# Design: portable-git-daily-report-dev-workflow.md Task 8, AC-7, AC-12, AC-13.
def test_tc_106_device_flow_emits_msal_verification_message_without_token_leakage(tmp_path):
    auth = _task_8_auth()
    messages = []
    flow_message = "To sign in, use https://microsoft.com/devicelogin and code ABCD-EFGH."
    app = SimpleNamespace(
        acquire_token_silent=lambda *_args, **_kwargs: None,
        initiate_device_flow=lambda **_kwargs: {"message": flow_message, "user_code": "ABCD-EFGH"},
        acquire_token_by_device_flow=lambda _flow: {"access_token": "access-token-secret", "refresh_token": "refresh-token-secret"},
    )
    assert auth.acquire_access_token(
        _config(), cache_path=tmp_path / "auth-cache.bin", interactive=True,
        encrypted_persistence_builder=lambda *_args, **_kwargs: object(),
        persisted_token_cache_factory=lambda *_args: object(),
        public_client_factory=lambda *_args, **_kwargs: app,
        status=messages.append,
    ) == "access-token-secret"
    rendered = "\n".join(messages)
    assert flow_message in rendered
    assert "access-token-secret" not in rendered
    assert "refresh-token-secret" not in rendered
