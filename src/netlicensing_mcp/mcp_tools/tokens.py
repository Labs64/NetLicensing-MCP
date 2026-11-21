"""MCP tools for Tokens."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _WRITE,
    _error,
    _extract_props,
    _json,
    _scrub_apikey_console_url,
    _wrap_json_token_read,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.redaction import tag_one_time_display
from netlicensing_mcp.responses import wrap
from netlicensing_mcp.tools import tokens


@tool(title="List tokens", annotations=_READONLY)
async def netlicensing_list_tokens(filter: str = "", include_raw: bool = False) -> str:
    """List all active tokens in the account.

    Args:
        filter: Optional server-side filter expression (e.g. 'tokenType=SHOP')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json_token_read(
            await tokens.list_tokens(filter_str=filter or None),
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Get token", annotations=_READONLY)
async def netlicensing_get_token(token_number: str, include_raw: bool = False) -> str:
    """Get details of a specific token.

    Args:
        token_number: Token identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json_token_read(
            await tokens.get_token(token_number),
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Create shop token", annotations=_WRITE)
async def netlicensing_create_shop_token(
    licensee_number: str = "",
    product_number: str = "",
    license_template_number: str = "",
    success_url: str = "",
    cancel_url: str = "",
    success_url_title: str = "",
    cancel_url_title: str = "",
    include_raw: bool = False,
) -> str:
    """Generate a NetLicensing Shop one-time checkout URL for a customer.

    Args:
        licensee_number: Customer to generate the shop URL for (the product is
            taken from the licensee)
        product_number: Only used when licensee_number is not given; ignored
            otherwise, since NetLicensing rejects both together
        license_template_number: Optional — pre-select a specific license template
        success_url: Optional URL to redirect to after successful purchase
        cancel_url: Optional URL to redirect to if customer cancels
        success_url_title: Optional button/link label for success redirect
        cancel_url_title: Optional button/link label for cancel redirect
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        raw = await tokens.create_shop_token(
            licensee_number or None,
            product_number=product_number or None,
            license_template_number=license_template_number or None,
            success_url=success_url or None,
            cancel_url=cancel_url or None,
            success_url_title=success_url_title or None,
            cancel_url_title=cancel_url_title or None,
        )
        wrapped = wrap(raw, "Token", raw=raw if include_raw else None)
        _scrub_apikey_console_url(wrapped)
        return _json(tag_one_time_display(wrapped))
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Create api token", annotations=_WRITE)
async def netlicensing_create_api_token(
    api_key_role: str = "ROLE_APIKEY_LICENSEE",
    licensee_number: str = "",
    include_raw: bool = False,
) -> str:
    """Create a scoped API token.

    Args:
        api_key_role: ROLE_APIKEY_LICENSEE | ROLE_APIKEY_ANALYTICS |
              ROLE_APIKEY_OPERATION | ROLE_APIKEY_MAINTENANCE | ROLE_APIKEY_ADMIN
        licensee_number: Optional — scope token to a specific licensee
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        raw = await tokens.create_api_token(api_key_role, licensee_number or None)
        wrapped = wrap(raw, "Token", raw=raw if include_raw else None)
        _scrub_apikey_console_url(wrapped)
        return _json(tag_one_time_display(wrapped))
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Preview deletion of token", annotations=_READONLY)
async def netlicensing_preview_delete_token(token_number: str) -> str:
    """Preview what would be revoked when deleting a token.

    For APIKEY tokens this is always required before deletion.
    Returns token kind, role, and a confirmation token.

    Args:
        token_number: Token to preview deletion for
    """
    try:
        token_resp = await tokens.get_token(token_number)
        props = _extract_props(token_resp)
        return _json(
            safety.make_delete_preview(
                "delete_token",
                token_number,
                affected={
                    "token_type": props.get("tokenType", "UNKNOWN"),
                    "role": props.get("role", ""),
                },
                samples={},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@tool(title="Delete token", annotations=_DELETE)
async def netlicensing_delete_token(
    token_number: str,
    confirm_token: str = "",
) -> str:
    """Revoke an API or shop token.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_token)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        token_number: Token to revoke
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_token", token_number)
            return await tokens.delete_token(token_number)

        # No token — always show preview; deletion is never allowed without confirmation.
        token_resp = await tokens.get_token(token_number)
        props = _extract_props(token_resp)
        return _json(
            safety.make_delete_preview(
                "delete_token",
                token_number,
                affected={
                    "token_type": props.get("tokenType", "UNKNOWN"),
                    "role": props.get("role", ""),
                },
                samples={},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)
