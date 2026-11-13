"""Tools: Licenses — individual license records assigned to licensees."""

from __future__ import annotations

from netlicensing_mcp.tools.helpers import first_item_property, scoped_filter
from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_licenses(
    licensee_number: str,
    filter_str: str | None = None,
    page: int | None = None,
    items_per_page: int | None = None,
) -> dict:
    """List all licenses for a specific licensee.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    page / items_per_page: optional paging. All criteria (including
        licenseeNumber) go into the ``filter`` query parameter using the
        semicolon-separated format required by the NetLicensing API for
        scoping, pagination and total-item counts — a bare
        query parameter is ignored by the API
        (e.g. ``filter=licenseeNumber=I001;page=0;items=100``).
    """
    return await nl_get(
        "/license",
        scoped_filter("licenseeNumber", licensee_number, filter_str, page, items_per_page),
    )


_MAX_PAGES = 50  # 100 items per page (API maximum) → up to 5,000 licenses


async def list_all_licenses(licensee_number: str) -> dict:
    """List every license of a licensee, following pagination.

    Returns the first page's envelope with ``items.item`` holding all pages.
    """
    first = await list_licenses(licensee_number, page=0, items_per_page=100)
    items_obj = first.get("items")
    if not isinstance(items_obj, dict):
        return first
    collected = list(items_obj.get("item") or [])
    try:
        total_pages = int(items_obj.get("totalpages", 1))
    except (TypeError, ValueError):
        total_pages = 1
    for page in range(1, min(total_pages, _MAX_PAGES)):
        resp = await list_licenses(licensee_number, page=page, items_per_page=100)
        page_items = (resp.get("items") or {}).get("item") or []
        if not page_items:
            break
        collected.extend(page_items)
    return {**first, "items": {**items_obj, "item": collected}}


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

    A new price without a currency keeps the license's current currency.
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
    if "price" in data and "currency" not in data:
        # NetLicensing rejects a price without a currency; keep the current one.
        current = first_item_property(await nl_get(f"/license/{license_number}"), "currency")
        if current:
            data["currency"] = current
    return await nl_post(f"/license/{license_number}", data)


async def delete_license(license_number: str, force_cascade: bool = False) -> str:
    """Delete a license."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/license/{license_number}", params or None)
    return f"License {license_number} deleted (HTTP {status})."
