"""MCP tools for Licensees (customers)."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _UPDATE,
    _WRITE,
    _error,
    _json,
    _sample_numbers,
    _total_items,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import (
    licensees,
    licenses,
)


@tool(title="List licensees", annotations=_READONLY)
async def netlicensing_list_licensees(
    product_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all customers (licensees) for a product.

    Args:
        product_number: Product to list customers for
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licensees.list_licensees(
                product_number,
                filter_str=filter or None,
            ),
            "Licensee",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Get licensee", annotations=_READONLY)
async def netlicensing_get_licensee(licensee_number: str, include_raw: bool = False) -> str:
    """Get a specific licensee (customer).

    Args:
        licensee_number: Licensee identifier (e.g. 'I001')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licensees.get_licensee(licensee_number),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Create licensee", annotations=_WRITE)
async def netlicensing_create_licensee(
    product_number: str,
    number: str = "",
    name: str = "",
    active: bool = True,
    marked_for_transfer: bool | None = None,
    licensee_secret: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new customer (licensee) under a product.

    Args:
        product_number: Product to associate the customer with
        number: Optional custom licensee number (auto-generated if empty)
        name: Optional display name for the customer
        active: Whether the licensee is active
        marked_for_transfer: Mark licensee for license transfer
        licensee_secret: Secret for licensee identification (when product licenseeSecretMode is PREDEFINED)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licensees.create_licensee(
                product_number,
                number or None,
                name or None,
                active,
                marked_for_transfer=marked_for_transfer,
                licensee_secret=licensee_secret or None,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Update licensee", annotations=_UPDATE)
async def netlicensing_update_licensee(
    licensee_number: str,
    name: str = "",
    active: bool | None = None,
    marked_for_transfer: bool | None = None,
    licensee_secret: str = "",
    include_raw: bool = False,
) -> str:
    """Update a licensee's properties.

    Args:
        licensee_number: Licensee to update
        name: New name (empty to keep current)
        active: New active state (omit to keep current)
        marked_for_transfer: Mark for license transfer (omit to keep current)
        licensee_secret: Secret for licensee identification (leave empty to keep current)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licensees.update_licensee(
                licensee_number,
                name or None,
                active,
                marked_for_transfer=marked_for_transfer,
                licensee_secret=licensee_secret or None,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Preview deletion of licensee", annotations=_READONLY)
async def netlicensing_preview_delete_licensee(licensee_number: str) -> str:
    """Preview what would be deleted when deleting a licensee.

    Returns the count of licenses that would be removed and a confirmation token.

    Args:
        licensee_number: Licensee to preview deletion for
    """
    try:
        await licensees.get_licensee(licensee_number)  # raises if it does not exist
        licenses_resp = await licenses.list_licenses(licensee_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_licensee",
                licensee_number,
                affected={"licenses": _total_items(licenses_resp)},
                samples={"licenses": _sample_numbers(licenses_resp)},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Delete licensee", annotations=_DELETE)
async def netlicensing_delete_licensee(
    licensee_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a licensee and all their licenses permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_licensee)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        licensee_number: Licensee to delete
        force_cascade: Also delete all dependent licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_licensee", licensee_number)
            return await licensees.delete_licensee(licensee_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        await licensees.get_licensee(licensee_number)  # raises if it does not exist
        licenses_resp = await licenses.list_licenses(licensee_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_licensee",
                licensee_number,
                affected={"licenses": _total_items(licenses_resp)},
                samples={"licenses": _sample_numbers(licenses_resp)},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Validate licensee", annotations=_WRITE)
async def netlicensing_validate_licensee(
    licensee_number: str,
    product_number: str = "",
    licensee_name: str = "",
    session_id: str = "",
    action: str = "",
    product_module_number: str = "",
    node_secret: str = "",
    dry_run: bool = False,
    include_raw: bool = False,
) -> str:
    """Validate a customer's licenses across all product modules.

    Returns the list envelope with one ProductModuleValidation item per module
    (validity, type, expiry, usage; Floating expirationTimestamp and session data
    are kept), even when only one module is validated. API infos (ERROR, WARNING,
    INFO — e.g. "No free floating licenses found.") appear in 'warnings'.

    Module-scoped parameters (session_id, action, node_secret) require
    product_module_number, and one call addresses ONE module. A call that is not
    a dry run still validates every module of the product, so other Floating or
    NodeLocked modules may report their own missing-parameter errors.

    Args:
        licensee_number: Customer to validate
        product_number: Optional — scope validation to a specific product
        licensee_name: Human-readable name for auto-created licensees (when licenseeAutoCreate is enabled)
        session_id: Floating model — unique session identifier (needs product_module_number;
            required with action)
        action: Floating model — 'checkOut' or 'checkIn' (needs product_module_number and session_id)
        product_module_number: Module that session_id / action / node_secret apply to;
            required when any of them is given
        node_secret: NodeLocked model — unique device/node secret (needs product_module_number)
        dry_run: When true, validate without side effects: never checks out, checks in,
            binds a node or consumes anything. Default false.
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await licensees.validate_licensee(
                licensee_number,
                product_number=product_number or None,
                licensee_name=licensee_name or None,
                session_id=session_id or None,
                action=action or None,
                product_module_number=product_module_number or None,
                node_secret=node_secret or None,
                dry_run=dry_run,
            ),
            "ProductModuleValidation",
            include_raw=include_raw,
            as_list=True,
            warn_info_types=("ERROR", "WARNING", "INFO"),
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Transfer licenses", annotations=_UPDATE)
async def netlicensing_transfer_licenses(
    from_licensee_number: str,
    to_licensee_number: str,
    include_raw: bool = False,
) -> str:
    """Transfer all licenses from one licensee to another.

    The source licensee must be marked for transfer (markedForTransfer=true)
    and both licensees must be active. The source licensee is consumed.

    Args:
        from_licensee_number: Source licensee
        to_licensee_number: Destination licensee
        include_raw: Accepted for consistency; the API returns no body (204)
    """
    try:
        return _json(await licensees.transfer_licenses(from_licensee_number, to_licensee_number))
    except NetLicensingError as exc:
        return _error(exc)
