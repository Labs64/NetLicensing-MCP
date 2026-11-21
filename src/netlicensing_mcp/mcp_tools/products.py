"""MCP tools for Products."""

from __future__ import annotations

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
    _sample_numbers,
    _total_items,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import (
    licensees,
    product_modules,
    products,
)


@tool(title="List products", annotations=_READONLY)
async def netlicensing_list_products(filter: str = "", include_raw: bool = False) -> str:
    """List all products in the NetLicensing account.

    Args:
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await products.list_products(filter_str=filter or None),
            "Product",
            include_raw=include_raw,
            as_list=True,
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
        return _json(safety.make_update_preview("update_product", product_number, diff))
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

        if sensitive:
            if confirm_token:
                safety.validate_and_consume(confirm_token, "update_product", product_number)
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
                return _json(safety.make_update_preview("update_product", product_number, diff))

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


@tool(title="Preview deletion of product", annotations=_READONLY)
async def netlicensing_preview_delete_product(product_number: str) -> str:
    """Preview what would be deleted when deleting a product.

    Returns affected counts, sample entity identifiers, and a short-lived
    confirmation token. Pass the token to netlicensing_delete_product within
    5 minutes to confirm the deletion.

    Args:
        product_number: Product to preview deletion for
    """
    try:
        # Use filter-embedded pagination to get accurate total counts from
        # the API metadata (``totalitems``), not just the current page.
        # items=1 for modules — only total count is needed, no samples.
        # items=100 for licensees — fetch enough to also extract samples.
        await products.get_product(product_number)  # raises if it does not exist
        modules_resp = await product_modules.list_product_modules(
            product_number, page=0, items_per_page=1
        )
        licensees_resp = await licensees.list_licensees(product_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_product",
                product_number,
                affected={
                    "product_modules": _total_items(modules_resp),
                    "licensees": _total_items(licensees_resp),
                },
                samples={"licensees": _sample_numbers(licensees_resp)},
            )
        )
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
    1. Call without confirm_token (or call netlicensing_preview_delete_product)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        product_number: Product to delete
        force_cascade: Also delete all dependent modules, templates, licensees, and licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_product", product_number)
            return await products.delete_product(product_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        await products.get_product(product_number)  # raises if it does not exist
        modules_resp = await product_modules.list_product_modules(
            product_number, page=0, items_per_page=1
        )
        licensees_resp = await licensees.list_licensees(product_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_product",
                product_number,
                affected={
                    "product_modules": _total_items(modules_resp),
                    "licensees": _total_items(licensees_resp),
                },
                samples={"licensees": _sample_numbers(licensees_resp)},
            )
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_product")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_product")
