"""MCP tools for Product Modules."""

from __future__ import annotations

from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    _DELETE,
    _READONLY,
    _UPDATE,
    _WRITE,
    _confirm_error,
    _error,
    _json,
    _sample_numbers,
    _total_items,
    _wrap_json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import (
    license_templates,
    product_modules,
)
from netlicensing_mcp.tools.helpers import CustomPropertyValue


@tool(title="List product modules", annotations=_READONLY)
async def netlicensing_list_product_modules(
    product_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all modules (feature groups) for a product.

    Args:
        product_number: Product whose modules to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await product_modules.list_product_modules(
                product_number,
                filter_str=filter or None,
            ),
            "ProductModule",
            include_raw=include_raw,
            as_list=True,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_list_product_modules")


@tool(title="Get product module", annotations=_READONLY)
async def netlicensing_get_product_module(module_number: str, include_raw: bool = False) -> str:
    """Get a specific product module.

    Args:
        module_number: Module identifier
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await product_modules.get_product_module(module_number),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_product_module")


@tool(title="Create product module", annotations=_WRITE)
async def netlicensing_create_product_module(
    product_number: str,
    number: str,
    name: str,
    licensing_model: str,
    active: bool = True,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str = "",
    custom_properties: dict[str, CustomPropertyValue] | None = None,
    include_raw: bool = False,
) -> str:
    """Create a product module with a licensing model.

    Args:
        product_number: Parent product
        number: Unique module number (e.g. 'M01')
        name: Module name
        licensing_model: One of: TryAndBuy, Subscription, Rental, Floating,
                         MultiFeature, PayPerUse, PricingTable, Quota, NodeLocked
        active: Whether the module is active
        max_checkout_validity: Maximum checkout validity in days (Floating model)
        yellow_threshold: Remaining time volume for yellow warning (Rental model)
        red_threshold: Remaining time volume for red warning (Rental model)
        node_secret_mode: PREDEFINED or CLIENT (NodeLocked model)
        custom_properties: Additional properties as key-value pairs (e.g. skudef for PricingTable)
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await product_modules.create_product_module(
                product_number,
                number,
                name,
                licensing_model,
                active,
                max_checkout_validity=max_checkout_validity,
                yellow_threshold=yellow_threshold,
                red_threshold=red_threshold,
                node_secret_mode=node_secret_mode or None,
                custom_properties=custom_properties,
            ),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_create_product_module")


@tool(title="Update product module", annotations=_UPDATE)
async def netlicensing_update_product_module(
    module_number: str,
    name: str = "",
    active: bool | None = None,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str = "",
    custom_properties: dict[str, CustomPropertyValue] | None = None,
    include_raw: bool = False,
) -> str:
    """Update a product module's properties.

    Args:
        module_number: Module to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        max_checkout_validity: Maximum checkout validity in days (Floating model, omit to keep current)
        yellow_threshold: Remaining time volume for yellow warning (Rental model, omit to keep current)
        red_threshold: Remaining time volume for red warning (Rental model, omit to keep current)
        node_secret_mode: PREDEFINED or CLIENT (NodeLocked model, leave empty to keep current)
        custom_properties: Additional properties to set or update as key-value pairs
        include_raw: When true, include the sanitized NetLicensing API response under 'raw' (the upstream reply, before this tool's normalization)
    """
    try:
        return _wrap_json(
            await product_modules.update_product_module(
                module_number,
                name or None,
                active,
                max_checkout_validity=max_checkout_validity,
                yellow_threshold=yellow_threshold,
                red_threshold=red_threshold,
                node_secret_mode=node_secret_mode or None,
                custom_properties=custom_properties,
            ),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_update_product_module")


@tool(title="Preview deletion of product module", annotations=_READONLY)
async def netlicensing_preview_delete_product_module(module_number: str) -> str:
    """Preview what would be deleted when deleting a product module.

    Returns affected license template counts and a confirmation token.

    Args:
        module_number: Module to preview deletion for
    """
    try:
        await product_modules.get_product_module(module_number)  # raises if missing
        templates_resp = await license_templates.list_license_templates(
            module_number, page=0, items_per_page=100
        )
        return _json(
            safety.make_delete_preview(
                "delete_product_module",
                module_number,
                affected={"license_templates": _total_items(templates_resp)},
                samples={"license_templates": _sample_numbers(templates_resp)},
            )
        )
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_preview_delete_product_module")


@tool(title="Delete product module", annotations=_DELETE)
async def netlicensing_delete_product_module(
    module_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a product module.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_product_module)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        module_number: Module to delete
        force_cascade: Also delete all dependent license templates and licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_product_module", module_number)
            return await product_modules.delete_product_module(module_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        await product_modules.get_product_module(module_number)  # raises if missing
        templates_resp = await license_templates.list_license_templates(
            module_number, page=0, items_per_page=100
        )
        return _json(
            safety.make_delete_preview(
                "delete_product_module",
                module_number,
                affected={"license_templates": _total_items(templates_resp)},
                samples={"license_templates": _sample_numbers(templates_resp)},
            )
        )
    except ValueError as exc:
        return _confirm_error(exc, "netlicensing_delete_product_module")
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_delete_product_module")
