# Timesheet authentication

Authentication uses `msal` with `msal-extensions`. The configured organization
URL, resource tenant, and client ID define the resource. Use the tenant that
owns the Dataverse organization, including when your account is a guest there.

## Cache security

The cache lives at the portable state root as `auth-cache.bin`. Persistence uses
the platform secure store:

- Windows: DPAPI
- macOS: Keychain
- Linux: LibSecret

The implementation calls `build_encrypted_persistence` with
`fallback_to_plaintext=False`. It never writes a plaintext fallback. If Linux
has no usable secure-store backend, authentication fails closed. Install and
unlock a supported Secret Service backend, then rerun setup or the report; do
not copy another user's cache or create a plaintext token file.

## Token flow

1. Attempt silent acquisition from the encrypted cache.
2. If silent acquisition cannot proceed and interaction is allowed, start one
   MSAL device-code flow against the resource tenant.
3. Display MSAL's verification URL and code message, complete it in a browser,
   then persist only encrypted cache state.
4. Call Dataverse `WhoAmI` with the resulting token to confirm resource access
   and obtain the current user ID.

`write_timesheet.py --check-auth` uses non-interactive acquisition. It returns
an actionable authentication-required status instead of opening device login.
The daily workflow preflights this before any committed timesheet write.

Never log, print, commit, or paste access tokens, refresh tokens, cache bytes,
or client secrets. Error paths redact bearer material. A corrupt cache is a
stop condition: remove only the affected local cache after confirming its path,
then sign in again through the normal device-code flow.
