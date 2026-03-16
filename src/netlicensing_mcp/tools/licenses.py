"""Tools: Licenses — individual license records assigned to licensees."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_licenses(licensee_number: str) -> dict:
    """List all licenses for a specific licensee."""
    return await nl_get("/license", {"licenseeNumber": licensee_number})


async def get_license(license_number: str) -> dict:
    """Get details of a specific license."""
    return await nl_get(f"/license/{license_number}")


async def create_license(
    licensee_number: str,
    license_template_number: str,
    number: str | None = None,
    active: bool = True,
    **custom_props: str,
) -> dict:
    """
    Create a license for a licensee from a license template.
    custom_props: e.g. startDate="2025-01-01T00:00:00.000Z"
    """
    data: dict[str, str] = {
        "licenseeNumber": licensee_number,
        "licenseTemplateNumber": license_template_number,
        "active": str(active).lower(),
    }
    if number:
        data["number"] = number
    data.update(custom_props)
    return await nl_post("/license", data)


async def update_license(
    license_number: str,
    active: bool | None = None,
    **custom_props: str,
) -> dict:
    """Activate, deactivate, or update custom properties of a license."""
    data: dict[str, str] = {}
    if active is not None:
        data["active"] = str(active).lower()
    data.update(custom_props)
    return await nl_put(f"/license/{license_number}", data)


async def delete_license(license_number: str) -> str:
    """Delete a license."""
    status = await nl_delete(f"/license/{license_number}")
    return f"License {license_number} deleted (HTTP {status})."
