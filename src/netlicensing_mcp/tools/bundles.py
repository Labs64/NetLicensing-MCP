"""Tools: Bundles — CRUD and obtain for NetLicensing bundle objects."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post


async def list_bundles() -> dict:
    """List all bundles in the account."""
    return await nl_get("/bundle")


async def get_bundle(bundle_number: str) -> dict:
    """Get a single bundle by its number."""
    return await nl_get(f"/bundle/{bundle_number}")


async def create_bundle(
    number: str,
    name: str,
    license_template_numbers: list[str],
    active: bool = True,
    price: float | None = None,
    currency: str | None = None,
    description: str = "",
) -> dict:
    """
    Create a new bundle.

    license_template_numbers: list of license template numbers included in the bundle.
    price: bundle price (optional).
    currency: ISO 4217 currency code (e.g. EUR, USD).
    """
    data: dict[str, str] = {
        "number": number,
        "name": name,
        "active": str(active).lower(),
    }
    if license_template_numbers:
        data["licenseTemplateNumber"] = ",".join(license_template_numbers)
    if description:
        data["description"] = description
    if price is not None:
        data["price"] = str(price)
    if currency:
        data["currency"] = currency
    return await nl_post("/bundle", data)


async def update_bundle(
    bundle_number: str,
    name: str | None = None,
    active: bool | None = None,
    license_template_numbers: list[str] | None = None,
    price: float | None = None,
    currency: str | None = None,
    description: str | None = None,
) -> dict:
    """Update fields of an existing bundle."""
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if license_template_numbers is not None:
        data["licenseTemplateNumber"] = ",".join(license_template_numbers)
    if price is not None:
        data["price"] = str(price)
    if currency is not None:
        data["currency"] = currency
    if description is not None:
        data["description"] = description
    return await nl_post(f"/bundle/{bundle_number}", data)


async def delete_bundle(bundle_number: str, force_cascade: bool = False) -> str:
    """Delete a bundle. Returns confirmation message."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/bundle/{bundle_number}", params or None)
    return f"Bundle {bundle_number} deleted (HTTP {status})."


async def obtain_bundle(
    bundle_number: str,
    licensee_number: str,
) -> dict:
    """
    Obtain a bundle for a licensee — creates licenses from all
    license templates included in the bundle.
    """
    data: dict[str, str] = {
        "licenseeNumber": licensee_number,
    }
    return await nl_post(f"/bundle/{bundle_number}/obtain", data)
