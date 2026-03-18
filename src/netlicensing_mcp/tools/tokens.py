"""Tools: Tokens — shop URLs and API access tokens."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_tokens(filter_str: str | None = None) -> dict:
    """List all active tokens in the account.

    filter_str: optional server-side filter expression (e.g. 'tokenType=SHOP').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/token", params or None)


async def get_token(token_number: str) -> dict:
    """Get details of a specific token."""
    return await nl_get(f"/token/{token_number}")


async def create_shop_token(
    licensee_number: str,
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

    product_number: scope shop to a specific product.
    license_template_number: pre-select a specific license template.
    success_url / cancel_url: redirect URLs after checkout.
    """
    data: dict[str, str] = {
        "tokenType": "SHOP",
        "licenseeNumber": licensee_number,
    }
    if product_number:
        data["productNumber"] = product_number
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
    data: dict[str, str] = {
        "tokenType": "APIKEY",
        "apiKeyRole": api_key_role,
    }
    if licensee_number:
        data["licenseeNumber"] = licensee_number
    return await nl_post("/token", data)


async def delete_token(token_number: str) -> str:
    """Revoke / delete a token."""
    status = await nl_delete(f"/token/{token_number}")
    return f"Token {token_number} deleted (HTTP {status})."
