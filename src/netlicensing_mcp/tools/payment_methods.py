"""Tools: Payment Methods — vendor payment configuration."""

from __future__ import annotations

from netlicensing_mcp.client import nl_get, nl_post


async def list_payment_methods(filter_str: str | None = None) -> dict:
    """List all payment methods for the current vendor.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/paymentmethod", params or None)


async def get_payment_method(payment_method_number: str) -> dict:
    """Get a specific payment method by number."""
    return await nl_get(f"/paymentmethod/{payment_method_number}")


async def update_payment_method(
    payment_method_number: str,
    active: bool | None = None,
    paypal_subject: str | None = None,
) -> dict:
    """
    Update a payment method's configuration.

    paypal_subject: The e-mail address of the PayPal account.
    """
    data: dict[str, str] = {}
    if active is not None:
        data["active"] = str(active).lower()
    if paypal_subject is not None:
        data["paypal.subject"] = paypal_subject
    return await nl_post(f"/paymentmethod/{payment_method_number}", data)
