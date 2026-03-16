"""Tools: Tokens — shop URLs and API access tokens."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_tokens() -> dict:
    """List all active tokens in the account."""
    return await nl_get("/token")


async def get_token(token_number: str) -> dict:
    """Get details of a specific token."""
    return await nl_get(f"/token/{token_number}")


async def create_shop_token(
    licensee_number: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
    success_url_title: str | None = None,
    cancel_url_title: str | None = None,
) -> dict:
    """
    Generate a NetLicensing Shop one-time checkout URL for a customer.
    Returns a token containing the shopURL property.
    """
    data: dict[str, str] = {
        "tokenType": "SHOP",
        "licenseeNumber": licensee_number,
    }
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
    role: str = "ROLE_APIKEY_LICENSEE",
    licensee_number: str | None = None,
) -> dict:
    """
    Create a scoped API token.

    role options:
      ROLE_APIKEY_LICENSEE      – read-only licensee-scoped access
      ROLE_APIKEY_ANALYTICS     – analytics read access
      ROLE_APIKEY_OPERATION     – validate + shop token creation only
      ROLE_APIKEY_MAINTENANCE   – full CRUD except account management
    """
    data: dict[str, str] = {
        "tokenType": "APIKEY",
        "role": role,
    }
    if licensee_number:
        data["licenseeNumber"] = licensee_number
    return await nl_post("/token", data)


async def delete_token(token_number: str) -> str:
    """Revoke / delete a token."""
    status = await nl_delete(f"/token/{token_number}")
    return f"Token {token_number} deleted (HTTP {status})."
