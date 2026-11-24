"""Tools: Transactions — payment/checkout transaction records."""

from __future__ import annotations

from netlicensing_mcp.client import ClientValidationError, nl_get, nl_post
from netlicensing_mcp.tools.helpers import (
    TRANSACTION_SOURCES,
    TRANSACTION_STATUSES,
    first_item_property,
    require_one_of,
)


async def list_transactions(filter_str: str | None = None) -> dict:
    """List all transactions for the current vendor.

    filter_str: optional server-side filter expression (e.g. 'status=CLOSED').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/transaction", params or None)


async def get_transaction(transaction_number: str) -> dict:
    """Get a specific transaction by number."""
    return await nl_get(f"/transaction/{transaction_number}")


def _reject_dates(**dates: str | None) -> None:
    """NetLicensing sets dateCreated/dateClosed itself; a client value would only be
    stored as a misleading custom property, so refuse it instead of accepting it silently."""
    given = [n for n, v in dates.items() if v]
    if given:
        raise ClientValidationError(
            f"{', '.join(given)} cannot be set: NetLicensing records the real creation and "
            "close times itself (a supplied value would only be stored as a custom property). "
            "Omit the argument."
        )


async def create_transaction(
    status: str,
    source: str = "SHOP",
    licensee_number: str | None = None,
    number: str | None = None,
    name: str | None = None,
    active: bool = True,
    date_created: str | None = None,
    date_closed: str | None = None,
    payment_method: str | None = None,
) -> dict:
    """
    Create a new transaction.

    status: CANCELLED | CLOSED | PENDING
    source: SHOP | AUTO
    name: human-readable transaction name.
    """
    require_one_of("status", status, TRANSACTION_STATUSES)
    require_one_of("source", source, TRANSACTION_SOURCES)
    _reject_dates(date_created=date_created, date_closed=date_closed)
    data: dict[str, str] = {
        "active": str(active).lower(),
        "status": status,
        "source": source,
    }
    if number:
        data["number"] = number
    if name:
        data["name"] = name
    if licensee_number:
        data["licenseeNumber"] = licensee_number
    if payment_method:
        data["paymentMethod"] = payment_method
    return await nl_post("/transaction", data)


async def update_transaction(
    transaction_number: str,
    status: str | None = None,
    active: bool | None = None,
    name: str | None = None,
    date_closed: str | None = None,
    payment_method: str | None = None,
) -> dict:
    """Update a transaction's status or properties.

    name: human-readable transaction name.
    """
    require_one_of("status", status, TRANSACTION_STATUSES)
    _reject_dates(date_closed=date_closed)
    data: dict[str, str] = {}
    if status is None:
        # Core fails with a NullPointerException when a transaction is updated
        # without a status, so send the one it already has.
        current = first_item_property(await get_transaction(transaction_number), "status")
        if current:
            data["status"] = current
    else:
        data["status"] = status
    if active is not None:
        data["active"] = str(active).lower()
    if name is not None:
        data["name"] = name
    if payment_method is not None:
        data["paymentMethod"] = payment_method
    return await nl_post(f"/transaction/{transaction_number}", data)
