"""MCP tools for License Templates."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _UPDATE,
    _WRITE,
    _error,
    _extract_props,
    _fmt_price,
    _json,
    _price_active_diff,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import license_templates
from netlicensing_mcp.tools.helpers import CustomPropertyValue


@tool(title="List license templates", annotations=_READONLY)
async def netlicensing_list_license_templates(
    module_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all license templates for a product module.

    Args:
        module_number: Module whose templates to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await license_templates.list_license_templates(
                module_number,
                filter_str=filter or None,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Get license template", annotations=_READONLY)
async def netlicensing_get_license_template(template_number: str, include_raw: bool = False) -> str:
    """Get a specific license template.

    Args:
        template_number: Template identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await license_templates.get_license_template(template_number),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Create license template", annotations=_WRITE)
async def netlicensing_create_license_template(
    module_number: str,
    number: str,
    name: str,
    license_type: str,
    price: float = 0.0,
    currency: str = "EUR",
    automatic: bool = False,
    hidden: bool = False,
    hide_licenses: bool = False,
    active: bool = True,
    time_volume: int | None = None,
    time_volume_period: str = "",
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
    custom_properties: dict[str, CustomPropertyValue] | None = None,
    include_raw: bool = False,
) -> str:
    """Create a license template.

    Args:
        module_number: Parent product module
        number: Unique template number (e.g. 'LT01')
        name: Template display name
        license_type: FEATURE | TIMEVOLUME | FLOATING | QUANTITY
        price: Template price (0 for free)
        currency: ISO 4217 currency code (default EUR)
        automatic: Auto-assign this license to new licensees
        hidden: Hide template in NetLicensing Shop
        hide_licenses: Hide licenses derived from this template in the Shop
        active: Whether the template is active
        time_volume: Number of time units (TIMEVOLUME type)
        time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME type)
        max_sessions: Concurrent sessions allowed (FLOATING type)
        quantity: Usage quota (QUANTITY / PayPerUse type)
        grace_period: Allow grace period after expiry (Subscription model)
        custom_properties: Additional properties as key-value pairs (e.g. skus for PricingTable, description)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await license_templates.create_license_template(
                module_number,
                number,
                name,
                license_type,
                active,
                price,
                currency,
                automatic,
                hidden=hidden,
                hide_licenses=hide_licenses,
                time_volume=time_volume,
                time_volume_period=time_volume_period or None,
                max_sessions=max_sessions,
                quantity=quantity,
                grace_period=grace_period,
                custom_properties=custom_properties,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Preview update of license template", annotations=_READONLY)
async def netlicensing_preview_update_license_template(
    template_number: str,
    active: bool | None = None,
    price: float | None = None,
    currency: str = "",
) -> str:
    """Preview a sensitive license template update (price, currency, or active state).

    Returns a diff table of the proposed changes and a confirmation token. Pass
    the token to netlicensing_update_license_template within 5 minutes to apply.

    Args:
        template_number: Template to preview changes for
        active: Proposed new active state (omit to skip)
        price: Proposed new price (omit to skip)
        currency: Proposed new currency code (leave empty to skip)
    """
    try:
        current_resp = await license_templates.get_license_template(template_number)
        diff = _price_active_diff(_extract_props(current_resp), price, currency, active)
        return _json(safety.make_update_preview("update_license_template", template_number, diff))
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Update license template", annotations=_UPDATE)
async def netlicensing_update_license_template(
    template_number: str,
    name: str = "",
    active: bool | None = None,
    price: float | None = None,
    currency: str = "",
    automatic: bool | None = None,
    hidden: bool | None = None,
    hide_licenses: bool | None = None,
    time_volume: int | None = None,
    time_volume_period: str = "",
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
    custom_properties: dict[str, CustomPropertyValue] | None = None,
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update a license template's properties.

    Changing price, currency, or active requires a confirmation token (revenue /
    availability impact). Call netlicensing_preview_update_license_template first.

    Args:
        template_number: Template to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        price: New price (omit to keep current)
        currency: New ISO 4217 currency code (leave empty to keep current)
        automatic: Auto-assign to new licensees (omit to keep current)
        hidden: Hide template in NetLicensing Shop (omit to keep current)
        hide_licenses: Hide derived licenses in the Shop (omit to keep current)
        time_volume: Number of time units — TIMEVOLUME type (omit to keep current)
        time_volume_period: DAY | WEEK | MONTH | YEAR — TIMEVOLUME type (leave empty to keep current)
        max_sessions: Concurrent sessions — FLOATING type (omit to keep current)
        quantity: Usage quota — QUANTITY / PayPerUse type (omit to keep current)
        grace_period: Grace period after expiry — Subscription model (omit to keep current)
        custom_properties: Additional properties to set or update as key-value pairs
        confirm_token: Confirmation token (required when price, currency, or active change)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        sensitive = price is not None or bool(currency) or active is not None

        if sensitive:
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_license_template", template_number
                )
            else:
                current_resp = await license_templates.get_license_template(template_number)
                diff = _price_active_diff(_extract_props(current_resp), price, currency, active)
                return _json(
                    safety.make_update_preview("update_license_template", template_number, diff)
                )

        return _wrap_json(
            await license_templates.update_license_template(
                template_number,
                name or None,
                active,
                price,
                currency=currency or None,
                automatic=automatic,
                hidden=hidden,
                hide_licenses=hide_licenses,
                time_volume=time_volume,
                time_volume_period=time_volume_period or None,
                max_sessions=max_sessions,
                quantity=quantity,
                grace_period=grace_period,
                custom_properties=custom_properties,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Preview deletion of license template", annotations=_READONLY)
async def netlicensing_preview_delete_license_template(template_number: str) -> str:
    """Preview what would be deleted when deleting a license template.

    Dependent licenses cannot be efficiently counted without enumerating all
    licensees, so the preview always warns that licenses may be affected.
    Returns a confirmation token.

    Args:
        template_number: Template to preview deletion for
    """
    try:
        template_resp = await license_templates.get_license_template(template_number)
        props = _extract_props(template_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license_template",
                template_number,
                affected={
                    "licenses": "unknown — may have licenses derived from this template",
                },
                samples={
                    "template_name": props.get("name", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Delete license template", annotations=_DELETE)
async def netlicensing_delete_license_template(
    template_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a license template.

    Because dependent licenses cannot be cheaply enumerated, a confirmation
    token is always required. Call netlicensing_preview_delete_license_template
    first to obtain one.

    Args:
        template_number: Template to delete
        force_cascade: Also delete all dependent licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_license_template", template_number)
            return await license_templates.delete_license_template(template_number, force_cascade)

        template_resp = await license_templates.get_license_template(template_number)
        props = _extract_props(template_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license_template",
                template_number,
                affected={
                    "licenses": "unknown — may have licenses derived from this template",
                },
                samples={
                    "template_name": props.get("name", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)
