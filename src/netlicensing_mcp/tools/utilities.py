"""Tools: Utilities — reference data from the NetLicensing API."""

from __future__ import annotations

from netlicensing_mcp.client import nl_get


async def list_licensing_models() -> dict:
    """Return all licensing models supported by the service."""
    return await nl_get("/utility/licensingModels")


async def list_license_types() -> dict:
    """Return all license types supported by the service."""
    return await nl_get("/utility/licenseTypes")


async def list_countries() -> dict:
    """Return all countries available for VAT and localization settings."""
    return await nl_get("/utility/countries")
