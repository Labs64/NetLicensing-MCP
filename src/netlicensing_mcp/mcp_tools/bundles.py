"""MCP tools for Bundles."""

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
from netlicensing_mcp.tools import bundles


@tool(title="List bundles", annotations=_READONLY)
async def netlicensing_list_bundles(filter: str = "", include_raw: bool = False) -> str:
    """List all bundles in the NetLicensing account.

    Args:
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await bundles.list_bundles(filter_str=filter or None),
            "Bundle",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_bundles")


@tool(title="Get bundle", annotations=_READONLY)
async def netlicensing_get_bundle(bundle_number: str, include_raw: bool = False) -> str:
    """Get details of a specific bundle.

    Args:
        bundle_number: Bundle identifier (e.g. 'B001')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await bundles.get_bundle(bundle_number), "Bundle", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_bundle")


@tool(title="Create bundle", annotations=_WRITE)
async def netlicensing_create_bundle(
    number: str,
    name: str,
    license_template_numbers: list[str],
    active: bool = True,
    price: float | None = None,
    currency: str = "",
    description: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new bundle grouping one or more license templates.

    Args:
        number: Unique bundle number (e.g. 'B001')
        name: Human-readable bundle name
        license_template_numbers: List of license template numbers included in the bundle
        active: Whether the bundle is active
        price: Optional bundle price
        currency: ISO 4217 currency code (e.g. EUR, USD — leave empty for account default)
        description: Optional bundle description
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await bundles.create_bundle(
                number,
                name,
                license_template_numbers,
                active,
                price=price,
                currency=currency or None,
                description=description,
            ),
            "Bundle",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_create_bundle")


@tool(title="Update bundle", annotations=_UPDATE)
async def netlicensing_update_bundle(
    bundle_number: str,
    name: str = "",
    active: bool | None = None,
    license_template_numbers: list[str] | None = None,
    price: float | None = None,
    currency: str = "",
    description: str = "",
    include_raw: bool = False,
) -> str:
    """Update an existing bundle's fields.

    Args:
        bundle_number: Bundle to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        license_template_numbers: New list of license template numbers (omit to keep current)
        price: New price (omit to keep current)
        currency: New currency code (leave empty to keep current)
        description: New description (leave empty to keep current)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await bundles.update_bundle(
                bundle_number,
                name or None,
                active,
                license_template_numbers,
                price,
                currency or None,
                description or None,
            ),
            "Bundle",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_bundle")


@tool(title="Preview deletion of bundle", annotations=_READONLY)
async def netlicensing_preview_delete_bundle(bundle_number: str) -> str:
    """Preview what would be deleted when deleting a bundle.

    Bundles reference license templates but do not own them; only the bundle
    record itself is removed. Returns a confirmation token.

    Args:
        bundle_number: Bundle to preview deletion for
    """
    try:
        bundle_resp = await bundles.get_bundle(bundle_number)
        props = _extract_props(bundle_resp)
        return _json(
            safety.make_delete_preview(
                "delete_bundle",
                bundle_number,
                affected={
                    "license_templates": "referenced only — will NOT be deleted",
                },
                samples={
                    "bundle_name": props.get("name", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
            )
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_delete_bundle")


@tool(title="Delete bundle", annotations=_DELETE)
async def netlicensing_delete_bundle(
    bundle_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a bundle permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_bundle)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        bundle_number: Bundle to delete
        force_cascade: Force deletion even if dependencies exist
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_bundle", bundle_number)
            return await bundles.delete_bundle(bundle_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        bundle_resp = await bundles.get_bundle(bundle_number)
        props = _extract_props(bundle_resp)
        return _json(
            safety.make_delete_preview(
                "delete_bundle",
                bundle_number,
                affected={"license_templates": "referenced only — will NOT be deleted"},
                samples={
                    "bundle_name": props.get("name", ""),
                    "price": _fmt_price(props.get("price"), props.get("currency")) or "",
                },
            )
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_bundle")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_bundle")


@tool(title="Obtain bundle", annotations=_WRITE)
async def netlicensing_obtain_bundle(
    bundle_number: str,
    licensee_number: str,
    include_raw: bool = False,
) -> str:
    """Obtain a bundle for a customer — creates licenses from all license
    templates included in the bundle for the specified licensee.

    Args:
        bundle_number: Bundle to obtain
        licensee_number: Customer (licensee) who receives the licenses
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await bundles.obtain_bundle(bundle_number, licensee_number),
            "License",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_obtain_bundle")
