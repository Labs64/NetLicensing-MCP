"""MCP tools for reference data (licensing models, license types, countries) and server info."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from urllib.parse import urlsplit

from netlicensing_mcp import client as _client
from netlicensing_mcp.app import (
    _READONLY,
    _error,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError, is_demo_mode
from netlicensing_mcp.tools import utilities


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
async def netlicensing_list_countries(include_raw: bool = False) -> str:
    """List all countries available for VAT and localization settings.

    Args:
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await utilities.list_countries(), "Country", include_raw=include_raw, as_list=True
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_countries")


def _server_version() -> str:
    """Installed package version (from package metadata, not a literal)."""
    try:
        return _pkg_version("netlicensing-mcp")
    except PackageNotFoundError:
        return "unknown"


@tool(title="Get server info", annotations=_READONLY)
async def netlicensing_server_info() -> str:
    """Return this MCP server's version, NetLicensing API host and demo-mode flag.

    Read-only; makes no API call and returns no secrets.
    """
    return json.dumps(
        {
            "version": _server_version(),
            "base_url": urlsplit(_client.BASE_URL).hostname or "",
            "demo_mode": is_demo_mode(),
        },
        indent=2,
    )
