"""MCP tools for Payment Methods."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _READONLY,
    _UPDATE,
    _confirm_error,
    _error,
    _extract_props,
    _json,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import payment_methods


@tool(title="List payment methods", annotations=_READONLY)
async def netlicensing_list_payment_methods(filter: str = "", include_raw: bool = False) -> str:
    """List all payment methods configured for the account.

    Args:
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await payment_methods.list_payment_methods(
                filter_str=filter or None,
            ),
            "PaymentMethod",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_payment_methods")


@tool(title="Get payment method", annotations=_READONLY)
async def netlicensing_get_payment_method(
    payment_method_number: str, include_raw: bool = False
) -> str:
    """Get details of a specific payment method.

    Args:
        payment_method_number: Payment method identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await payment_methods.get_payment_method(payment_method_number),
            "PaymentMethod",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_payment_method")


@tool(title="Preview update of payment method", annotations=_READONLY)
async def netlicensing_preview_update_payment_method(
    payment_method_number: str,
    active: bool | None = None,
) -> str:
    """Preview a sensitive payment method update (active state change).

    Returns a diff and a confirmation token. Pass the token to
    netlicensing_update_payment_method within 5 minutes to apply.

    Args:
        payment_method_number: Payment method to preview changes for
        active: Proposed new active state (omit to skip)
    """
    try:
        current_resp = await payment_methods.get_payment_method(payment_method_number)
        current = _extract_props(current_resp)
        diff: list[dict] = []
        if active is not None:
            diff.append(
                {
                    "field": "active",
                    "from": current.get("active"),
                    "to": str(active).lower(),
                }
            )
        return _json(
            safety.make_update_preview("update_payment_method", payment_method_number, diff)
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_update_payment_method")


@tool(title="Update payment method", annotations=_UPDATE)
async def netlicensing_update_payment_method(
    payment_method_number: str,
    active: bool | None = None,
    paypal_subject: str = "",
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update a payment method's configuration.

    Changing the active state requires a confirmation token. Call
    netlicensing_preview_update_payment_method first.

    Args:
        payment_method_number: Payment method to update
        active: Enable or disable the payment method
        paypal_subject: PayPal account e-mail address
        confirm_token: Confirmation token (required when active changes)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        if active is not None:
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_payment_method", payment_method_number
                )
            else:
                current_resp = await payment_methods.get_payment_method(payment_method_number)
                current = _extract_props(current_resp)
                diff: list[dict] = [
                    {
                        "field": "active",
                        "from": current.get("active"),
                        "to": str(active).lower(),
                    }
                ]
                return _json(
                    safety.make_update_preview("update_payment_method", payment_method_number, diff)
                )

        return _wrap_json(
            await payment_methods.update_payment_method(
                payment_method_number,
                active=active,
                paypal_subject=paypal_subject or None,
            ),
            "PaymentMethod",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_update_payment_method")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_payment_method")
