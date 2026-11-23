"""Tools: Tokens — shop URLs and API access tokens."""

from __future__ import annotations

from netlicensing_mcp.tools.helpers import (
    API_KEY_ROLES,
    delete_result,
    require_one_of,
    require_plain_text,
    require_redirect_url,
)
from netlicensing_mcp.client import ClientValidationError, nl_delete, nl_get, nl_post
from netlicensing_mcp.redaction import mask_token_number


async def list_tokens(filter_str: str | None = None) -> dict:
    """List all active tokens in the account.

    filter_str: optional server-side filter expression (e.g. 'tokenType=SHOP').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/token", params or None)


_MAX_TOKEN_PAGES = 50


async def resolve_token_number(token_number: str) -> str:
    """Return the real token number for *token_number*, which may be a masked one.

    ``list_tokens`` shows token numbers masked (``aac****534c``). A masked value
    (it contains ``****``) is matched against the real tokens by the same mask and
    must identify exactly one; anything else is returned unchanged. The real number
    is only used inside the server, never shown.
    """
    if "****" not in token_number:
        return token_number
    matches: list[str] = []
    for page in range(_MAX_TOKEN_PAGES):
        resp = await nl_get("/token", {"filter": f"page={page};items=100"})
        items_obj = resp.get("items")
        items = items_obj.get("item", []) if isinstance(items_obj, dict) else []
        for item in items:
            for prop in item.get("property", []) if isinstance(item, dict) else []:
                if isinstance(prop, dict) and prop.get("name") == "number":
                    real = str(prop.get("value", ""))
                    if mask_token_number(real) == token_number:
                        matches.append(real)
        if not items or not (isinstance(items_obj, dict) and _has_next(items_obj)):
            break
    if not matches:
        raise ClientValidationError(
            f"No token matches the masked number {token_number!r}. List tokens again."
        )
    if len(matches) > 1:
        raise ClientValidationError(
            f"The masked number {token_number!r} matches {len(matches)} tokens: it is "
            "ambiguous, so nothing was done. Use the full token number.",
        )
    return matches[0]


def _has_next(items_obj: dict) -> bool:
    return str(items_obj.get("hasnext", "")).strip().lower() == "true"


async def get_token(token_number: str) -> dict:
    """Get details of a specific token (a masked number from the token list is accepted)."""
    return await nl_get(f"/token/{await resolve_token_number(token_number)}")


async def create_shop_token(
    licensee_number: str | None,
    product_number: str | None = None,
    license_template_number: str | None = None,
    success_url: str | None = None,
    cancel_url: str | None = None,
    success_url_title: str | None = None,
    cancel_url_title: str | None = None,
) -> dict:
    """
    Generate a NetLicensing Shop one-time checkout URL for a customer.
    Returns a token containing the shopURL property.

    product_number: only used when *licensee_number* is empty. The API takes
        the product from the licensee and rejects both together ("not allowed
        simultaneously"), so it is dropped when a licensee is given.
    license_template_number: pre-select a specific license template.
    success_url / cancel_url: redirect URLs after checkout.
    """
    require_redirect_url("success_url", success_url)
    require_redirect_url("cancel_url", cancel_url)
    require_plain_text("success_url_title", success_url_title)
    require_plain_text("cancel_url_title", cancel_url_title)
    data: dict[str, str] = {"tokenType": "SHOP"}
    if licensee_number:
        data["licenseeNumber"] = licensee_number
    elif product_number:
        data["productNumber"] = product_number
    else:
        raise ClientValidationError("Either licensee_number or product_number is required")
    if license_template_number:
        data["licenseTemplateNumber"] = license_template_number
    if success_url:
        data["successURL"] = success_url
    if cancel_url:
        data["cancelURL"] = cancel_url
    if success_url_title:
        data["successURLTitle"] = success_url_title
    if cancel_url_title:
        data["cancelURLTitle"] = cancel_url_title
    return await nl_post("/token", data)


async def create_api_token(
    api_key_role: str = "ROLE_APIKEY_LICENSEE",
    licensee_number: str | None = None,
) -> dict:
    """
    Create a scoped API token.

    api_key_role options:
      ROLE_APIKEY_LICENSEE      – read-only licensee-scoped access
      ROLE_APIKEY_ANALYTICS     – analytics read access
      ROLE_APIKEY_OPERATION     – validate + shop token creation only
      ROLE_APIKEY_MAINTENANCE   – full CRUD except account management
      ROLE_APIKEY_ADMIN         – full admin access
    """
    require_one_of("api_key_role", api_key_role, API_KEY_ROLES)
    data: dict[str, str] = {
        "tokenType": "APIKEY",
        "apiKeyRole": api_key_role,
    }
    if licensee_number:
        data["licenseeNumber"] = licensee_number
    return await nl_post("/token", data)


async def delete_token(token_number: str) -> str:
    """Revoke / delete a token.

    The message masks the number: for APIKEY and SHOP tokens it is the credential.
    """
    status = await nl_delete(f"/token/{token_number}")
    return delete_result("delete_token", "Token", mask_token_number(token_number), status)
