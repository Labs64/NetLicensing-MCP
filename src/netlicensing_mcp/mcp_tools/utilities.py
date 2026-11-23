"""MCP tools for reference data (licensing models, license types, countries) and server info."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from netlicensing_mcp import __version__
from netlicensing_mcp import client as _client
from netlicensing_mcp.app import (
    _READONLY,
    _error,
    _wrap_json,
    active_tool_settings,
    active_transport,
    tool,
)
from netlicensing_mcp.client import NetLicensingError, is_demo_mode
from netlicensing_mcp.errors import error_hint
from netlicensing_mcp.tools import products, utilities

logger = logging.getLogger(__name__)


@tool(title="List licensing models", annotations=_READONLY)
async def netlicensing_list_licensing_models(include_raw: bool = False) -> str:
    """List all licensing models supported by the NetLicensing service.

    Args:
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await utilities.list_licensing_models(),
            "LicensingModel",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_licensing_models")


@tool(title="List license types", annotations=_READONLY)
async def netlicensing_list_license_types(include_raw: bool = False) -> str:
    """List all license types supported by the NetLicensing service.

    Args:
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await utilities.list_license_types(),
            "LicenseType",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_license_types")


@tool(title="List countries", annotations=_READONLY)
async def netlicensing_list_countries(
    search: str = "", eu_only: bool = False, include_raw: bool = False
) -> str:
    """List countries available for VAT and localization settings (249 without filters).

    Args:
        search: Only countries whose name or code contains this text (case-insensitive)
        eu_only: When true, only EU member states
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            _filter_countries(await utilities.list_countries(), search, eu_only),
            "Country",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_countries")


def _filter_countries(response: dict, search: str, eu_only: bool) -> dict:
    """Keep the countries matching *search* (name or code) and, if asked, only EU members."""
    items_obj = response.get("items")
    if not isinstance(items_obj, dict):
        return response
    items = items_obj.get("item")
    needle = search.strip().lower()
    if not isinstance(items, list) or not (needle or eu_only):
        return response

    def keep(item: Any) -> bool:
        props = {
            p.get("name"): str(p.get("value", ""))
            for p in (item.get("property") or [] if isinstance(item, dict) else [])
            if isinstance(p, dict)
        }
        if eu_only and props.get("isEu", "").lower() != "true":
            return False
        return (
            not needle
            or needle in props.get("name", "").lower()
            or needle in props.get("code", "").lower()
        )

    return {**response, "items": {**items_obj, "item": [i for i in items if keep(i)]}}


def _server_version() -> str:
    """Installed package version (from package metadata, not a literal).

    ``netlicensing_mcp.__version__``: also what ``initialize`` reports as
    ``serverInfo.version``; ``"unknown"`` when the package is not installed.
    """
    return __version__


# ── server_info: first-run check ─────────────────────────────────────────────

# One cheap authenticated read; well below the client's 30 s read timeout.
_CHECK_TIMEOUT_SECONDS = 10.0
_CHECK_FILTER = "page=0;items=1"
_SELF = "netlicensing_server_info"
_LEVELS = ("ok", "warning", "error")

_CREDENTIAL_DETAIL = {
    "env": "API key from the NETLICENSING_API_KEY environment variable (or .env file).",
    "header": (
        "API key from this request's X-NetLicensing-API-Key or Authorization: Bearer header."
    ),
    "demo": "No API key; NETLICENSING_ALLOW_DEMO=true, so the sandbox demo credentials are used.",
    "none": "No API key configured, and demo mode (NETLICENSING_ALLOW_DEMO) is off.",
}


def _auth_source() -> str:
    """Where the credentials of this call come from: env, header, demo or none.

    ``api_key_ctx`` defaults to ``NETLICENSING_API_KEY``; only
    ``ApiKeyMiddleware`` sets it, per HTTP request. A ContextVar is in
    ``copy_context()`` only once it has been set in this context, so a set
    value is the header key and the default is the env key.
    """
    var = _client.api_key_ctx
    if var.get():
        return "header" if var in contextvars.copy_context() else "env"
    return "demo" if is_demo_mode() else "none"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


@dataclass
class _Probe:
    """Outcome of the connection check."""

    valid: bool | None
    level: str
    checks: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def _hint(exc: NetLicensingError) -> str:
    """The error-hint sentence for *exc* (fixed text, never the detail or a key)."""
    return str(error_hint(exc, _SELF)["hint"])


def _retry_steps(source: str) -> list[str]:
    """How to apply a new key and check again (none for the fixed demo credentials)."""
    if source == "header":
        return [
            "Update the key your MCP client sends in the header, "
            "then run netlicensing_server_info again."
        ]
    if source == "env":
        return [
            "After changing NETLICENSING_API_KEY, restart the MCP server (or the client that "
            "starts it) and run netlicensing_server_info again."
        ]
    return []


def _unreachable(exc: NetLicensingError, detail: str) -> _Probe:
    return _Probe(
        valid=None,
        level="error",
        checks=[_check("reachable", False, detail)],
        next_steps=[_hint(exc)],
    )


def _from_api_error(exc: NetLicensingError, host: str, source: str) -> _Probe:
    status = exc.status_code
    if status in (502, 504) and isinstance(exc.__cause__, httpx.HTTPError):
        what = "timed out" if status == 504 else "could not be reached"
        return _unreachable(exc, f"The NetLicensing API at {host} {what}.")
    reachable = _check("reachable", True, f"The NetLicensing API at {host} answered.")
    if status == 401:
        # API Conventions: 401 = missing or wrong credentials.
        return _Probe(
            valid=False,
            level="error",
            checks=[
                reachable,
                _check(
                    "authentication", False, "NetLicensing rejected the credentials (HTTP 401)."
                ),
            ],
            next_steps=[_hint(exc), *_retry_steps(source)],
        )
    if status == 403:
        # API Conventions: 403 = authenticated, but the key's role may not call this operation.
        return _Probe(
            valid=True,
            level="warning",
            checks=[
                reachable,
                _check(
                    "authentication",
                    True,
                    "NetLicensing accepted the API key; HTTP 403 means authenticated but "
                    "not permitted.",
                ),
                _check(
                    "permission",
                    False,
                    "The API key's role does not allow listing products (HTTP 403).",
                ),
            ],
            warnings=[
                "The API key is valid, but its role does not allow listing products, so tools "
                "that need a higher role will fail with HTTP 403; license validation works with "
                "any role."
            ],
            next_steps=[_hint(exc), *_retry_steps(source)],
        )
    if status == 502:
        what = "did not answer with a NetLicensing JSON response"
    else:
        what = f"answered HTTP {status}"
    warning = f"The NetLicensing API {what}, so the credentials could not be verified."
    return _Probe(
        valid=None,
        level="warning",
        checks=[reachable, _check("api_read", False, warning)],
        warnings=[warning],
        next_steps=[_hint(exc)],
    )


async def _probe(host: str, source: str) -> _Probe:
    """List one product with a short timeout; never raises (except cancellation)."""
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            await products.list_products(filter_str=_CHECK_FILTER)
    except NetLicensingError as exc:
        return _from_api_error(exc, host, source)
    except TimeoutError:
        return _unreachable(
            NetLicensingError(504, "NetLicensing API request timed out"),
            f"The NetLicensing API at {host} did not answer within "
            f"{_CHECK_TIMEOUT_SECONDS:g} seconds.",
        )
    except Exception as exc:  # server_info must never raise
        # Only the exception type: its message could carry request details.
        logger.warning("server_info connection check failed: %s", type(exc).__name__)
        warning = (
            f"The connection check failed unexpectedly ({type(exc).__name__}), "
            "so the credentials could not be verified."
        )
        return _Probe(
            valid=None,
            level="warning",
            checks=[_check("api_read", False, warning)],
            warnings=[warning],
            next_steps=["Run netlicensing_server_info again; if this persists, check the logs."],
        )
    return _Probe(
        valid=True,
        level="ok",
        checks=[
            _check("reachable", True, f"The NetLicensing API at {host} answered."),
            _check(
                "authentication",
                True,
                "The credentials were accepted (test read: list products, 1 item).",
            ),
        ],
    )


def _no_key_steps(transport: str) -> list[str]:
    if transport == "http":
        return [
            "Send your NetLicensing API key with every request in the "
            + "X-NetLicensing-API-Key header, or as Authorization: Bearer <key>."
        ]
    return [
        "Set NETLICENSING_API_KEY to your NetLicensing API key (sign in at "
        + "https://ui.netlicensing.io, open your API keys and create one) in the env "
        + "settings of this server in your MCP client, then restart the client.",
        "To try the public sandbox without an account, set NETLICENSING_ALLOW_DEMO=true "
        + "instead (sandbox data only; never in production).",
    ]


@tool(title="Get server info", annotations=_READONLY)
async def netlicensing_server_info(check_connection: bool = True) -> str:
    """Check this MCP server's setup and its NetLicensing connection.

    Call this FIRST on a new setup, and whenever another tool fails with an
    authentication, connection or configuration error: 'status' ("ok",
    "warning" or "error") and 'next_steps' (plain-language sentences to pass
    on to the user) say what to fix.

    Returns version, NetLicensing API host (base_url), demo_mode, transport
    (stdio or http), toolsets, read_only and tool_count, plus 'auth'
    ({configured, source: env|header|demo|none, valid: true|false|null}),
    'checks' ([{name, ok, detail}]) and 'warnings'. Never returns the API key.

    Args:
        check_connection: When true (default), make one cheap read-only API call (list one product, short timeout) to check that the API is reachable and accepts the credentials; when false, make no API call (auth.valid stays null)
    """
    source = _auth_source()
    transport = active_transport()
    host = _client.base_url_host() or ""
    configured = source != "none"
    level = "ok"
    valid: bool | None = None
    checks = [_check("credentials", configured, _CREDENTIAL_DETAIL[source])]
    warnings: list[str] = []
    next_steps: list[str] = []

    if not configured:
        level = "error"
        next_steps += _no_key_steps(transport)
    if source == "demo":
        level = "warning"
        warnings.append(_client.DEMO_MODE_WARNING)
        next_steps.append(
            "To work with your own NetLicensing account, set NETLICENSING_API_KEY and remove "
            "NETLICENSING_ALLOW_DEMO=true, then restart the server."
        )
    if configured and check_connection:
        probe = await _probe(host or "the NETLICENSING_BASE_URL host", source)
        valid = probe.valid
        level = max(level, probe.level, key=_LEVELS.index)
        checks += probe.checks
        warnings += probe.warnings
        next_steps = probe.next_steps + next_steps
    elif configured:
        next_steps.append(
            "Run netlicensing_server_info with check_connection=true to check that the API "
            "is reachable and accepts the credentials."
        )

    return json.dumps(
        {
            "version": _server_version(),
            "base_url": host,
            "demo_mode": is_demo_mode(),
            "status": level,
            "transport": transport,
            "auth": {"configured": configured, "source": source, "valid": valid},
            "checks": checks,
            "warnings": warnings,
            "next_steps": next_steps,
            **active_tool_settings(),
        },
        indent=2,
    )
