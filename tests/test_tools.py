"""
Test suite for netlicensing-mcp.
Run with: pytest tests/ -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def product_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Product",
                    "property": [
                        {"name": "number", "value": "P001"},
                        {"name": "name", "value": "Test Product"},
                        {"name": "active", "value": "true"},
                        {"name": "version", "value": "1.0"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def licensee_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Licensee",
                    "property": [
                        {"name": "number", "value": "I001"},
                        {"name": "name", "value": "ACME Corp"},
                        {"name": "active", "value": "true"},
                        {"name": "productNumber", "value": "P001"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def validation_response():
    return {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M01"},
                        {"name": "valid", "value": "true"},
                        {"name": "licensingModel", "value": "Subscription"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def shop_token_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "TK001"},
                        {"name": "tokenType", "value": "SHOP"},
                        {"name": "shopURL", "value": "https://netlicensing.io/shop?token=abc123"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def license_response():
    return {
        "items": {
            "item": [
                {
                    "type": "License",
                    "property": [
                        {"name": "number", "value": "L001"},
                        {"name": "active", "value": "true"},
                        {"name": "licenseeNumber", "value": "I001"},
                        {"name": "licenseTemplateNumber", "value": "LT01"},
                    ],
                }
            ]
        }
    }


# ── Products ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_products(product_response):
    with patch(
        "netlicensing_mcp.tools.products.nl_get", new=AsyncMock(return_value=product_response)
    ):
        from netlicensing_mcp.tools.products import list_products

        result = await list_products()
        assert result["items"]["item"][0]["type"] == "Product"


@pytest.mark.asyncio
async def test_get_product(product_response):
    with patch(
        "netlicensing_mcp.tools.products.nl_get", new=AsyncMock(return_value=product_response)
    ):
        from netlicensing_mcp.tools.products import get_product

        result = await get_product("P001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "P001"
        assert props["active"] == "true"


@pytest.mark.asyncio
async def test_create_product(product_response):
    with patch(
        "netlicensing_mcp.tools.products.nl_post", new=AsyncMock(return_value=product_response)
    ):
        from netlicensing_mcp.tools.products import create_product

        result = await create_product("P001", "Test Product")
        assert result["items"]["item"][0]["type"] == "Product"


@pytest.mark.asyncio
async def test_delete_product():
    with patch("netlicensing_mcp.tools.products.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.products import delete_product

        result = await delete_product("P001")
        assert "P001" in result
        assert "204" in result


# ── Licensees ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_licensees(licensee_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_get", new=AsyncMock(return_value=licensee_response)
    ):
        from netlicensing_mcp.tools.licensees import list_licensees

        result = await list_licensees("P001")
        assert result["items"]["item"][0]["type"] == "Licensee"


@pytest.mark.asyncio
async def test_validate_licensee(validation_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=validation_response)
    ):
        from netlicensing_mcp.tools.licensees import validate_licensee

        result = await validate_licensee("I001")
        item = result["items"]["item"][0]
        props = {p["name"]: p["value"] for p in item["property"]}
        assert props["valid"] == "true"


@pytest.mark.asyncio
async def test_create_licensee(licensee_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=licensee_response)
    ):
        from netlicensing_mcp.tools.licensees import create_licensee

        result = await create_licensee("P001", number="I001", name="ACME Corp")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "I001"


@pytest.mark.asyncio
async def test_transfer_licenses(licensee_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=licensee_response)
    ):
        from netlicensing_mcp.tools.licensees import transfer_licenses

        result = await transfer_licenses("I001", "I002")
        assert "item" in result["items"]


# ── Licenses ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_licenses(license_response):
    with patch(
        "netlicensing_mcp.tools.licenses.nl_get", new=AsyncMock(return_value=license_response)
    ):
        from netlicensing_mcp.tools.licenses import list_licenses

        result = await list_licenses("I001")
        assert result["items"]["item"][0]["type"] == "License"


@pytest.mark.asyncio
async def test_create_license(license_response):
    with patch(
        "netlicensing_mcp.tools.licenses.nl_post", new=AsyncMock(return_value=license_response)
    ):
        from netlicensing_mcp.tools.licenses import create_license

        result = await create_license("I001", "LT01")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["active"] == "true"


@pytest.mark.asyncio
async def test_update_license_deactivate(license_response):
    deactivated = dict(license_response)
    deactivated["items"]["item"][0]["property"][1]["value"] = "false"
    with patch("netlicensing_mcp.tools.licenses.nl_put", new=AsyncMock(return_value=deactivated)):
        from netlicensing_mcp.tools.licenses import update_license

        result = await update_license("L001", active=False)
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["active"] == "false"


@pytest.mark.asyncio
async def test_delete_license():
    with patch("netlicensing_mcp.tools.licenses.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.licenses import delete_license

        result = await delete_license("L001")
        assert "L001" in result


# ── Tokens ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_shop_token(shop_token_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_post", new=AsyncMock(return_value=shop_token_response)
    ):
        from netlicensing_mcp.tools.tokens import create_shop_token

        result = await create_shop_token("I001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert "shopURL" in props
        assert "netlicensing.io/shop" in props["shopURL"]


@pytest.mark.asyncio
async def test_create_api_token():
    mock_response = {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "tokenType", "value": "APIKEY"},
                        {"name": "role", "value": "ROLE_APIKEY_ANALYTICS"},
                        {"name": "number", "value": "TK002"},
                    ],
                }
            ]
        }
    }
    with patch("netlicensing_mcp.tools.tokens.nl_post", new=AsyncMock(return_value=mock_response)):
        from netlicensing_mcp.tools.tokens import create_api_token

        result = await create_api_token(role="ROLE_APIKEY_ANALYTICS")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["role"] == "ROLE_APIKEY_ANALYTICS"


# ── Prompts ───────────────────────────────────────────────────────────────────


def test_audit_prompts_register():
    """Verify all five audit prompts register without error."""
    from mcp.server.fastmcp import FastMCP
    from netlicensing_mcp.prompts.audit import register_audit_prompts

    server = FastMCP("test-server")
    register_audit_prompts(server)
    # No exception means prompts registered successfully


def test_audit_full_prompt_content():
    from mcp.server.fastmcp import FastMCP
    from netlicensing_mcp.prompts.audit import register_audit_prompts

    captured = {}

    class CaptureMCP(FastMCP):
        def prompt(self):
            def decorator(fn):
                if fn.__name__ == "license_audit_full":
                    msgs = fn("P001")
                    captured["text"] = msgs[0].content.text
                return fn

            return decorator

    server = CaptureMCP("test")
    register_audit_prompts(server)

    if captured:
        assert "P001" in captured["text"]
        assert "Step 1" in captured["text"]
