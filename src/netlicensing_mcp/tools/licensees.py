"""Tools: Licensees — customers who hold licenses."""

from __future__ import annotations

from typing import Optional

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_licensees(product_number: str) -> dict:
    """List all licensees (customers) for a product."""
    return await nl_get("/licensee", {"productNumber": product_number})


async def get_licensee(licensee_number: str) -> dict:
    """Get a specific licensee by number."""
    return await nl_get(f"/licensee/{licensee_number}")


async def create_licensee(
    product_number: str,
    number: Optional[str] = None,
    name: Optional[str] = None,
    active: bool = True,
    **custom_props: str,
) -> dict:
    """
    Create a new licensee (customer) under a product.
    Pass arbitrary custom_props as extra keyword arguments.
    """
    data: dict[str, str] = {
        "productNumber": product_number,
        "active": str(active).lower(),
    }
    if number:
        data["number"] = number
    if name:
        data["name"] = name
    data.update(custom_props)
    return await nl_post("/licensee", data)


async def update_licensee(
    licensee_number: str,
    name: Optional[str] = None,
    active: Optional[bool] = None,
) -> dict:
    """Update a licensee's name or active status."""
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    return await nl_put(f"/licensee/{licensee_number}", data)


async def delete_licensee(licensee_number: str) -> str:
    """Delete a licensee and all their licenses."""
    status = await nl_delete(f"/licensee/{licensee_number}")
    return f"Licensee {licensee_number} deleted (HTTP {status})."


async def validate_licensee(
    licensee_number: str,
    product_number: Optional[str] = None,
    license_name: Optional[str] = None,
) -> dict:
    """
    Validate a licensee's licenses across all product modules.

    Returns per-module validity, type, expiry, and usage information.
    Optionally scope by product_number or a specific license_name.
    """
    data: dict[str, str] = {}
    if product_number:
        data["productNumber"] = product_number
    if license_name:
        data["licenseName"] = license_name
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


def audit_all_customers(customers):
    """
    Audit all NetLicensing customers and print summary.
    customers: list of dicts, each representing a customer/licensee
    """
    for customer in customers:
        number = customer.get("number")
        name = customer.get("name")
        active = customer.get("active")
        product_number = customer.get("productNumber")
        warning_summary = customer.get("warningLevelSummary")
        print(
            f"Customer: {name} (#{number}) | Product: {product_number} | Active: {active} | Warnings: {warning_summary}"
        )
