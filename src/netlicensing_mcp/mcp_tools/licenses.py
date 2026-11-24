"""MCP tools for Licenses."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _UPDATE,
    _WRITE,
    _confirm_error,
    _error,
    _extract_props,
    _fmt_price,
    _json,
    _list_filter,
    _price_active_diff,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import licenses
from netlicensing_mcp.tools.helpers import require_currency, require_price


@tool(title="List licenses", annotations=_READONLY)
async def netlicensing_list_licenses(
    licensee_number: str,
    filter: str = "",
    page: int | None = None,
    page_size: int | None = None,
    compact: bool = False,
    include_raw: bool = False,
) -> str:
    """List all licenses for a specific customer.

    Args:
        licensee_number: Customer whose licenses to list
        ; supported keys: active (others are ignored with a warning; malformed expressions are rejected)
        page: Page to return, 0-based (default 0; overrides 'page' in filter)
        page_size: Items per page, 1-100 (default 25; overrides 'items' in filter)
        compact: When true, return only type, number, name, status and active for each item
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        filter = _list_filter(filter, page, page_size, supported=("active",))
        return _wrap_json(
            await licenses.list_licenses(
                licensee_number,
                filter_str=filter or None,
            ),
            "License",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
            compact=compact,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_licenses")


@tool(title="Get license", annotations=_READONLY)
async def netlicensing_get_license(license_number: str, include_raw: bool = False) -> str:
    """Get details of a specific license.

    Args:
        license_number: License identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licenses.get_license(license_number),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_license")


@tool(title="Create license", annotations=_WRITE)
async def netlicensing_create_license(
    licensee_number: str,
    license_template_number: str,
    number: str = "",
    active: bool = True,
    name: str = "",
    start_date: str = "",
    price: float | None = None,
    currency: str = "",
    time_volume: str = "",
    time_volume_period: str = "",
    quantity: str = "",
    parent_feature: str = "",
    hidden: bool | None = None,
    include_raw: bool = False,
) -> str:
    """Assign a new license to a customer from a license template.

    Args:
        licensee_number: Customer to assign the license to
        license_template_number: Template defining type and rules
        number: Optional custom license number (auto-generated if empty)
        active: Whether the license is active immediately
        name: Display name (defaults from template if empty)
        start_date: ISO 8601 datetime, or "now" for an immediate start; a time in the past is rejected — mandatory for TIMEVOLUME type
        price: License price (overrides template default, omit to inherit)
        currency: ISO 4217 currency code (overrides template default)
        time_volume: Duration value — mandatory for TIMEVOLUME type
        time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME type)
        quantity: Usage quota — mandatory for PayPerUse / NodeLocked models
        parent_feature: Parent feature — mandatory for TIMEVOLUME + Rental model
        hidden: Hide license from end customer in Shop (omit to inherit)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licenses.create_license(
                licensee_number,
                license_template_number,
                number or None,
                active,
                name=name or None,
                start_date=start_date or None,
                price=price,
                currency=currency or None,
                time_volume=time_volume or None,
                time_volume_period=time_volume_period or None,
                quantity=quantity or None,
                parent_feature=parent_feature or None,
                hidden=hidden,
            ),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_create_license")


@tool(title="Preview update of license", annotations=_READONLY)
async def netlicensing_preview_update_license(
    license_number: str,
    active: bool | None = None,
    price: float | None = None,
    currency: str = "",
) -> str:
    """Preview a sensitive license update (price, currency, or active state).

    Returns a diff table of the proposed changes and a confirmation token. Pass
    the token to netlicensing_update_license within 5 minutes to apply.

    Args:
        license_number: License to preview changes for
        active: Proposed new active state (omit to skip)
        price: Proposed new price (omit to skip)
        currency: Proposed new currency code (leave empty to skip)
    """
    try:
        require_price(price)
        require_currency(currency)
        current_resp = await licenses.get_license(license_number)
        diff = _price_active_diff(_extract_props(current_resp), price, currency, active)
        return _json(
            safety.make_update_preview(
                "update_license",
                license_number,
                diff,
                changes=safety.change_set(price=price, currency=currency, active=active),
            )
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_update_license")


@tool(title="Update license", annotations=_UPDATE)
async def netlicensing_update_license(
    license_number: str,
    active: bool | None = None,
    name: str = "",
    start_date: str = "",
    price: float | None = None,
    currency: str = "",
    time_volume: str = "",
    time_volume_period: str = "",
    quantity: str = "",
    used_quantity: str = "",
    parent_feature: str = "",
    hidden: bool | None = None,
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update a license's properties.

    Changing active, price or currency requires a confirmation token (revenue /
    availability impact). Call netlicensing_preview_update_license first.
    used_quantity must not exceed quantity.

    Args:
        license_number: License to update
        active: True to activate, False to deactivate (omit to keep current)
        name: New display name (leave empty to keep current)
        start_date: ISO 8601 datetime, or "now" for an immediate start; a time in the past is rejected — TIMEVOLUME type (leave empty to keep current)
        price: License price (omit to keep current)
        currency: ISO 4217 currency code (leave empty to keep current)
        time_volume: Duration value — TIMEVOLUME type (leave empty to keep current)
        time_volume_period: DAY | WEEK | MONTH | YEAR (leave empty to keep current)
        quantity: Usage quota — PayPerUse model (leave empty to keep current)
        used_quantity: Used count — PayPerUse model (leave empty to keep current)
        parent_feature: Parent feature — Rental model (leave empty to keep current)
        hidden: Visibility in Shop (omit to keep current)
        confirm_token: Confirmation token (required when active, price or currency change)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        sensitive = active is not None or price is not None or bool(currency)
        if sensitive:
            require_price(price)
            require_currency(currency)
            changes = safety.change_set(price=price, currency=currency, active=active)
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_license", license_number, changes=changes
                )
            else:
                current_resp = await licenses.get_license(license_number)
                diff = _price_active_diff(_extract_props(current_resp), price, currency, active)
                preview = safety.make_update_preview(
                    "update_license", license_number, diff, changes=changes
                )
                if not preview.get("no_change"):
                    return _json(preview)
                # The sensitive fields already hold the requested values: apply the rest.
        return _wrap_json(
            await licenses.update_license(
                license_number,
                active,
                name=name or None,
                start_date=start_date or None,
                price=price,
                currency=currency or None,
                time_volume=time_volume or None,
                time_volume_period=time_volume_period or None,
                quantity=quantity or None,
                used_quantity=used_quantity or None,
                parent_feature=parent_feature or None,
                hidden=hidden,
            ),
            "License",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_update_license")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_license")


@tool(title="Preview deletion of license", annotations=_READONLY)
async def netlicensing_preview_delete_license(license_number: str) -> str:
    """Preview what would be deleted when deleting a license.

    Licenses have no owned dependents. Returns context about the license
    (licensee, template) and a confirmation token.

    Args:
        license_number: License to preview deletion for
    """
    try:
        license_resp = await licenses.get_license(license_number)
        props = _extract_props(license_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license",
                license_number,
                affected={},
                samples={
                    "licensee": props.get("licenseeNumber", ""),
                    "template": props.get("licenseTemplateNumber", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
            )
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_delete_license")


@tool(title="Delete license", annotations=_DELETE)
async def netlicensing_delete_license(
    license_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a license permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_license)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        license_number: License to delete
        force_cascade: Force deletion even if dependencies exist
        confirm_token: Confirmation token from a previous preview call (not proof of human approval: show the preview to the user and wait for their go-ahead)
    """
    try:
        if confirm_token:
            safety.validate_and_consume(
                confirm_token, "delete_license", license_number, force_cascade
            )
            return await licenses.delete_license(license_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        license_resp = await licenses.get_license(license_number)
        props = _extract_props(license_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license",
                license_number,
                affected={},
                samples={
                    "licensee": props.get("licenseeNumber", ""),
                    "template": props.get("licenseTemplateNumber", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
                force_cascade=force_cascade,
            )
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_license")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_license")
