"""
NetLicensing MCP Server
=======================
Entry point for both stdio (Claude Desktop / Copilot) and HTTP (remote) modes.

Usage:
  stdio (default):  python -m netlicensing_mcp.server
  HTTP mode:        python -m netlicensing_mcp.server http
  Dev / inspector:  mcp dev src/netlicensing_mcp/server.py
"""

from __future__ import annotations

import json
import os
import sys

from mcp.server.fastmcp import FastMCP

from netlicensing_mcp.prompts.audit import register_audit_prompts
from netlicensing_mcp.tools import (
    license_templates,
    licensees,
    licenses,
    product_modules,
    products,
    tokens,
)

mcp = FastMCP(
    "netlicensing-mcp",
    instructions=(
        "You are connected to the Labs64 NetLicensing REST API. "
        "Use the available tools to manage products, product modules, "
        "license templates, licensees, and licenses. "
        "Always validate inputs before destructive operations and confirm with the user."
    ),
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _json(obj: object) -> str:
    return json.dumps(obj, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_products() -> str:
    """List all products in the NetLicensing account."""
    return _json(await products.list_products())


@mcp.tool()
async def tool_get_product(product_number: str) -> str:
    """Get details of a specific product.

    Args:
        product_number: Product identifier (e.g. 'P001')
    """
    return _json(await products.get_product(product_number))


@mcp.tool()
async def tool_create_product(
    number: str,
    name: str,
    version: str = "1.0",
    active: bool = True,
    description: str = "",
) -> str:
    """Create a new product.

    Args:
        number: Unique product number (e.g. 'P001')
        name: Human-readable product name
        version: Product version string
        active: Whether the product is active
        description: Optional product description
    """
    return _json(await products.create_product(number, name, active, version, description))


@mcp.tool()
async def tool_update_product(
    product_number: str,
    name: str = "",
    active: bool | None = None,
    version: str = "",
    description: str = "",
) -> str:
    """Update an existing product's fields.

    Args:
        product_number: Product to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        version: New version string (leave empty to keep current)
        description: New description (leave empty to keep current)
    """
    return _json(
        await products.update_product(
            product_number,
            name or None,
            active,
            version or None,
            description or None,
        )
    )


@mcp.tool()
async def tool_delete_product(product_number: str) -> str:
    """Delete a product permanently.

    Args:
        product_number: Product to delete
    """
    return await products.delete_product(product_number)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT MODULES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_product_modules(product_number: str) -> str:
    """List all modules (feature groups) for a product.

    Args:
        product_number: Product whose modules to list
    """
    return _json(await product_modules.list_product_modules(product_number))


@mcp.tool()
async def tool_get_product_module(module_number: str) -> str:
    """Get a specific product module.

    Args:
        module_number: Module identifier
    """
    return _json(await product_modules.get_product_module(module_number))


@mcp.tool()
async def tool_create_product_module(
    product_number: str,
    number: str,
    name: str,
    licensing_model: str,
    active: bool = True,
) -> str:
    """Create a product module with a licensing model.

    Args:
        product_number: Parent product
        number: Unique module number (e.g. 'M01')
        name: Module name
        licensing_model: One of: TryAndBuy, Subscription, Rental, Floating,
                         MultiFeature, PayPerUse, PricingTable, Quota, NodeLocked
        active: Whether the module is active
    """
    return _json(
        await product_modules.create_product_module(
            product_number,
            number,
            name,
            licensing_model,
            active,
        )
    )


@mcp.tool()
async def tool_delete_product_module(module_number: str) -> str:
    """Delete a product module.

    Args:
        module_number: Module to delete
    """
    return await product_modules.delete_product_module(module_number)


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_license_templates(module_number: str) -> str:
    """List all license templates for a product module.

    Args:
        module_number: Module whose templates to list
    """
    return _json(await license_templates.list_license_templates(module_number))


@mcp.tool()
async def tool_get_license_template(template_number: str) -> str:
    """Get a specific license template.

    Args:
        template_number: Template identifier
    """
    return _json(await license_templates.get_license_template(template_number))


@mcp.tool()
async def tool_create_license_template(
    module_number: str,
    number: str,
    name: str,
    license_type: str,
    price: float = 0.0,
    currency: str = "EUR",
    automatic: bool = False,
    active: bool = True,
) -> str:
    """Create a license template.

    Args:
        module_number: Parent product module
        number: Unique template number (e.g. 'LT01')
        name: Template display name
        license_type: FEATURE | TIMEVOLUME | FLOATING | QUANTITY
        price: Template price (0 for free)
        currency: ISO 4217 currency code (default EUR)
        automatic: Auto-assign this license to new licensees
        active: Whether the template is active
    """
    return _json(
        await license_templates.create_license_template(
            module_number,
            number,
            name,
            license_type,
            active,
            price,
            currency,
            automatic,
        )
    )


@mcp.tool()
async def tool_delete_license_template(template_number: str) -> str:
    """Delete a license template.

    Args:
        template_number: Template to delete
    """
    return await license_templates.delete_license_template(template_number)


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSEES  (customers)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_licensees(product_number: str) -> str:
    """List all customers (licensees) for a product.

    Args:
        product_number: Product to list customers for
    """
    return _json(await licensees.list_licensees(product_number))


@mcp.tool()
async def tool_get_licensee(licensee_number: str) -> str:
    """Get a specific licensee (customer).

    Args:
        licensee_number: Licensee identifier (e.g. 'I001')
    """
    return _json(await licensees.get_licensee(licensee_number))


@mcp.tool()
async def tool_create_licensee(
    product_number: str,
    number: str = "",
    name: str = "",
    active: bool = True,
) -> str:
    """Create a new customer (licensee) under a product.

    Args:
        product_number: Product to associate the customer with
        number: Optional custom licensee number (auto-generated if empty)
        name: Optional display name for the customer
        active: Whether the licensee is active
    """
    return _json(
        await licensees.create_licensee(
            product_number,
            number or None,
            name or None,
            active,
        )
    )


@mcp.tool()
async def tool_update_licensee(
    licensee_number: str,
    name: str = "",
    active: bool | None = None,
) -> str:
    """Update a licensee's name or active status.

    Args:
        licensee_number: Licensee to update
        name: New name (empty to keep current)
        active: New active state (omit to keep current)
    """
    return _json(
        await licensees.update_licensee(
            licensee_number,
            name or None,
            active,
        )
    )


@mcp.tool()
async def tool_delete_licensee(licensee_number: str) -> str:
    """Delete a licensee and all their licenses permanently.

    Args:
        licensee_number: Licensee to delete
    """
    return await licensees.delete_licensee(licensee_number)


@mcp.tool()
async def tool_validate_licensee(
    licensee_number: str,
    product_number: str = "",
) -> str:
    """Validate a customer's licenses across all product modules.

    Returns per-module validity, type, expiry dates, and usage counts.

    Args:
        licensee_number: Customer to validate
        product_number: Optional — scope validation to a specific product
    """
    return _json(
        await licensees.validate_licensee(
            licensee_number,
            product_number or None,
        )
    )


@mcp.tool()
async def tool_transfer_licenses(
    from_licensee_number: str,
    to_licensee_number: str,
) -> str:
    """Transfer all licenses from one licensee to another.

    Args:
        from_licensee_number: Source licensee
        to_licensee_number: Destination licensee
    """
    return _json(
        await licensees.transfer_licenses(
            from_licensee_number,
            to_licensee_number,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_licenses(licensee_number: str) -> str:
    """List all licenses for a specific customer.

    Args:
        licensee_number: Customer whose licenses to list
    """
    return _json(await licenses.list_licenses(licensee_number))


@mcp.tool()
async def tool_get_license(license_number: str) -> str:
    """Get details of a specific license.

    Args:
        license_number: License identifier
    """
    return _json(await licenses.get_license(license_number))


@mcp.tool()
async def tool_create_license(
    licensee_number: str,
    license_template_number: str,
    number: str = "",
    active: bool = True,
) -> str:
    """Assign a new license to a customer from a license template.

    Args:
        licensee_number: Customer to assign the license to
        license_template_number: Template defining type and rules
        number: Optional custom license number
        active: Whether the license is active immediately
    """
    return _json(
        await licenses.create_license(
            licensee_number,
            license_template_number,
            number or None,
            active,
        )
    )


@mcp.tool()
async def tool_update_license(
    license_number: str,
    active: bool | None = None,
) -> str:
    """Activate or deactivate a license.

    Args:
        license_number: License to update
        active: True to activate, False to deactivate
    """
    return _json(await licenses.update_license(license_number, active))


@mcp.tool()
async def tool_delete_license(license_number: str) -> str:
    """Delete a license permanently.

    Args:
        license_number: License to delete
    """
    return await licenses.delete_license(license_number)


# ═══════════════════════════════════════════════════════════════════════════════
# TOKENS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def tool_list_tokens() -> str:
    """List all active tokens in the account."""
    return _json(await tokens.list_tokens())


@mcp.tool()
async def tool_create_shop_token(
    licensee_number: str,
    success_url: str = "",
    cancel_url: str = "",
) -> str:
    """Generate a NetLicensing Shop one-time checkout URL for a customer.

    Args:
        licensee_number: Customer to generate the shop URL for
        success_url: Optional URL to redirect to after successful purchase
        cancel_url: Optional URL to redirect to if customer cancels
    """
    return _json(
        await tokens.create_shop_token(
            licensee_number,
            success_url or None,
            cancel_url or None,
        )
    )


@mcp.tool()
async def tool_create_api_token(
    role: str = "ROLE_APIKEY_LICENSEE",
    licensee_number: str = "",
) -> str:
    """Create a scoped API token.

    Args:
        role: ROLE_APIKEY_LICENSEE | ROLE_APIKEY_ANALYTICS |
              ROLE_APIKEY_OPERATION | ROLE_APIKEY_MAINTENANCE
        licensee_number: Optional — scope token to a specific licensee
    """
    return _json(await tokens.create_api_token(role, licensee_number or None))


@mcp.tool()
async def tool_delete_token(token_number: str) -> str:
    """Revoke an API or shop token.

    Args:
        token_number: Token to revoke
    """
    return await tokens.delete_token(token_number)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

register_audit_prompts(mcp)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == "http":
        mcp.run(transport="streamable-http")  # host/port set on constructor
    else:
        mcp.run()


if __name__ == "__main__":
    main()
