"""Encrypted MSAL token-cache support for the portable daily-report skill.

The MSAL Extensions cache owns persistence, reload, and cross-process locking.
This module intentionally never reads, writes, or locks the cache itself.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping


class SecureStorageUnavailable(RuntimeError):
    """Raised when the platform cannot provide encrypted token persistence."""


class TokenCacheCorrupt(RuntimeError):
    """Raised when the encrypted token cache cannot be opened safely."""


class ResourceTenantMismatch(RuntimeError):
    """Raised when an acquired token belongs to a tenant other than the resource."""


class AuthenticationRequired(RuntimeError):
    """Raised when interactive device sign-in is required but not permitted."""


def _encrypted_persistence_builder(location: Path) -> Any:
    """Import MSAL Extensions only when runtime authentication is requested.

    requirements.txt admits msal-extensions >=1.2,<2, and the builder signature changed
    inside that range: 1.2 accepts ``fallback_to_plaintext``, while 1.3 removed it. The
    no-plaintext guarantee survives either way — 1.3+ has no plaintext branch at all and
    raises on an unsupported platform, returning DPAPI on Windows, Keychain on macOS, and
    LibSecret on Linux.
    """
    try:
        from msal_extensions import build_encrypted_persistence
    except ImportError:
        raise SecureStorageUnavailable(
            "Encrypted secure storage is unavailable; install the daily-report runtime dependencies."
        ) from None
    try:
        return build_encrypted_persistence(str(location), fallback_to_plaintext=False)
    except TypeError:
        return build_encrypted_persistence(str(location))


def _persisted_token_cache_factory(persistence: Any) -> Any:
    """Construct the single process-safe MSAL Extensions cache wrapper."""
    try:
        from msal_extensions import PersistedTokenCache
    except ImportError:
        raise SecureStorageUnavailable(
            "Encrypted secure storage is unavailable; install the daily-report runtime dependencies."
        ) from None
    return PersistedTokenCache(persistence)


def _public_client_factory(client_id: str, authority: str, token_cache: Any) -> Any:
    """Create an MSAL public client without importing MSAL during module import."""
    try:
        import msal
    except ImportError:
        raise SecureStorageUnavailable(
            "Encrypted secure storage is unavailable; install the daily-report runtime dependencies."
        ) from None
    return msal.PublicClientApplication(client_id, authority=authority, token_cache=token_cache)


def create_encrypted_persistence(
    cache_path: str | Path,
    *,
    encrypted_persistence_builder: Callable[..., Any] | None = None,
) -> Any:
    """Build encrypted platform persistence and explicitly refuse plaintext fallback."""
    location = Path(cache_path)
    builder = encrypted_persistence_builder
    if builder is None:
        try:
            return _encrypted_persistence_builder(location)
        except SecureStorageUnavailable:
            raise
        except Exception as error:
            # Chain the cause: swallowing it hid a builder signature change behind a
            # generic "secure storage unavailable" for every caller.
            raise SecureStorageUnavailable(
                "Encrypted secure storage is unavailable for the Dataverse token cache."
            ) from error
    try:
        return builder(location, fallback_to_plaintext=False)
    except Exception:
        raise SecureStorageUnavailable(
            "Encrypted secure storage is unavailable for the Dataverse token cache."
        ) from None


def _resource_settings(config: Mapping[str, Any]) -> tuple[str, str, str, list[str]]:
    try:
        timesheet = config["timesheet"]
        tenant_id = str(timesheet["tenant_id"])
        client_id = str(timesheet["client_id"])
        org_url = str(timesheet["org_url"]).rstrip("/")
    except (KeyError, TypeError, ValueError):
        raise ValueError("Dataverse authentication configuration is incomplete.") from None
    if not tenant_id or not client_id or not org_url:
        raise ValueError("Dataverse authentication configuration is incomplete.")
    return tenant_id, client_id, f"https://login.microsoftonline.com/{tenant_id}", [f"{org_url}/.default"]


def _cached_account(application: Any) -> Any:
    """Use a cached account when MSAL exposes one; test doubles need no account API."""
    get_accounts = getattr(application, "get_accounts", None)
    if not callable(get_accounts):
        return None
    try:
        accounts = get_accounts()
    except Exception:
        return None
    return accounts[0] if accounts else None


def _validate_resource_tenant(result: Mapping[str, Any], resource_tenant_id: str) -> None:
    claims = result.get("id_token_claims")
    token_tenant_id = claims.get("tid") if isinstance(claims, Mapping) else None
    if token_tenant_id is not None and str(token_tenant_id) != resource_tenant_id:
        raise ResourceTenantMismatch(
            "The acquired token is not for the configured resource tenant."
        )


def _access_token(result: Any, resource_tenant_id: str) -> str | None:
    if not isinstance(result, Mapping) or not result.get("access_token"):
        return None
    _validate_resource_tenant(result, resource_tenant_id)
    return str(result["access_token"])


def acquire_access_token(
    config: Mapping[str, Any],
    *,
    cache_path: str | Path,
    interactive: bool,
    encrypted_persistence_builder: Callable[..., Any] | None = None,
    persisted_token_cache_factory: Callable[[Any], Any] | None = None,
    public_client_factory: Callable[[str, str, Any], Any] | None = None,
    status: Callable[[str], None] | None = None,
) -> str:
    """Acquire a Dataverse token silently, using device code only when allowed.

    Status messages never disclose token/cache data. MSAL's device-flow message is
    the deliberate exception: it is required for the user to finish sign-in.
    """
    emit = status or (lambda _message: None)
    tenant_id, client_id, authority, scopes = _resource_settings(config)
    persistence = create_encrypted_persistence(
        cache_path, encrypted_persistence_builder=encrypted_persistence_builder
    )
    cache_factory = persisted_token_cache_factory or _persisted_token_cache_factory
    try:
        token_cache = cache_factory(persistence)
    except SecureStorageUnavailable:
        raise
    except Exception:
        raise TokenCacheCorrupt("The encrypted Dataverse token cache could not be opened.") from None

    app_factory = public_client_factory or _public_client_factory
    try:
        application = app_factory(client_id, authority, token_cache)
    except (SecureStorageUnavailable, TokenCacheCorrupt):
        raise
    except Exception:
        raise SecureStorageUnavailable("Dataverse authentication could not initialize securely.") from None

    try:
        silent_result = application.acquire_token_silent(scopes, account=_cached_account(application))
    except Exception:
        raise TokenCacheCorrupt("The encrypted Dataverse token cache could not be read.") from None
    token = _access_token(silent_result, tenant_id)
    if token is not None:
        return token

    if not interactive:
        raise AuthenticationRequired("Dataverse sign-in is required; rerun with interactive sign-in enabled.")

    emit("AUTH_REQUIRED: Complete Dataverse device sign-in to continue.")
    try:
        flow = application.initiate_device_flow(scopes=scopes)
    except Exception:
        raise AuthenticationRequired("Dataverse device sign-in could not be started.") from None
    if not isinstance(flow, Mapping):
        raise AuthenticationRequired("Dataverse device sign-in could not be started.")
    verification_message = flow.get("message")
    if not isinstance(verification_message, str) or not verification_message.strip():
        raise AuthenticationRequired(
            "Dataverse device sign-in did not provide verification instructions."
        )
    # This is MSAL's user-facing URL/code instruction, needed before completion.
    # Do not emit any other flow fields or OAuth result/cache data.
    emit(verification_message)
    try:
        result = application.acquire_token_by_device_flow(flow)
    except Exception:
        raise AuthenticationRequired("Dataverse device sign-in did not complete.") from None
    token = _access_token(result, tenant_id)
    if token is None:
        raise AuthenticationRequired("Dataverse device sign-in did not return an access token.")
    return token
