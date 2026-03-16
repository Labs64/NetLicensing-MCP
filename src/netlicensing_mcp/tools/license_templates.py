"""Tools: License Templates — define what licenses look like within a module."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post, nl_put


async def list_license_templates(module_number: str) -> dict:
    """List all license templates for a product module."""
    return await nl_get("/licensetemplate", {"productModuleNumber": module_number})


async def get_license_template(template_number: str) -> dict:
    """Get a specific license template."""
    return await nl_get(f"/licensetemplate/{template_number}")


async def create_license_template(
    module_number: str,
    number: str,
    name: str,
    license_type: str,
    active: bool = True,
    price: float | None = None,
    currency: str = "EUR",
    automatic: bool = False,
    hidden: bool = False,
    **extra_props: str,
) -> dict:
    """
    Create a license template.

    license_type values: FEATURE, TIMEVOLUME, FLOATING, QUANTITY
    extra_props: model-specific props e.g. timeVolume="30", timeVolumePeriod="DAY"
    """
    data: dict[str, str] = {
        "productModuleNumber": module_number,
        "number": number,
        "name": name,
        "licenseType": license_type,
        "active": str(active).lower(),
        "automatic": str(automatic).lower(),
        "hidden": str(hidden).lower(),
        "currency": currency,
    }
    if price is not None:
        data["price"] = str(price)
    data.update(extra_props)
    return await nl_post("/licensetemplate", data)


async def update_license_template(
    template_number: str,
    name: str | None = None,
    active: bool | None = None,
    price: float | None = None,
) -> dict:
    """Update a license template."""
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if price is not None:
        data["price"] = str(price)
    return await nl_put(f"/licensetemplate/{template_number}", data)


async def delete_license_template(template_number: str) -> str:
    """Delete a license template."""
    status = await nl_delete(f"/licensetemplate/{template_number}")
    return f"Template {template_number} deleted (HTTP {status})."
