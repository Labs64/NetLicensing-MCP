"""Tools: Bundles — CRUD and obtain for NetLicensing bundle objects."""

from __future__ import annotations

from netlicensing_mcp.client import nl_delete, nl_get, nl_post
from netlicensing_mcp.tools.helpers import delete_result, first_item_property, strip_output_fields


async def list_bundles(filter_str: str | None = None) -> dict:
    """List all bundles in the account.

    filter_str: optional server-side filter expression (e.g. 'active=true').
    """
    params: dict[str, str] = {}
    if filter_str:
        params["filter"] = filter_str
    return strip_output_fields(await nl_get("/bundle", params or None))


async def get_bundle(bundle_number: str) -> dict:
    """Get a single bundle by its number."""
    return strip_output_fields(await nl_get(f"/bundle/{bundle_number}"))


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

    Note: 'logo' is intentionally not passed — omitting it avoids accidentally
    clearing an existing bundle logo on the NetLicensing server.
    """
    data: dict[str, str] = {
        "number": number,
        "name": name,
        "active": str(active).lower(),
    }
    if license_template_numbers:
        data["licenseTemplateNumbers"] = ",".join(license_template_numbers)
    if description:
        data["description"] = description
    if price is not None:
        data["price"] = str(price)
    if currency:
        data["currency"] = currency
    return strip_output_fields(await nl_post("/bundle", data))


async def update_bundle(
    bundle_number: str,
    name: str | None = None,
    active: bool | None = None,
    license_template_numbers: list[str] | None = None,
    price: float | None = None,
    currency: str | None = None,
    description: str | None = None,
) -> dict:
    """Update fields of an existing bundle.

    Note: 'logo' is intentionally not passed — omitting it preserves the
    existing bundle logo on the NetLicensing server. A new price without a
    currency keeps the bundle's current currency.
    """
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if active is not None:
        data["active"] = str(active).lower()
    if license_template_numbers is not None:
        data["licenseTemplateNumbers"] = ",".join(license_template_numbers)
    if price is not None:
        data["price"] = str(price)
    if currency is not None:
        data["currency"] = currency
    if description is not None:
        data["description"] = description
    if "price" in data and "currency" not in data:
        # NetLicensing rejects a price without a currency; keep the current one.
        current = first_item_property(await nl_get(f"/bundle/{bundle_number}"), "currency")
        if current:
            data["currency"] = current
    return strip_output_fields(await nl_post(f"/bundle/{bundle_number}", data))


async def delete_bundle(bundle_number: str, force_cascade: bool = False) -> str:
    """Delete a bundle. Returns a JSON result."""
    params: dict[str, str] = {}
    if force_cascade:
        params["forceCascade"] = "true"
    status = await nl_delete(f"/bundle/{bundle_number}", params or None)
    return delete_result("delete_bundle", "Bundle", bundle_number, status, force_cascade)


def _item_props(item: object) -> dict[str, str]:
    if not isinstance(item, dict):
        return {}
    return {
        str(p.get("name")): str(p.get("value", ""))
        for p in item.get("property", [])
        if isinstance(p, dict)
    }


async def existing_bundle_licenses(bundle_number: str, licensee_number: str) -> list[str]:
    """Numbers of the licensee's licenses already derived from the bundle's templates.

    ``obtain`` has no idempotency key: repeating it (for example after a lost
    response) issues a second set of licenses. This lets the caller detect that.
    """
    from netlicensing_mcp.tools import licenses  # local: avoid an import cycle at load

    bundle = await nl_get(f"/bundle/{bundle_number}")
    raw = first_item_property(bundle, "licenseTemplateNumbers") or ""
    templates = {t.strip() for t in raw.split(",") if t.strip()}
    if not templates:
        return []
    resp = await licenses.list_all_licenses(licensee_number)
    items = (resp.get("items") or {}).get("item") or []
    found: list[str] = []
    for item in items if isinstance(items, list) else [items]:
        props = _item_props(item)
        if props.get("licenseTemplateNumber") in templates:
            found.append(props.get("number", ""))
    return found


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
