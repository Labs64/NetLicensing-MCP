"""Tools: Transactions — payment/checkout transaction records."""

from __future__ import annotations

from netlicensing_mcp.client import nl_get, nl_post


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
    if date_created:
        data["dateCreated"] = date_created
    if date_closed:
        data["dateClosed"] = date_closed
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
    data: dict[str, str] = {}
    if status is not None:
        data["status"] = status
    if active is not None:
        data["active"] = str(active).lower()
    if name is not None:
        data["name"] = name
    if date_closed is not None:
        data["dateClosed"] = date_closed
    if payment_method is not None:
        data["paymentMethod"] = payment_method
    return await nl_post(f"/transaction/{transaction_number}", data)
