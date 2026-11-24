"""MCP tools for Transactions."""

from __future__ import annotations

from netlicensing_mcp.app import (
    _READONLY,
    _UPDATE,
    _WRITE,
    _error,
    _list_filter,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import transactions


@tool(title="List transactions", annotations=_READONLY)
async def netlicensing_list_transactions(
    filter: str = "",
    page: int | None = None,
    page_size: int | None = None,
    compact: bool = False,
    include_raw: bool = False,
) -> str:
    """List all transactions in the account.

    Args:
        ; supported keys: status, active (others are ignored with a warning; malformed expressions are rejected)
        page: Page to return, 0-based (default 0; overrides 'page' in filter)
        page_size: Items per page, 1-100 (default 25; overrides 'items' in filter)
        compact: When true, return only type, number, name, status and active for each item
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        filter = _list_filter(
            filter,
            page,
            page_size,
            supported=(
                "status",
                "active",
            ),
        )
        return _wrap_json(
            await transactions.list_transactions(
                filter_str=filter or None,
            ),
            "Transaction",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
            compact=compact,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_transactions")


@tool(title="Get transaction", annotations=_READONLY)
async def netlicensing_get_transaction(transaction_number: str, include_raw: bool = False) -> str:
    """Get details of a specific transaction.

    Args:
        transaction_number: Transaction identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await transactions.get_transaction(transaction_number),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_transaction")


@tool(title="Create transaction", annotations=_WRITE)
async def netlicensing_create_transaction(
    status: str,
    source: str = "SHOP",
    licensee_number: str = "",
    number: str = "",
    name: str = "",
    active: bool = True,
    date_created: str = "",
    date_closed: str = "",
    payment_method: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new transaction.

    Args:
        status: CANCELLED | CLOSED | PENDING
        source: Transaction source — SHOP or AUTO (default SHOP)
        licensee_number: Optional — associated licensee
        number: Optional custom transaction number (auto-generated if empty)
        name: Optional human-readable transaction name
        active: Whether the transaction is active
        date_created: Not supported — NetLicensing sets the creation time itself; a value is rejected (leave empty)
        date_closed: Not supported — NetLicensing sets the close time itself; a value is rejected (leave empty)
        payment_method: Optional payment method number
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await transactions.create_transaction(
                status,
                source,
                licensee_number=licensee_number or None,
                number=number or None,
                name=name or None,
                active=active,
                date_created=date_created or None,
                date_closed=date_closed or None,
                payment_method=payment_method or None,
            ),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_create_transaction")


@tool(title="Update transaction", annotations=_UPDATE)
async def netlicensing_update_transaction(
    transaction_number: str,
    status: str = "",
    active: bool | None = None,
    name: str = "",
    date_closed: str = "",
    payment_method: str = "",
    include_raw: bool = False,
) -> str:
    """Update a transaction's status or properties.

    Args:
        transaction_number: Transaction to update
        status: CANCELLED | CLOSED | PENDING (leave empty to keep current)
        active: Set active state (omit to keep current)
        name: Human-readable name (leave empty to keep current)
        date_closed: Not supported — NetLicensing sets the close time itself; a value is rejected (leave empty). Note: a CLOSED transaction can be set back to PENDING and keeps its old close time; there is no delete tool, so cancel unwanted transactions
        payment_method: Payment method number (leave empty to keep current)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await transactions.update_transaction(
                transaction_number,
                status=status or None,
                active=active,
                name=name or None,
                date_closed=date_closed or None,
                payment_method=payment_method or None,
            ),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_transaction")
