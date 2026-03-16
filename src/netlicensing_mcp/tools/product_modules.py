"""Tools: Product Modules — licensing feature groups within a product."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_product_modules(product_number: str) -> dict:
    """List all modules for a product."""
    return await nl_get("/productmodule", {"productNumber": product_number})


async def get_product_module(module_number: str) -> dict:
    """Get a specific product module by its number."""
    return await nl_get(f"/productmodule/{module_number}")


async def create_product_module(
    product_number: str,
    number: str,
    name: str,
    licensing_model: str,
    active: bool = True,
) -> dict:
    """
    Create a product module with the specified licensing model.

    Common licensing_model values:
      TryAndBuy, Subscription, Rental, Floating, MultiFeature,
      PayPerUse, PricingTable, Quota, NodeLocked
    """
    return await nl_post(
        "/productmodule",
        {
            "productNumber": product_number,
            "number": number,
            "name": name,
            "licensingModel": licensing_model,
            "active": str(active).lower(),
        },
    )


async def update_product_module(
    module_number: str,
    name: str | None = None,
    active: bool | None = None,
) -> dict:
    """Update a product module's name or active state."""
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    return await nl_put(f"/productmodule/{module_number}", data)


async def delete_product_module(module_number: str) -> str:
    """Delete a product module."""
    status = await nl_delete(f"/productmodule/{module_number}")
    return f"Module {module_number} deleted (HTTP {status})."
