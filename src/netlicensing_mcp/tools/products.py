"""Tools: Products — CRUD for NetLicensing product objects."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_products(filter_str: str | None = None) -> dict:
    """List all products in the account.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return await nl_get("/product", params or None)


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
    licensee_auto_create: bool | None = None,
    vat_mode: str | None = None,
    licensee_secret_mode: str | None = None,
) -> dict:
    """
    Create a new product.

    vat_mode: GROSS | NET
    licensee_auto_create: if true, non-existing licensees are created on first validation.
    licensee_secret_mode: DISABLED | PREDEFINED | CLIENT
    """
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
    if licensee_auto_create is not None:
        data["licenseeAutoCreate"] = str(licensee_auto_create).lower()
    if vat_mode:
        data["vatMode"] = vat_mode
    if licensee_secret_mode:
        data["licenseeSecretMode"] = licensee_secret_mode
    return await nl_post("/product", data)


async def update_product(
    product_number: str,
    name: str | None = None,
    active: bool | None = None,
    version: str | None = None,
    description: str | None = None,
    licensing_info: str | None = None,
    licensee_auto_create: bool | None = None,
    vat_mode: str | None = None,
    licensee_secret_mode: str | None = None,
) -> dict:
    """Update fields of an existing product.

    licensee_secret_mode: DISABLED | PREDEFINED | CLIENT
    """
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if version is not None:
        data["version"] = version
    if description is not None:
        data["description"] = description
    if licensing_info is not None:
        data["licensingInfo"] = licensing_info
    if licensee_auto_create is not None:
        data["licenseeAutoCreate"] = str(licensee_auto_create).lower()
    if vat_mode is not None:
        data["vatMode"] = vat_mode
    if licensee_secret_mode is not None:
        data["licenseeSecretMode"] = licensee_secret_mode
    return await nl_post(f"/product/{product_number}", data)


async def delete_product(product_number: str, force_cascade: bool = False) -> str:
    """Delete a product. Returns confirmation message."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/product/{product_number}", params or None)
    return f"Product {product_number} deleted (HTTP {status})."
