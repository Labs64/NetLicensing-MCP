"""Tools: Product Modules — licensing feature groups within a product."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_product_modules(
    product_number: str,
    filter_str: str | None = None,
    page: int | None = None,
    items_per_page: int | None = None,
) -> dict:
    """List all modules for a product.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    page / items_per_page: when provided, embeds all criteria (including
        productNumber) into the ``filter`` query parameter using the
        semicolon-separated format required by the NetLicensing API for
        accurate pagination and total-item counts
        (e.g. ``filter=productNumber=P001;page=0;items=1``).
    """
    if page is not None or items_per_page is not None:
        parts = [f"productNumber={product_number}"]
        if page is not None:
            parts.append(f"page={page}")
        if items_per_page is not None:
            parts.append(f"items={items_per_page}")
        if filter_str:
            parts.append(filter_str)
        return await nl_get("/productmodule", {"filter": ";".join(parts)})
    params: dict[str, str] = {"productNumber": product_number}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/productmodule", params)


async def get_product_module(module_number: str) -> dict:
    """Get a specific product module by its number."""
    return await nl_get(f"/productmodule/{module_number}")


async def create_product_module(
    product_number: str,
    number: str,
    name: str,
    licensing_model: str,
    active: bool = True,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str | None = None,
    custom_properties: dict[str, str] | None = None,
) -> dict:
    """
    Create a product module with the specified licensing model.

    licensing_model values:
      TryAndBuy, Subscription, Rental, Floating, MultiFeature,
      PayPerUse, PricingTable, Quota, NodeLocked

    Model-specific parameters:
      max_checkout_validity: Maximum checkout validity in days (Floating).
      yellow_threshold: Remaining time volume for yellow level (Rental).
      red_threshold: Remaining time volume for red level (Rental).
      node_secret_mode: PREDEFINED | CLIENT (NodeLocked).

    custom_properties: Optional dict of additional properties (e.g., skudef for PricingTable).
    """
    data: dict[str, str] = {
        "productNumber": product_number,
        "number": number,
        "name": name,
        "licensingModel": licensing_model,
        "active": str(active).lower(),
    }
    if max_checkout_validity is not None:
        data["maxCheckoutValidity"] = str(max_checkout_validity)
    if yellow_threshold is not None:
        data["yellowThreshold"] = str(yellow_threshold)
    if red_threshold is not None:
        data["redThreshold"] = str(red_threshold)
    if node_secret_mode:
        data["nodeSecretMode"] = node_secret_mode
    if custom_properties:
        data.update(custom_properties)
    return await nl_post("/productmodule", data)


async def update_product_module(
    module_number: str,
    name: str | None = None,
    active: bool | None = None,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str | None = None,
    custom_properties: dict[str, str] | None = None,
) -> dict:
    """Update a product module's properties.

    Model-specific parameters:
      max_checkout_validity: Maximum checkout validity in days (Floating).
      yellow_threshold: Remaining time volume for yellow level (Rental).
      red_threshold: Remaining time volume for red level (Rental).
      node_secret_mode: PREDEFINED | CLIENT (NodeLocked).

    custom_properties: Optional dict of additional properties to set or update.
    """
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if max_checkout_validity is not None:
        data["maxCheckoutValidity"] = str(max_checkout_validity)
    if yellow_threshold is not None:
        data["yellowThreshold"] = str(yellow_threshold)
    if red_threshold is not None:
        data["redThreshold"] = str(red_threshold)
    if node_secret_mode is not None:
        data["nodeSecretMode"] = node_secret_mode
    if custom_properties:
        data.update(custom_properties)
    return await nl_post(f"/productmodule/{module_number}", data)


async def delete_product_module(module_number: str, force_cascade: bool = False) -> str:
    """Delete a product module."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/productmodule/{module_number}", params or None)
    return f"Module {module_number} deleted (HTTP {status})."
