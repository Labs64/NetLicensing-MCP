"""Tools: Licenses — individual license records assigned to licensees."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_licenses(
    licensee_number: str,
    filter_str: str | None = None,
) -> dict:
    """List all licenses for a specific licensee.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {"licenseeNumber": licensee_number}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/license", params)


async def get_license(license_number: str) -> dict:
    """Get details of a specific license."""
    return await nl_get(f"/license/{license_number}")


async def create_license(
    licensee_number: str,
    license_template_number: str,
    number: str | None = None,
    active: bool = True,
    name: str | None = None,
    start_date: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    time_volume: str | None = None,
    time_volume_period: str | None = None,
    quantity: str | None = None,
    parent_feature: str | None = None,
    hidden: bool | None = None,
) -> dict:
    """
    Create a license for a licensee from a license template.

    Type-specific parameters:
      name: display name (defaults from template).
      start_date: ISO 8601 datetime, mandatory for TIMEVOLUME.
      price: license price (overrides template default).
      currency: ISO 4217 currency code (overrides template default).
      time_volume: duration value, mandatory for TIMEVOLUME.
      time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME).
      quantity: mandatory for PayPerUse / NodeLocked models.
      parent_feature: mandatory for TIMEVOLUME + Rental model.
      hidden: if true, license is hidden from end customer in Shop.
    """
    data: dict[str, str] = {
        "licenseeNumber": licensee_number,
        "licenseTemplateNumber": license_template_number,
        "active": str(active).lower(),
    }
    if number:
        data["number"] = number
    if name:
        data["name"] = name
    if start_date:
        data["startDate"] = start_date
    if price is not None:
        data["price"] = str(price)
    if currency:
        data["currency"] = currency
    if time_volume:
        data["timeVolume"] = time_volume
    if time_volume_period:
        data["timeVolumePeriod"] = time_volume_period
    if quantity:
        data["quantity"] = quantity
    if parent_feature:
        data["parentfeature"] = parent_feature
    if hidden is not None:
        data["hidden"] = str(hidden).lower()
    return await nl_post("/license", data)


async def update_license(
    license_number: str,
    active: bool | None = None,
    name: str | None = None,
    start_date: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    time_volume: str | None = None,
    time_volume_period: str | None = None,
    quantity: str | None = None,
    used_quantity: str | None = None,
    parent_feature: str | None = None,
    hidden: bool | None = None,
) -> dict:
    """
    Update a license's properties.

    active: True to activate, False to deactivate.
    name: display name.
    start_date: ISO 8601 datetime (TIMEVOLUME).
    price: license price.
    currency: ISO 4217 currency code.
    time_volume / time_volume_period: duration (TIMEVOLUME).
    quantity / used_quantity: for PayPerUse model.
    parent_feature: for TIMEVOLUME + Rental model.
    hidden: visibility in Shop.
    """
    data: dict[str, str] = {}
    if active is not None:
        data["active"] = str(active).lower()
    if name is not None:
        data["name"] = name
    if start_date is not None:
        data["startDate"] = start_date
    if price is not None:
        data["price"] = str(price)
    if currency is not None:
        data["currency"] = currency
    if time_volume is not None:
        data["timeVolume"] = time_volume
    if time_volume_period is not None:
        data["timeVolumePeriod"] = time_volume_period
    if quantity is not None:
        data["quantity"] = quantity
    if used_quantity is not None:
        data["usedQuantity"] = used_quantity
    if parent_feature is not None:
        data["parentfeature"] = parent_feature
    if hidden is not None:
        data["hidden"] = str(hidden).lower()
    return await nl_post(f"/license/{license_number}", data)


async def delete_license(license_number: str, force_cascade: bool = False) -> str:
    """Delete a license."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/license/{license_number}", params or None)
    return f"License {license_number} deleted (HTTP {status})."
