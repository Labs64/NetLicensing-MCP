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
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import licenses


@tool(title="List licenses", annotations=_READONLY)
async def netlicensing_list_licenses(
    licensee_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all licenses for a specific customer.

    Args:
        licensee_number: Customer whose licenses to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licenses.list_licenses(
                licensee_number,
                filter_str=filter or None,
            ),
            "License",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
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
        start_date: ISO 8601 datetime — mandatory for TIMEVOLUME type
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
    include_raw: bool = False,
) -> str:
    """Update a license's properties.

    Args:
        license_number: License to update
        active: True to activate, False to deactivate (omit to keep current)
        name: New display name (leave empty to keep current)
        start_date: ISO 8601 datetime — TIMEVOLUME type (leave empty to keep current)
        price: License price (omit to keep current)
        currency: ISO 4217 currency code (leave empty to keep current)
        time_volume: Duration value — TIMEVOLUME type (leave empty to keep current)
        time_volume_period: DAY | WEEK | MONTH | YEAR (leave empty to keep current)
        quantity: Usage quota — PayPerUse model (leave empty to keep current)
        used_quantity: Used count — PayPerUse model (leave empty to keep current)
        parent_feature: Parent feature — Rental model (leave empty to keep current)
        hidden: Visibility in Shop (omit to keep current)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
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
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_license", license_number)
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
            )
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_license")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_license")
