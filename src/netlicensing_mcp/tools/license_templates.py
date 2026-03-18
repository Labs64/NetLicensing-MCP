"""Tools: License Templates — define what licenses look like within a module."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_license_templates(
    module_number: str,
    filter_str: str | None = None,
) -> dict:
    """List all license templates for a product module.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {"productModuleNumber": module_number}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/licensetemplate", params)


async def get_license_template(template_number: str) -> dict:
    """Get a specific license template."""
    return await nl_get(f"/licensetemplate/{template_number}")


async def create_license_template(
    module_number: str,
    number: str,
    name: str,
    license_type: str,
    active: bool = True,
    price: float | None = None,
    currency: str = "EUR",
    automatic: bool = False,
    hidden: bool = False,
    hide_licenses: bool = False,
    time_volume: int | None = None,
    time_volume_period: str | None = None,
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
) -> dict:
    """
    Create a license template.

    license_type values: FEATURE, TIMEVOLUME, FLOATING, QUANTITY

    Type / model-specific parameters:
      time_volume: number of time units (TIMEVOLUME).
      time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME).
      max_sessions: concurrent sessions allowed (FLOATING).
      quantity: usage quota (QUANTITY / PayPerUse).
      grace_period: allow grace period after expiry (Subscription).
    """
    data: dict[str, str] = {
        "productModuleNumber": module_number,
        "number": number,
        "name": name,
        "licenseType": license_type,
        "active": str(active).lower(),
        "automatic": str(automatic).lower(),
        "hidden": str(hidden).lower(),
        "hideLicenses": str(hide_licenses).lower(),
        "currency": currency,
    }
    if price is not None:
        data["price"] = str(price)
    if time_volume is not None:
        data["timeVolume"] = str(time_volume)
    if time_volume_period:
        data["timeVolumePeriod"] = time_volume_period
    if max_sessions is not None:
        data["maxSessions"] = str(max_sessions)
    if quantity is not None:
        data["quantity"] = str(quantity)
    if grace_period is not None:
        data["gracePeriod"] = str(grace_period).lower()
    return await nl_post("/licensetemplate", data)


async def update_license_template(
    template_number: str,
    name: str | None = None,
    active: bool | None = None,
    price: float | None = None,
    currency: str | None = None,
    automatic: bool | None = None,
    hidden: bool | None = None,
    hide_licenses: bool | None = None,
    time_volume: int | None = None,
    time_volume_period: str | None = None,
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
) -> dict:
    """Update a license template.

    Type / model-specific parameters:
      time_volume: number of time units (TIMEVOLUME).
      time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME).
      max_sessions: concurrent sessions allowed (FLOATING).
      quantity: usage quota (QUANTITY / PayPerUse).
      grace_period: allow grace period after expiry (Subscription).
    """
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if price is not None:
        data["price"] = str(price)
    if currency is not None:
        data["currency"] = currency
    if automatic is not None:
        data["automatic"] = str(automatic).lower()
    if hidden is not None:
        data["hidden"] = str(hidden).lower()
    if hide_licenses is not None:
        data["hideLicenses"] = str(hide_licenses).lower()
    if time_volume is not None:
        data["timeVolume"] = str(time_volume)
    if time_volume_period is not None:
        data["timeVolumePeriod"] = time_volume_period
    if max_sessions is not None:
        data["maxSessions"] = str(max_sessions)
    if quantity is not None:
        data["quantity"] = str(quantity)
    if grace_period is not None:
        data["gracePeriod"] = str(grace_period).lower()
    return await nl_put(f"/licensetemplate/{template_number}", data)


async def delete_license_template(template_number: str, force_cascade: bool = False) -> str:
    """Delete a license template."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/licensetemplate/{template_number}", params or None)
    return f"Template {template_number} deleted (HTTP {status})."
