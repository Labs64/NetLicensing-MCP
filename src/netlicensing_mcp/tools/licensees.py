"""Tools: Licensees — customers who hold licenses."""

from __future__ import annotations

from netlicensing_mcp.tools.helpers import scoped_filter
from netlicensing_mcp.client import NetLicensingError, nl_delete, nl_get, nl_post


async def list_licensees(
    product_number: str,
    filter_str: str | None = None,
    page: int | None = None,
    items_per_page: int | None = None,
) -> dict:
    """List all licensees (customers) for a product.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    page / items_per_page: optional paging. All criteria (including
        productNumber) go into the ``filter`` query parameter using the
        semicolon-separated format required by the NetLicensing API for
        scoping, pagination and total-item counts — a bare
        query parameter is ignored by the API
        (e.g. ``filter=productNumber=P001;page=0;items=100``).
    """
    return await nl_get(
        "/licensee",
        scoped_filter("productNumber", product_number, filter_str, page, items_per_page),
    )


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
    dry_run: bool = False,
) -> dict:
    """
    Validate a licensee's licenses across all product modules.

    Returns per-module validity, type, expiry, and usage information.

    One call addresses at most **one** module with module-scoped parameters.
    Those are sent in the indexed form the reference client
    (NetLicensingClient-java) uses — ``productModuleNumber0``, ``sessionId0``,
    ``action0``, ``nodeSecret0`` — while global parameters (``productNumber``,
    ``licenseeName``, ``dryRun``) stay unindexed.

    Parameters:
      product_number: scope validation to a specific product.
      licensee_name: human-readable name for auto-created licensees.
      product_module_number: module that session_id / action / node_secret
          apply to; required when any of them is given.
      node_secret: for Node-Locked model — unique device secret.
      session_id: for Floating model — unique session identifier; required
          with action.
      action: for Floating model — 'checkOut' or 'checkIn'.
      dry_run: when True, sends dryRun=true so the call has no side effects
               (never checks out, checks in or consumes anything).
    """
    # The API applies sessionId / action / nodeSecret to the module named by
    # productModuleNumber and silently ignores them otherwise — fail loudly.
    module_params = [
        n
        for n, v in (("session_id", session_id), ("action", action), ("node_secret", node_secret))
        if v
    ]
    if module_params and not product_module_number:
        raise NetLicensingError(
            400,
            f"{', '.join(module_params)} requires product_module_number "
            "(the module these parameters apply to)",
        )
    if action and action not in ("checkOut", "checkIn"):
        raise NetLicensingError(400, "action must be 'checkOut' or 'checkIn'")
    if action and not session_id:
        raise NetLicensingError(
            400,
            f"action '{action}' requires session_id (the Floating session to "
            f"{'check out' if action == 'checkOut' else 'check in'})",
        )
    data: dict[str, str] = {}
    if product_number:
        data["productNumber"] = product_number
    if licensee_name:
        data["licenseeName"] = licensee_name
    if product_module_number:
        # Indexed per-module parameters, exactly as ValidationService in the
        # Java reference client sends them.
        data["productModuleNumber0"] = product_module_number
        if node_secret:
            data["nodeSecret0"] = node_secret
        if session_id:
            data["sessionId0"] = session_id
        if action:
            data["action0"] = action
    if dry_run:
        data["dryRun"] = "true"
    return await nl_post(f"/licensee/{licensee_number}/validate", data)


async def transfer_licenses(
    from_licensee_number: str,
    to_licensee_number: str,
) -> dict:
    """Transfer all licenses from one licensee to another.

    The API answers ``204 No Content`` on success. The source licensee must be
    marked for transfer and both licensees must be active.
    """
    await nl_post(
        f"/licensee/{to_licensee_number}/transfer",
        {"sourceLicenseeNumber": from_licensee_number},
    )
    return {
        "transferred": True,
        "from_licensee_number": from_licensee_number,
        "to_licensee_number": to_licensee_number,
        "detail": (
            f"All licenses moved from {from_licensee_number} to {to_licensee_number}. "
            f"Call netlicensing_list_licenses on {to_licensee_number} to see them."
        ),
    }
