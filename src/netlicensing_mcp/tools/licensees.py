"""Tools: Licensees — customers who hold licenses."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_licensees(
    product_number: str,
    filter_str: str | None = None,
) -> dict:
    """List all licensees (customers) for a product.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {"productNumber": product_number}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/licensee", params)


async def get_licensee(licensee_number: str) -> dict:
    """Get a specific licensee by number."""
    return await nl_get(f"/licensee/{licensee_number}")


async def create_licensee(
    product_number: str,
    number: str | None = None,
    name: str | None = None,
    active: bool = True,
    marked_for_transfer: bool | None = None,
    licensee_secret: str | None = None,
) -> dict:
    """
    Create a new licensee (customer) under a product.

    marked_for_transfer: if true, marks the licensee for license transfer.
    licensee_secret: secret string for licensee identification (when product
        licenseeSecretMode is PREDEFINED).
    """
    data: dict[str, str] = {
        "productNumber": product_number,
        "active": str(active).lower(),
    }
    if number:
        data["number"] = number
    if name:
        data["name"] = name
    if marked_for_transfer is not None:
        data["markedForTransfer"] = str(marked_for_transfer).lower()
    if licensee_secret is not None:
        data["licenseeSecret"] = licensee_secret
    return await nl_post("/licensee", data)


async def update_licensee(
    licensee_number: str,
    name: str | None = None,
    active: bool | None = None,
    marked_for_transfer: bool | None = None,
    licensee_secret: str | None = None,
) -> dict:
    """Update a licensee's properties.

    licensee_secret: secret string for licensee identification (when product
        licenseeSecretMode is PREDEFINED).
    """
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if marked_for_transfer is not None:
        data["markedForTransfer"] = str(marked_for_transfer).lower()
    if licensee_secret is not None:
        data["licenseeSecret"] = licensee_secret
    return await nl_post(f"/licensee/{licensee_number}", data)


async def delete_licensee(licensee_number: str, force_cascade: bool = False) -> str:
    """Delete a licensee and all their licenses."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/licensee/{licensee_number}", params or None)
    return f"Licensee {licensee_number} deleted (HTTP {status})."


async def validate_licensee(
    licensee_number: str,
    product_number: str | None = None,
    licensee_name: str | None = None,
    product_module_number: str | None = None,
    node_secret: str | None = None,
    session_id: str | None = None,
    action: str | None = None,
) -> dict:
    """
    Validate a licensee's licenses across all product modules.

    Returns per-module validity, type, expiry, and usage information.

    Parameters:
      product_number: scope validation to a specific product.
      licensee_name: human-readable name for auto-created licensees.
      product_module_number: for Node-Locked model — target module.
      node_secret: for Node-Locked model — unique device secret.
      session_id: for Floating model — unique session identifier.
      action: for Floating model — 'checkOut' or 'checkIn'.
    """
    data: dict[str, str] = {}
    if product_number:
        data["productNumber"] = product_number
    if licensee_name:
        data["licenseeName"] = licensee_name
    if product_module_number:
        data["productModuleNumber"] = product_module_number
    if node_secret:
        data["nodeSecret"] = node_secret
    if session_id:
        data["sessionId"] = session_id
    if action:
        data["action"] = action
    return await nl_post(f"/licensee/{licensee_number}/validate", data)


async def transfer_licenses(
    from_licensee_number: str,
    to_licensee_number: str,
) -> dict:
    """Transfer all licenses from one licensee to another."""
    return await nl_post(
        f"/licensee/{to_licensee_number}/transfer",
        {"sourceLicenseeNumber": from_licensee_number},
    )
