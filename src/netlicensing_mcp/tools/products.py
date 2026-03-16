"""Tools: Products — CRUD for NetLicensing product objects."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_products() -> dict:
    """List all products in the account."""
    return await nl_get("/product")


async def get_product(product_number: str) -> dict:
    """Get a single product by its number."""
    return await nl_get(f"/product/{product_number}")


async def create_product(
    number: str,
    name: str,
    active: bool = True,
    version: str = "1.0",
    description: str = "",
    licensing_info: str = "",
) -> dict:
    """Create a new product."""
    data: dict[str, str] = {
        "number": number,
        "name": name,
        "active": str(active).lower(),
        "version": version,
    }
    if description:
        data["description"] = description
    if licensing_info:
        data["licensingInfo"] = licensing_info
    return await nl_post("/product", data)


async def update_product(
    product_number: str,
    name: str | None = None,
    active: bool | None = None,
    version: str | None = None,
    description: str | None = None,
) -> dict:
    """Update fields of an existing product."""
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if version is not None:
        data["version"] = version
    if description is not None:
        data["description"] = description
    return await nl_put(f"/product/{product_number}", data)


async def delete_product(product_number: str) -> str:
    """Delete a product. Returns confirmation message."""
    status = await nl_delete(f"/product/{product_number}")
    return f"Product {product_number} deleted (HTTP {status})."
