"""MCP tools for Products."""

from __future__ import annotations

import asyncio
import json

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _UPDATE,
    _WRITE,
    _confirm_error,
    _error,
    _extract_props,
    _json,
    _list_filter,
    _total_items,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools.helpers import VAT_MODES, require_one_of
from netlicensing_mcp.tools import (
    bundles,
    license_templates,
    licenses,
    licensees,
    product_modules,
    products,
)


@tool(title="List products", annotations=_READONLY)
async def netlicensing_list_products(
    filter: str = "",
    page: int | None = None,
    page_size: int | None = None,
    compact: bool = False,
    include_raw: bool = False,
) -> str:
    """List all products in the NetLicensing account.

    Args:
        ; supported keys: active (others are ignored with a warning; malformed expressions are rejected)
        page: Page to return, 0-based (default 0; overrides 'page' in filter)
        page_size: Items per page, 1-100 (default 25; overrides 'items' in filter)
        compact: When true, return only type, number, name, status and active for each item
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        filter = _list_filter(filter, page, page_size, supported=("active",))
        return _wrap_json(
            await products.list_products(filter_str=filter or None),
            "Product",
            include_raw=include_raw,
            as_list=True,
            paging_filter=filter,
            compact=compact,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_products")


@tool(title="Get product", annotations=_READONLY)
async def netlicensing_get_product(product_number: str, include_raw: bool = False) -> str:
    """Get details of a specific product.

    Args:
        product_number: Product identifier (e.g. 'P001')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await products.get_product(product_number), "Product", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_product")


@tool(title="Create product", annotations=_WRITE)
async def netlicensing_create_product(
    number: str,
    name: str,
    version: str = "1.0",
    active: bool = True,
    description: str = "",
    licensing_info: str = "",
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
    licensee_secret_mode: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new product.

    Args:
        number: Unique product number (e.g. 'P001')
        name: Human-readable product name
        version: Product version string
        active: Whether the product is active
        description: Optional product description
        licensing_info: Optional licensing information displayed in the shop
        licensee_auto_create: Auto-create licensees on first validation attempt
        vat_mode: GROSS or NET (leave empty to use account default)
        licensee_secret_mode: DISABLED, PREDEFINED, or CLIENT (leave empty for default)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await products.create_product(
                number,
                name,
                active,
                version,
                description,
                licensing_info=licensing_info,
                licensee_auto_create=licensee_auto_create,
                vat_mode=vat_mode or None,
                licensee_secret_mode=licensee_secret_mode or None,
            ),
            "Product",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_create_product")


@tool(title="Preview update of product", annotations=_READONLY)
async def netlicensing_preview_update_product(
    product_number: str,
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
) -> str:
    """Preview a sensitive product update (licenseeAutoCreate or vatMode change).

    Returns a diff of proposed changes and a confirmation token. Pass the
    token to netlicensing_update_product within 5 minutes to apply.

    Args:
        product_number: Product to preview changes for
        licensee_auto_create: Proposed new auto-create setting (omit to skip)
        vat_mode: Proposed new VAT mode — GROSS or NET (leave empty to skip)
    """
    try:
        # Same checks as the update tool, before a token is issued.
        require_one_of("vat_mode", vat_mode, VAT_MODES)
        current_resp = await products.get_product(product_number)
        current = _extract_props(current_resp)
        diff: list[dict] = []
        if licensee_auto_create is not None:
            diff.append(
                {
                    "field": "licenseeAutoCreate",
                    "from": current.get("licenseeAutoCreate"),
                    "to": str(licensee_auto_create).lower(),
                }
            )
        if vat_mode:
            diff.append({"field": "vatMode", "from": current.get("vatMode"), "to": vat_mode})
        return _json(
            safety.make_update_preview(
                "update_product",
                product_number,
                diff,
                changes=safety.change_set(
                    licenseeAutoCreate=licensee_auto_create, vatMode=vat_mode
                ),
            )
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_update_product")


@tool(title="Update product", annotations=_UPDATE)
async def netlicensing_update_product(
    product_number: str,
    name: str = "",
    active: bool | None = None,
    version: str = "",
    description: str = "",
    licensing_info: str = "",
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
    licensee_secret_mode: str = "",
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update an existing product's fields.

    Changing licenseeAutoCreate or vatMode requires a confirmation token
    (downstream business effect). Call netlicensing_preview_update_product first.

    Args:
        product_number: Product to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        version: New version string (leave empty to keep current)
        description: New description (leave empty to keep current)
        licensing_info: Licensing information for the shop (leave empty to keep current)
        licensee_auto_create: Auto-create licensees on first validation
        vat_mode: GROSS or NET (leave empty to keep current)
        licensee_secret_mode: DISABLED, PREDEFINED, or CLIENT (leave empty to keep current)
        confirm_token: Confirmation token (required when licenseeAutoCreate or vatMode change)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        sensitive = licensee_auto_create is not None or bool(vat_mode)
        changes = safety.change_set(licenseeAutoCreate=licensee_auto_create, vatMode=vat_mode)

        if sensitive:
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_product", product_number, changes=changes
                )
            else:
                current_resp = await products.get_product(product_number)
                current = _extract_props(current_resp)
                diff: list[dict] = []
                if licensee_auto_create is not None:
                    diff.append(
                        {
                            "field": "licenseeAutoCreate",
                            "from": current.get("licenseeAutoCreate"),
                            "to": str(licensee_auto_create).lower(),
                        }
                    )
                if vat_mode:
                    diff.append(
                        {
                            "field": "vatMode",
                            "from": current.get("vatMode"),
                            "to": vat_mode,
                        }
                    )
                preview = safety.make_update_preview(
                    "update_product", product_number, diff, changes=changes
                )
                if not preview.get("no_change"):
                    return _json(preview)
                # The sensitive fields already hold the requested values: apply the rest.

        return _wrap_json(
            await products.update_product(
                product_number,
                name or None,
                active,
                version or None,
                description or None,
                licensing_info=licensing_info or None,
                licensee_auto_create=licensee_auto_create,
                vat_mode=vat_mode or None,
                licensee_secret_mode=licensee_secret_mode or None,
            ),
            "Product",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_update_product")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_product")


#: Upper bounds of the lookups a product delete preview makes; beyond them a count
#: is reported as "unknown" instead of issuing hundreds of requests.
_PREVIEW_MAX_MODULES = 50
_PREVIEW_MAX_LICENSEES = 50
_PREVIEW_MAX_BUNDLE_PAGES = 5


def _item_numbers(response: dict) -> list[str]:
    items = response.get("items", {}).get("item", [])
    out: list[str] = []
    for item in items if isinstance(items, list) else []:
        for prop in item.get("property", []) if isinstance(item, dict) else []:
            if isinstance(prop, dict) and prop.get("name") == "number":
                out.append(str(prop.get("value", "")))
                break
    return out


async def _count_templates(module_numbers: list[str]) -> tuple[int, list[str]]:
    """Total license templates of *module_numbers* and (a page of) their numbers."""
    resps = await asyncio.gather(
        *(
            license_templates.list_license_templates(m, page=0, items_per_page=100)
            for m in module_numbers
        )
    )
    return sum(_total_items(r) for r in resps), [n for r in resps for n in _item_numbers(r)]


async def _count_licenses(licensee_numbers: list[str]) -> int:
    resps = await asyncio.gather(
        *(licenses.list_licenses(n, page=0, items_per_page=1) for n in licensee_numbers)
    )
    return sum(_total_items(r) for r in resps)


async def _bundles_using(template_numbers: set[str]) -> list[str]:
    """Numbers of the bundles that contain any of *template_numbers*."""
    found: list[str] = []
    for page in range(_PREVIEW_MAX_BUNDLE_PAGES):
        resp = await bundles.list_bundles(f"page={page};items=100")
        items = resp.get("items", {})
        for item in items.get("item", []) if isinstance(items, dict) else []:
            props = {
                p.get("name"): p.get("value")
                for p in item.get("property", [])
                if isinstance(p, dict)
            }
            used = {t.strip() for t in str(props.get("licenseTemplateNumbers") or "").split(",")}
            if used & template_numbers:
                found.append(str(props.get("number", "")))
        if not (isinstance(items, dict) and str(items.get("hasnext", "")).lower() == "true"):
            return found
    return found


async def _product_delete_preview(product_number: str, force_cascade: bool) -> str:
    await products.get_product(product_number)  # raises if it does not exist
    modules_resp = await product_modules.list_product_modules(
        product_number, page=0, items_per_page=100
    )
    licensees_resp = await licensees.list_licensees(product_number, page=0, items_per_page=100)
    modules_n = _total_items(modules_resp)
    licensees_n = _total_items(licensees_resp)
    module_numbers = _item_numbers(modules_resp)
    licensee_numbers = _item_numbers(licensees_resp)

    templates_n: int | str = "unknown"
    template_numbers: list[str] = []
    bundles_n: int | str = "unknown"
    bundle_numbers: list[str] = []
    licenses_n: int | str = "unknown"
    # A failed secondary lookup (a role that cannot read it, a timeout) leaves that
    # count "unknown" instead of failing the whole preview.
    if modules_n <= _PREVIEW_MAX_MODULES and len(module_numbers) == modules_n:
        try:
            templates_n, template_numbers = await _count_templates(module_numbers)
        except NetLicensingError:
            templates_n = "unknown"
        if isinstance(templates_n, int) and templates_n == len(template_numbers):
            try:
                bundle_numbers = await _bundles_using(set(template_numbers))
                bundles_n = len(bundle_numbers)
            except NetLicensingError:
                bundles_n = "unknown"
    if licensees_n <= _PREVIEW_MAX_LICENSEES and len(licensee_numbers) == licensees_n:
        try:
            licenses_n = await _count_licenses(licensee_numbers)
        except NetLicensingError:
            licenses_n = "unknown"

    affected: dict[str, int | str] = {
        "product_modules": modules_n,
        "license_templates": templates_n,
        "licensees": licensees_n,
        "licenses": licenses_n,
        "bundles": bundles_n,
    }
    # Bundles are not deleted by the cascade and do not block a delete: they are orphaned.
    blocking = {k: v for k, v in affected.items() if isinstance(v, int) and v and k != "bundles"}
    preview = safety.make_delete_preview(
        "delete_product",
        product_number,
        affected=affected,
        samples={
            "product_modules": module_numbers[:3],
            "license_templates": template_numbers[:3],
            "licensees": licensee_numbers[:3],
            "bundles": bundle_numbers[:3],
        },
        force_cascade=force_cascade,
        blocking=blocking,
    )
    unknown = [k for k, v in affected.items() if v == "unknown"]
    warnings: list[str] = []
    if unknown:
        warnings.append(
            f"{', '.join(unknown)}: count not computed (too many modules or licensees to "
            "enumerate cheaply); treat the real impact as larger than shown."
        )
    if bundle_numbers:
        warnings.append(
            f"{len(bundle_numbers)} bundle(s) use this product's license templates. "
            "NetLicensing does NOT delete bundles in a cascade: they stay behind (inactive, "
            "with dangling licenseTemplateNumbers). Delete them separately with "
            "netlicensing_preview_delete_bundle / netlicensing_delete_bundle."
        )
    if warnings:
        preview["warnings"] = warnings
    return _json(preview)


async def _product_bundle_numbers(product_number: str) -> list[str]:
    """Best-effort numbers of the bundles that use any template of the product."""
    try:
        modules_resp = await product_modules.list_product_modules(
            product_number, page=0, items_per_page=100
        )
        module_numbers = _item_numbers(modules_resp)
        if not module_numbers:
            return []
        _, template_numbers = await _count_templates(module_numbers)
        return await _bundles_using(set(template_numbers)) if template_numbers else []
    except NetLicensingError:
        return []


def _with_orphaned_bundles(result: str, bundle_numbers: list[str]) -> str:
    """Add the bundles a cascade left behind to a ``delete_result`` JSON string."""
    if not bundle_numbers:
        return result
    out = json.loads(result)
    shown = ", ".join(bundle_numbers[:10]) + (" …" if len(bundle_numbers) > 10 else "")
    out["orphaned_bundles"] = bundle_numbers
    out["warnings"] = [
        *out.get("warnings", []),
        f"Bundles are not deleted by a product cascade and now reference deleted "
        f"templates: {shown}.",
    ]
    out["suggested_actions"] = [
        *out.get("suggested_actions", []),
        *(f'netlicensing_preview_delete_bundle(bundle_number="{b}")' for b in bundle_numbers[:10]),
    ]
    return json.dumps(out, indent=2)


@tool(title="Preview deletion of product", annotations=_READONLY)
async def netlicensing_preview_delete_product(
    product_number: str, force_cascade: bool = False
) -> str:
    """Preview what would be deleted when deleting a product.

    Returns affected counts (modules, license templates, licensees, licenses and
    bundles; "unknown" when too many to count cheaply), sample entity identifiers,
    `requires_force_cascade` and `blocking_dependencies` (a product with
    modules or licensees cannot be deleted without force_cascade), and a short-lived confirmation token. The
    token is bound to the force_cascade value used here: pass the same value,
    with the token, to netlicensing_delete_product within 5 minutes.

    Args:
        product_number: Product to preview deletion for
        force_cascade: Preview a cascade delete (also removes dependent modules, templates, licensees and licenses; bundles that use the product's templates are reported too)
    """
    try:
        return await _product_delete_preview(product_number, force_cascade)
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_delete_product")


@tool(title="Delete product", annotations=_DELETE)
async def netlicensing_delete_product(
    product_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a product permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_product,
       which shows the dependencies and whether force_cascade is required) to
       receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token and the same force_cascade value within
       5 minutes to execute. A token issued for a non-cascade delete is rejected
       for force_cascade=true and the reverse.

    Args:
        product_number: Product to delete
        force_cascade: Also delete all dependent modules, templates, licensees, and licenses (bundles are NOT deleted: they are orphaned and reported)
        confirm_token: Confirmation token from a previous preview call (not proof of human approval: show the preview to the user and wait for their go-ahead)
    """
    try:
        if confirm_token:
            safety.validate_and_consume(
                confirm_token, "delete_product", product_number, force_cascade
            )
            bundle_numbers = await _product_bundle_numbers(product_number) if force_cascade else []
            result = await products.delete_product(product_number, force_cascade)
            return _with_orphaned_bundles(result, bundle_numbers)

        # No token: always show the preview; deletion is never allowed without confirmation.
        return await _product_delete_preview(product_number, force_cascade)
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_product")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_product")
