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
def module_response():
    return {
        "items": {
            "item": [
                {
                    "type": "ProductModule",
                    "property": [
                        {"name": "number", "value": "M01"},
                        {"name": "name", "value": "Subscription Module"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "active", "value": "true"},
                        {"name": "productNumber", "value": "P001"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def template_response():
    return {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [
                        {"name": "number", "value": "LT01"},
                        {"name": "name", "value": "Sub Template"},
                        {"name": "licenseType", "value": "TIMEVOLUME"},
                        {"name": "active", "value": "true"},
                        {"name": "productModuleNumber", "value": "M01"},
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
def api_token_response():
    return {
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


@pytest.fixture
def bundle_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Bundle",
                    "property": [
                        {"name": "number", "value": "B001"},
                        {"name": "name", "value": "Starter Bundle"},
                        {"name": "active", "value": "true"},
                        {"name": "licenseTemplateNumber", "value": "LT01,LT02"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def bundle_obtain_response():
    return {
        "items": {
            "item": [
                {
                    "type": "License",
                    "property": [
                        {"name": "number", "value": "L100"},
                        {"name": "active", "value": "true"},
                        {"name": "licenseeNumber", "value": "I001"},
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
async def test_list_products_with_filter(product_response):
    mock_get = AsyncMock(return_value=product_response)
    with patch("netlicensing_mcp.tools.products.nl_get", new=mock_get):
        from netlicensing_mcp.tools.products import list_products

        result = await list_products(filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "Product"
        mock_get.assert_called_once_with("/product", {"filter": "active=true"})


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
async def test_create_product_all_fields(product_response):
    mock_post = AsyncMock(return_value=product_response)
    with patch("netlicensing_mcp.tools.products.nl_post", new=mock_post):
        from netlicensing_mcp.tools.products import create_product

        result = await create_product(
            "P001",
            "Test Product",
            active=True,
            version="2.0",
            description="A product",
            licensing_info="Licensed under X",
            licensee_auto_create=True,
            vat_mode="GROSS",
            licensee_secret_mode="PREDEFINED",
        )
        assert result["items"]["item"][0]["type"] == "Product"
        call_data = mock_post.call_args[0][1]
        assert call_data["number"] == "P001"
        assert call_data["name"] == "Test Product"
        assert call_data["version"] == "2.0"
        assert call_data["description"] == "A product"
        assert call_data["licensingInfo"] == "Licensed under X"
        assert call_data["licenseeAutoCreate"] == "true"
        assert call_data["vatMode"] == "GROSS"
        assert call_data["licenseeSecretMode"] == "PREDEFINED"


@pytest.mark.asyncio
async def test_update_product(product_response):
    with patch(
        "netlicensing_mcp.tools.products.nl_post", new=AsyncMock(return_value=product_response)
    ):
        from netlicensing_mcp.tools.products import update_product

        result = await update_product("P001", name="Updated Product")
        assert result["items"]["item"][0]["type"] == "Product"


@pytest.mark.asyncio
async def test_update_product_all_fields(product_response):
    mock_put = AsyncMock(return_value=product_response)
    with patch("netlicensing_mcp.tools.products.nl_post", new=mock_put):
        from netlicensing_mcp.tools.products import update_product

        result = await update_product(
            "P001",
            name="Updated Product",
            active=False,
            version="3.0",
            description="Updated desc",
            licensing_info="Updated info",
            licensee_auto_create=False,
            vat_mode="NET",
            licensee_secret_mode="CLIENT",
        )
        assert result["items"]["item"][0]["type"] == "Product"
        call_data = mock_put.call_args[0][1]
        assert call_data["name"] == "Updated Product"
        assert call_data["active"] == "false"
        assert call_data["version"] == "3.0"
        assert call_data["description"] == "Updated desc"
        assert call_data["licensingInfo"] == "Updated info"
        assert call_data["licenseeAutoCreate"] == "false"
        assert call_data["vatMode"] == "NET"
        assert call_data["licenseeSecretMode"] == "CLIENT"


@pytest.mark.asyncio
async def test_delete_product():
    with patch("netlicensing_mcp.tools.products.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.products import delete_product

        result = await delete_product("P001")
        assert "P001" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_product_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.products.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.products import delete_product

        result = await delete_product("P001", force_cascade=True)
        assert "P001" in result
        mock_delete.assert_called_once_with("/product/P001", {"forceCascade": "true"})


# ── Bundles ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_bundles(bundle_response):
    with patch(
        "netlicensing_mcp.tools.bundles.nl_get", new=AsyncMock(return_value=bundle_response)
    ):
        from netlicensing_mcp.tools.bundles import list_bundles

        result = await list_bundles()
        assert result["items"]["item"][0]["type"] == "Bundle"


@pytest.mark.asyncio
async def test_get_bundle(bundle_response):
    with patch(
        "netlicensing_mcp.tools.bundles.nl_get", new=AsyncMock(return_value=bundle_response)
    ):
        from netlicensing_mcp.tools.bundles import get_bundle

        result = await get_bundle("B001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "B001"
        assert props["active"] == "true"


@pytest.mark.asyncio
async def test_create_bundle(bundle_response):
    with patch(
        "netlicensing_mcp.tools.bundles.nl_post", new=AsyncMock(return_value=bundle_response)
    ):
        from netlicensing_mcp.tools.bundles import create_bundle

        result = await create_bundle("B001", "Starter Bundle", ["LT01", "LT02"])
        assert result["items"]["item"][0]["type"] == "Bundle"


@pytest.mark.asyncio
async def test_update_bundle(bundle_response):
    with patch(
        "netlicensing_mcp.tools.bundles.nl_post", new=AsyncMock(return_value=bundle_response)
    ):
        from netlicensing_mcp.tools.bundles import update_bundle

        result = await update_bundle("B001", name="Updated Bundle")
        assert result["items"]["item"][0]["type"] == "Bundle"


@pytest.mark.asyncio
async def test_delete_bundle():
    with patch("netlicensing_mcp.tools.bundles.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.bundles import delete_bundle

        result = await delete_bundle("B001")
        assert "B001" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_bundle_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.bundles.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.bundles import delete_bundle

        result = await delete_bundle("B001", force_cascade=True)
        assert "B001" in result
        mock_delete.assert_called_once_with("/bundle/B001", {"forceCascade": "true"})


@pytest.mark.asyncio
async def test_obtain_bundle(bundle_obtain_response):
    with patch(
        "netlicensing_mcp.tools.bundles.nl_post",
        new=AsyncMock(return_value=bundle_obtain_response),
    ):
        from netlicensing_mcp.tools.bundles import obtain_bundle

        result = await obtain_bundle("B001", "I001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["licenseeNumber"] == "I001"


# ── Product Modules ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_product_modules(module_response):
    with patch(
        "netlicensing_mcp.tools.product_modules.nl_get",
        new=AsyncMock(return_value=module_response),
    ):
        from netlicensing_mcp.tools.product_modules import list_product_modules

        result = await list_product_modules("P001")
        assert result["items"]["item"][0]["type"] == "ProductModule"


@pytest.mark.asyncio
async def test_list_product_modules_with_filter(module_response):
    mock_get = AsyncMock(return_value=module_response)
    with patch("netlicensing_mcp.tools.product_modules.nl_get", new=mock_get):
        from netlicensing_mcp.tools.product_modules import list_product_modules

        result = await list_product_modules("P001", filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "ProductModule"
        mock_get.assert_called_once_with(
            "/productmodule",
            {"productNumber": "P001", "filter": "active=true"},
        )


@pytest.mark.asyncio
async def test_get_product_module(module_response):
    with patch(
        "netlicensing_mcp.tools.product_modules.nl_get",
        new=AsyncMock(return_value=module_response),
    ):
        from netlicensing_mcp.tools.product_modules import get_product_module

        result = await get_product_module("M01")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "M01"
        assert props["licensingModel"] == "Subscription"


@pytest.mark.asyncio
async def test_create_product_module(module_response):
    with patch(
        "netlicensing_mcp.tools.product_modules.nl_post",
        new=AsyncMock(return_value=module_response),
    ):
        from netlicensing_mcp.tools.product_modules import create_product_module

        result = await create_product_module("P001", "M01", "Subscription Module", "Subscription")
        assert result["items"]["item"][0]["type"] == "ProductModule"


@pytest.mark.asyncio
async def test_create_product_module_all_fields(module_response):
    mock_post = AsyncMock(return_value=module_response)
    with patch("netlicensing_mcp.tools.product_modules.nl_post", new=mock_post):
        from netlicensing_mcp.tools.product_modules import create_product_module

        result = await create_product_module(
            "P001",
            "M01",
            "Floating Module",
            "Floating",
            active=True,
            max_checkout_validity=30,
            yellow_threshold=10,
            red_threshold=5,
            node_secret_mode="PREDEFINED",
        )
        assert result["items"]["item"][0]["type"] == "ProductModule"
        call_data = mock_post.call_args[0][1]
        assert call_data["productNumber"] == "P001"
        assert call_data["number"] == "M01"
        assert call_data["licensingModel"] == "Floating"
        assert call_data["maxCheckoutValidity"] == "30"
        assert call_data["yellowThreshold"] == "10"
        assert call_data["redThreshold"] == "5"
        assert call_data["nodeSecretMode"] == "PREDEFINED"


@pytest.mark.asyncio
async def test_update_product_module(module_response):
    with patch(
        "netlicensing_mcp.tools.product_modules.nl_post",
        new=AsyncMock(return_value=module_response),
    ):
        from netlicensing_mcp.tools.product_modules import update_product_module

        result = await update_product_module("M01", name="Updated Module")
        assert result["items"]["item"][0]["type"] == "ProductModule"


@pytest.mark.asyncio
async def test_update_product_module_all_fields(module_response):
    mock_put = AsyncMock(return_value=module_response)
    with patch("netlicensing_mcp.tools.product_modules.nl_post", new=mock_put):
        from netlicensing_mcp.tools.product_modules import update_product_module

        result = await update_product_module(
            "M01",
            name="Updated Module",
            active=False,
            max_checkout_validity=60,
            yellow_threshold=15,
            red_threshold=3,
            node_secret_mode="CLIENT",
        )
        assert result["items"]["item"][0]["type"] == "ProductModule"
        call_data = mock_put.call_args[0][1]
        assert call_data["name"] == "Updated Module"
        assert call_data["active"] == "false"
        assert call_data["maxCheckoutValidity"] == "60"
        assert call_data["yellowThreshold"] == "15"
        assert call_data["redThreshold"] == "3"
        assert call_data["nodeSecretMode"] == "CLIENT"


@pytest.mark.asyncio
async def test_delete_product_module():
    with patch("netlicensing_mcp.tools.product_modules.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.product_modules import delete_product_module

        result = await delete_product_module("M01")
        assert "M01" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_product_module_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.product_modules.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.product_modules import delete_product_module

        result = await delete_product_module("M01", force_cascade=True)
        assert "M01" in result
        mock_delete.assert_called_once_with("/productmodule/M01", {"forceCascade": "true"})


# ── License Templates ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_license_templates(template_response):
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        new=AsyncMock(return_value=template_response),
    ):
        from netlicensing_mcp.tools.license_templates import list_license_templates

        result = await list_license_templates("M01")
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"


@pytest.mark.asyncio
async def test_list_license_templates_with_filter(template_response):
    mock_get = AsyncMock(return_value=template_response)
    with patch("netlicensing_mcp.tools.license_templates.nl_get", new=mock_get):
        from netlicensing_mcp.tools.license_templates import list_license_templates

        result = await list_license_templates("M01", filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"
        mock_get.assert_called_once_with(
            "/licensetemplate",
            {"productModuleNumber": "M01", "filter": "active=true"},
        )


@pytest.mark.asyncio
async def test_get_license_template(template_response):
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        new=AsyncMock(return_value=template_response),
    ):
        from netlicensing_mcp.tools.license_templates import get_license_template

        result = await get_license_template("LT01")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "LT01"
        assert props["licenseType"] == "TIMEVOLUME"


@pytest.mark.asyncio
async def test_create_license_template(template_response):
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_post",
        new=AsyncMock(return_value=template_response),
    ):
        from netlicensing_mcp.tools.license_templates import create_license_template

        result = await create_license_template("M01", "LT01", "Sub Template", "TIMEVOLUME")
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"


@pytest.mark.asyncio
async def test_create_license_template_all_fields(template_response):
    mock_post = AsyncMock(return_value=template_response)
    with patch("netlicensing_mcp.tools.license_templates.nl_post", new=mock_post):
        from netlicensing_mcp.tools.license_templates import create_license_template

        result = await create_license_template(
            "M01",
            "LT01",
            "Sub Template",
            "TIMEVOLUME",
            active=True,
            price=19.99,
            currency="USD",
            automatic=True,
            hidden=True,
            hide_licenses=True,
            time_volume=30,
            time_volume_period="DAY",
            max_sessions=5,
            quantity=100,
            grace_period=True,
        )
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"
        call_data = mock_post.call_args[0][1]
        assert call_data["productModuleNumber"] == "M01"
        assert call_data["number"] == "LT01"
        assert call_data["licenseType"] == "TIMEVOLUME"
        assert call_data["price"] == "19.99"
        assert call_data["currency"] == "USD"
        assert call_data["automatic"] == "true"
        assert call_data["hidden"] == "true"
        assert call_data["hideLicenses"] == "true"
        assert call_data["timeVolume"] == "30"
        assert call_data["timeVolumePeriod"] == "DAY"
        assert call_data["maxSessions"] == "5"
        assert call_data["quantity"] == "100"
        assert call_data["gracePeriod"] == "true"


@pytest.mark.asyncio
async def test_update_license_template(template_response):
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_post",
        new=AsyncMock(return_value=template_response),
    ):
        from netlicensing_mcp.tools.license_templates import update_license_template

        result = await update_license_template("LT01", name="Updated Template")
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"


@pytest.mark.asyncio
async def test_update_license_template_all_fields(template_response):
    mock_put = AsyncMock(return_value=template_response)
    with patch("netlicensing_mcp.tools.license_templates.nl_post", new=mock_put):
        from netlicensing_mcp.tools.license_templates import update_license_template

        result = await update_license_template(
            "LT01",
            name="Updated Template",
            active=False,
            price=29.99,
            currency="EUR",
            automatic=False,
            hidden=False,
            hide_licenses=True,
            time_volume=60,
            time_volume_period="MONTH",
            max_sessions=10,
            quantity=200,
            grace_period=False,
        )
        assert result["items"]["item"][0]["type"] == "LicenseTemplate"
        call_data = mock_put.call_args[0][1]
        assert call_data["name"] == "Updated Template"
        assert call_data["active"] == "false"
        assert call_data["price"] == "29.99"
        assert call_data["currency"] == "EUR"
        assert call_data["automatic"] == "false"
        assert call_data["hidden"] == "false"
        assert call_data["hideLicenses"] == "true"
        assert call_data["timeVolume"] == "60"
        assert call_data["timeVolumePeriod"] == "MONTH"
        assert call_data["maxSessions"] == "10"
        assert call_data["quantity"] == "200"
        assert call_data["gracePeriod"] == "false"


@pytest.mark.asyncio
async def test_delete_license_template():
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_delete", new=AsyncMock(return_value=204)
    ):
        from netlicensing_mcp.tools.license_templates import delete_license_template

        result = await delete_license_template("LT01")
        assert "LT01" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_license_template_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.license_templates.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.license_templates import delete_license_template

        result = await delete_license_template("LT01", force_cascade=True)
        assert "LT01" in result
        mock_delete.assert_called_once_with("/licensetemplate/LT01", {"forceCascade": "true"})


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
async def test_list_licensees_with_filter(licensee_response):
    mock_get = AsyncMock(return_value=licensee_response)
    with patch("netlicensing_mcp.tools.licensees.nl_get", new=mock_get):
        from netlicensing_mcp.tools.licensees import list_licensees

        result = await list_licensees("P001", filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "Licensee"
        mock_get.assert_called_once_with(
            "/licensee",
            {"productNumber": "P001", "filter": "active=true"},
        )


@pytest.mark.asyncio
async def test_get_licensee(licensee_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_get", new=AsyncMock(return_value=licensee_response)
    ):
        from netlicensing_mcp.tools.licensees import get_licensee

        result = await get_licensee("I001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "I001"
        assert props["name"] == "ACME Corp"


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
async def test_validate_licensee_all_params(validation_response):
    mock_post = AsyncMock(return_value=validation_response)
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.tools.licensees import validate_licensee

        result = await validate_licensee(
            "I001",
            product_number="P001",
            licensee_name="ACME Corp",
            product_module_number="M01",
            node_secret="secret123",
            session_id="sess-42",
            action="checkOut",
        )
        assert result["items"]["item"][0]["type"] == "ProductModuleValidation"
        call_data = mock_post.call_args[0][1]
        assert call_data["productNumber"] == "P001"
        assert call_data["licenseeName"] == "ACME Corp"
        assert call_data["productModuleNumber"] == "M01"
        assert call_data["nodeSecret"] == "secret123"
        assert call_data["sessionId"] == "sess-42"
        assert call_data["action"] == "checkOut"


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
async def test_create_licensee_all_fields(licensee_response):
    mock_post = AsyncMock(return_value=licensee_response)
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.tools.licensees import create_licensee

        result = await create_licensee(
            "P001",
            number="I001",
            name="ACME Corp",
            active=True,
            marked_for_transfer=True,
            licensee_secret="s3cret",
        )
        assert result["items"]["item"][0]["type"] == "Licensee"
        call_data = mock_post.call_args[0][1]
        assert call_data["productNumber"] == "P001"
        assert call_data["number"] == "I001"
        assert call_data["name"] == "ACME Corp"
        assert call_data["active"] == "true"
        assert call_data["markedForTransfer"] == "true"
        assert call_data["licenseeSecret"] == "s3cret"


@pytest.mark.asyncio
async def test_update_licensee(licensee_response):
    with patch(
        "netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=licensee_response)
    ):
        from netlicensing_mcp.tools.licensees import update_licensee

        result = await update_licensee("I001", name="ACME Corp Updated")
        assert result["items"]["item"][0]["type"] == "Licensee"


@pytest.mark.asyncio
async def test_update_licensee_all_fields(licensee_response):
    mock_put = AsyncMock(return_value=licensee_response)
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_put):
        from netlicensing_mcp.tools.licensees import update_licensee

        result = await update_licensee(
            "I001",
            name="ACME Updated",
            active=False,
            marked_for_transfer=True,
            licensee_secret="new-secret",
        )
        assert result["items"]["item"][0]["type"] == "Licensee"
        call_data = mock_put.call_args[0][1]
        assert call_data["name"] == "ACME Updated"
        assert call_data["active"] == "false"
        assert call_data["markedForTransfer"] == "true"
        assert call_data["licenseeSecret"] == "new-secret"


@pytest.mark.asyncio
async def test_delete_licensee():
    with patch("netlicensing_mcp.tools.licensees.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.licensees import delete_licensee

        result = await delete_licensee("I001")
        assert "I001" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_licensee_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.licensees.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.licensees import delete_licensee

        result = await delete_licensee("I001", force_cascade=True)
        assert "I001" in result
        mock_delete.assert_called_once_with("/licensee/I001", {"forceCascade": "true"})


@pytest.mark.asyncio
async def test_transfer_licenses(licensee_response):
    mock_post = AsyncMock(return_value=licensee_response)
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.tools.licensees import transfer_licenses

        result = await transfer_licenses("I001", "I002")
        assert "item" in result["items"]
        mock_post.assert_called_once_with(
            "/licensee/I002/transfer",
            {"sourceLicenseeNumber": "I001"},
        )


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
async def test_list_licenses_with_filter(license_response):
    mock_get = AsyncMock(return_value=license_response)
    with patch("netlicensing_mcp.tools.licenses.nl_get", new=mock_get):
        from netlicensing_mcp.tools.licenses import list_licenses

        result = await list_licenses("I001", filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "License"
        mock_get.assert_called_once_with(
            "/license",
            {"licenseeNumber": "I001", "filter": "active=true"},
        )


@pytest.mark.asyncio
async def test_get_license(license_response):
    with patch(
        "netlicensing_mcp.tools.licenses.nl_get", new=AsyncMock(return_value=license_response)
    ):
        from netlicensing_mcp.tools.licenses import get_license

        result = await get_license("L001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "L001"


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
async def test_create_license_all_fields(license_response):
    mock_post = AsyncMock(return_value=license_response)
    with patch("netlicensing_mcp.tools.licenses.nl_post", new=mock_post):
        from netlicensing_mcp.tools.licenses import create_license

        result = await create_license(
            "I001",
            "LT01",
            number="L001",
            active=True,
            name="My License",
            start_date="2025-01-01T00:00:00Z",
            price=9.99,
            currency="USD",
            time_volume="30",
            time_volume_period="DAY",
            quantity="100",
            parent_feature="F01",
            hidden=True,
        )
        assert result["items"]["item"][0]["type"] == "License"
        call_data = mock_post.call_args[0][1]
        assert call_data["licenseeNumber"] == "I001"
        assert call_data["licenseTemplateNumber"] == "LT01"
        assert call_data["number"] == "L001"
        assert call_data["active"] == "true"
        assert call_data["name"] == "My License"
        assert call_data["startDate"] == "2025-01-01T00:00:00Z"
        assert call_data["price"] == "9.99"
        assert call_data["currency"] == "USD"
        assert call_data["timeVolume"] == "30"
        assert call_data["timeVolumePeriod"] == "DAY"
        assert call_data["quantity"] == "100"
        assert call_data["parentfeature"] == "F01"
        assert call_data["hidden"] == "true"


@pytest.mark.asyncio
async def test_update_license_deactivate(license_response):
    deactivated = dict(license_response)
    deactivated["items"]["item"][0]["property"][1]["value"] = "false"
    with patch("netlicensing_mcp.tools.licenses.nl_post", new=AsyncMock(return_value=deactivated)):
        from netlicensing_mcp.tools.licenses import update_license

        result = await update_license("L001", active=False)
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["active"] == "false"


@pytest.mark.asyncio
async def test_update_license_all_fields(license_response):
    mock_put = AsyncMock(return_value=license_response)
    with patch("netlicensing_mcp.tools.licenses.nl_post", new=mock_put):
        from netlicensing_mcp.tools.licenses import update_license

        result = await update_license(
            "L001",
            active=False,
            name="Updated License",
            start_date="2025-06-01T00:00:00Z",
            price=19.99,
            currency="EUR",
            time_volume="60",
            time_volume_period="MONTH",
            quantity="200",
            used_quantity="50",
            parent_feature="F02",
            hidden=False,
        )
        assert result["items"]["item"][0]["type"] == "License"
        call_data = mock_put.call_args[0][1]
        assert call_data["active"] == "false"
        assert call_data["name"] == "Updated License"
        assert call_data["startDate"] == "2025-06-01T00:00:00Z"
        assert call_data["price"] == "19.99"
        assert call_data["currency"] == "EUR"
        assert call_data["timeVolume"] == "60"
        assert call_data["timeVolumePeriod"] == "MONTH"
        assert call_data["quantity"] == "200"
        assert call_data["usedQuantity"] == "50"
        assert call_data["parentfeature"] == "F02"
        assert call_data["hidden"] == "false"


@pytest.mark.asyncio
async def test_delete_license():
    with patch("netlicensing_mcp.tools.licenses.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.licenses import delete_license

        result = await delete_license("L001")
        assert "L001" in result
        assert "204" in result


@pytest.mark.asyncio
async def test_delete_license_force_cascade():
    mock_delete = AsyncMock(return_value=204)
    with patch("netlicensing_mcp.tools.licenses.nl_delete", new=mock_delete):
        from netlicensing_mcp.tools.licenses import delete_license

        result = await delete_license("L001", force_cascade=True)
        assert "L001" in result
        mock_delete.assert_called_once_with("/license/L001", {"forceCascade": "true"})


# ── Tokens ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tokens(shop_token_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_get", new=AsyncMock(return_value=shop_token_response)
    ):
        from netlicensing_mcp.tools.tokens import list_tokens

        result = await list_tokens()
        assert result["items"]["item"][0]["type"] == "Token"


@pytest.mark.asyncio
async def test_list_tokens_with_filter(shop_token_response):
    mock_get = AsyncMock(return_value=shop_token_response)
    with patch("netlicensing_mcp.tools.tokens.nl_get", new=mock_get):
        from netlicensing_mcp.tools.tokens import list_tokens

        result = await list_tokens(filter_str="tokenType=SHOP")
        assert result["items"]["item"][0]["type"] == "Token"
        mock_get.assert_called_once_with("/token", {"filter": "tokenType=SHOP"})


@pytest.mark.asyncio
async def test_get_token(shop_token_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_get", new=AsyncMock(return_value=shop_token_response)
    ):
        from netlicensing_mcp.tools.tokens import get_token

        result = await get_token("TK001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "TK001"


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
async def test_create_shop_token_all_fields(shop_token_response):
    mock_post = AsyncMock(return_value=shop_token_response)
    with patch("netlicensing_mcp.tools.tokens.nl_post", new=mock_post):
        from netlicensing_mcp.tools.tokens import create_shop_token

        result = await create_shop_token(
            "I001",
            product_number="P001",
            license_template_number="LT01",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            success_url_title="Back to App",
            cancel_url_title="Return",
        )
        assert result["items"]["item"][0]["type"] == "Token"
        call_data = mock_post.call_args[0][1]
        assert call_data["tokenType"] == "SHOP"
        assert call_data["licenseeNumber"] == "I001"
        assert call_data["productNumber"] == "P001"
        assert call_data["licenseTemplateNumber"] == "LT01"
        assert call_data["successURL"] == "https://example.com/success"
        assert call_data["cancelURL"] == "https://example.com/cancel"
        assert call_data["successURLTitle"] == "Back to App"
        assert call_data["cancelURLTitle"] == "Return"


@pytest.mark.asyncio
async def test_create_api_token(api_token_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_post", new=AsyncMock(return_value=api_token_response)
    ):
        from netlicensing_mcp.tools.tokens import create_api_token

        result = await create_api_token(api_key_role="ROLE_APIKEY_ANALYTICS")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["role"] == "ROLE_APIKEY_ANALYTICS"


@pytest.mark.asyncio
async def test_create_api_token_with_licensee(api_token_response):
    mock_post = AsyncMock(return_value=api_token_response)
    with patch("netlicensing_mcp.tools.tokens.nl_post", new=mock_post):
        from netlicensing_mcp.tools.tokens import create_api_token

        result = await create_api_token(
            api_key_role="ROLE_APIKEY_LICENSEE",
            licensee_number="I001",
        )
        assert result["items"]["item"][0]["type"] == "Token"
        call_data = mock_post.call_args[0][1]
        assert call_data["tokenType"] == "APIKEY"
        assert call_data["apiKeyRole"] == "ROLE_APIKEY_LICENSEE"
        assert call_data["licenseeNumber"] == "I001"


@pytest.mark.asyncio
async def test_delete_token():
    with patch("netlicensing_mcp.tools.tokens.nl_delete", new=AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.tokens import delete_token

        result = await delete_token("TK001")
        assert "TK001" in result
        assert "204" in result


# ── Error handling ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_handling():
    """Verify that NetLicensingError is raised on non-2xx responses."""
    from netlicensing_mcp.client import NetLicensingError

    with patch(
        "netlicensing_mcp.tools.products.nl_get",
        new=AsyncMock(side_effect=NetLicensingError(404, "Product not found")),
    ):
        from netlicensing_mcp.tools.products import get_product

        with pytest.raises(NetLicensingError) as exc_info:
            await get_product("NONEXISTENT")
        assert exc_info.value.status_code == 404
        assert "Product not found" in exc_info.value.detail


# ── Transactions ──────────────────────────────────────────────────────────────


@pytest.fixture
def transaction_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Transaction",
                    "property": [
                        {"name": "number", "value": "TX001"},
                        {"name": "status", "value": "CLOSED"},
                        {"name": "source", "value": "SHOP"},
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_list_transactions(transaction_response):
    with patch(
        "netlicensing_mcp.tools.transactions.nl_get",
        new=AsyncMock(return_value=transaction_response),
    ):
        from netlicensing_mcp.tools.transactions import list_transactions

        result = await list_transactions()
        assert result["items"]["item"][0]["type"] == "Transaction"


@pytest.mark.asyncio
async def test_list_transactions_with_filter(transaction_response):
    mock_get = AsyncMock(return_value=transaction_response)
    with patch("netlicensing_mcp.tools.transactions.nl_get", new=mock_get):
        from netlicensing_mcp.tools.transactions import list_transactions

        result = await list_transactions(filter_str="status=CLOSED")
        assert result["items"]["item"][0]["type"] == "Transaction"
        mock_get.assert_called_once_with("/transaction", {"filter": "status=CLOSED"})


@pytest.mark.asyncio
async def test_get_transaction(transaction_response):
    with patch(
        "netlicensing_mcp.tools.transactions.nl_get",
        new=AsyncMock(return_value=transaction_response),
    ):
        from netlicensing_mcp.tools.transactions import get_transaction

        result = await get_transaction("TX001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "TX001"
        assert props["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_create_transaction(transaction_response):
    with patch(
        "netlicensing_mcp.tools.transactions.nl_post",
        new=AsyncMock(return_value=transaction_response),
    ):
        from netlicensing_mcp.tools.transactions import create_transaction

        result = await create_transaction("CLOSED", "SHOP")
        assert result["items"]["item"][0]["type"] == "Transaction"


@pytest.mark.asyncio
async def test_create_transaction_all_fields(transaction_response):
    mock_post = AsyncMock(return_value=transaction_response)
    with patch("netlicensing_mcp.tools.transactions.nl_post", new=mock_post):
        from netlicensing_mcp.tools.transactions import create_transaction

        result = await create_transaction(
            "CLOSED",
            "SHOP",
            licensee_number="I001",
            number="TX001",
            name="Order #42",
            active=True,
            date_created="2025-01-01T00:00:00Z",
            date_closed="2025-01-02T00:00:00Z",
            payment_method="PM001",
        )
        assert result["items"]["item"][0]["type"] == "Transaction"
        call_data = mock_post.call_args[0][1]
        assert call_data["status"] == "CLOSED"
        assert call_data["source"] == "SHOP"
        assert call_data["licenseeNumber"] == "I001"
        assert call_data["number"] == "TX001"
        assert call_data["name"] == "Order #42"
        assert call_data["active"] == "true"
        assert call_data["dateCreated"] == "2025-01-01T00:00:00Z"
        assert call_data["dateClosed"] == "2025-01-02T00:00:00Z"
        assert call_data["paymentMethod"] == "PM001"


@pytest.mark.asyncio
async def test_update_transaction(transaction_response):
    with patch(
        "netlicensing_mcp.tools.transactions.nl_post",
        new=AsyncMock(return_value=transaction_response),
    ):
        from netlicensing_mcp.tools.transactions import update_transaction

        result = await update_transaction("TX001", status="CLOSED")
        assert result["items"]["item"][0]["type"] == "Transaction"


@pytest.mark.asyncio
async def test_update_transaction_all_fields(transaction_response):
    mock_post = AsyncMock(return_value=transaction_response)
    with patch("netlicensing_mcp.tools.transactions.nl_post", new=mock_post):
        from netlicensing_mcp.tools.transactions import update_transaction

        result = await update_transaction(
            "TX001",
            status="CANCELLED",
            active=False,
            name="Cancelled Order",
            date_closed="2025-03-01T00:00:00Z",
            payment_method="PM002",
        )
        assert result["items"]["item"][0]["type"] == "Transaction"
        call_data = mock_post.call_args[0][1]
        assert call_data["status"] == "CANCELLED"
        assert call_data["active"] == "false"
        assert call_data["name"] == "Cancelled Order"
        assert call_data["dateClosed"] == "2025-03-01T00:00:00Z"
        assert call_data["paymentMethod"] == "PM002"


# ── Payment Methods ───────────────────────────────────────────────────────────


@pytest.fixture
def payment_method_response():
    return {
        "items": {
            "item": [
                {
                    "type": "PaymentMethod",
                    "property": [
                        {"name": "number", "value": "PM001"},
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_list_payment_methods(payment_method_response):
    with patch(
        "netlicensing_mcp.tools.payment_methods.nl_get",
        new=AsyncMock(return_value=payment_method_response),
    ):
        from netlicensing_mcp.tools.payment_methods import list_payment_methods

        result = await list_payment_methods()
        assert result["items"]["item"][0]["type"] == "PaymentMethod"


@pytest.mark.asyncio
async def test_list_payment_methods_with_filter(payment_method_response):
    mock_get = AsyncMock(return_value=payment_method_response)
    with patch("netlicensing_mcp.tools.payment_methods.nl_get", new=mock_get):
        from netlicensing_mcp.tools.payment_methods import list_payment_methods

        result = await list_payment_methods(filter_str="active=true")
        assert result["items"]["item"][0]["type"] == "PaymentMethod"
        mock_get.assert_called_once_with("/paymentmethod", {"filter": "active=true"})


@pytest.mark.asyncio
async def test_get_payment_method(payment_method_response):
    with patch(
        "netlicensing_mcp.tools.payment_methods.nl_get",
        new=AsyncMock(return_value=payment_method_response),
    ):
        from netlicensing_mcp.tools.payment_methods import get_payment_method

        result = await get_payment_method("PM001")
        props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
        assert props["number"] == "PM001"


@pytest.mark.asyncio
async def test_update_payment_method(payment_method_response):
    with patch(
        "netlicensing_mcp.tools.payment_methods.nl_post",
        new=AsyncMock(return_value=payment_method_response),
    ):
        from netlicensing_mcp.tools.payment_methods import update_payment_method

        result = await update_payment_method("PM001", active=True)
        assert result["items"]["item"][0]["type"] == "PaymentMethod"


@pytest.mark.asyncio
async def test_update_payment_method_all_fields(payment_method_response):
    mock_post = AsyncMock(return_value=payment_method_response)
    with patch("netlicensing_mcp.tools.payment_methods.nl_post", new=mock_post):
        from netlicensing_mcp.tools.payment_methods import update_payment_method

        result = await update_payment_method(
            "PM001",
            active=True,
            paypal_subject="vendor@example.com",
        )
        assert result["items"]["item"][0]["type"] == "PaymentMethod"
        call_data = mock_post.call_args[0][1]
        assert call_data["active"] == "true"
        assert call_data["paypal.subject"] == "vendor@example.com"


# ── Utilities ─────────────────────────────────────────────────────────────────


@pytest.fixture
def utility_response():
    return {
        "items": {
            "item": [
                {
                    "type": "LicensingModelProperties",
                    "property": [
                        {"name": "name", "value": "Subscription"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_list_licensing_models(utility_response):
    mock_get = AsyncMock(return_value=utility_response)
    with patch("netlicensing_mcp.tools.utilities.nl_get", new=mock_get):
        from netlicensing_mcp.tools.utilities import list_licensing_models

        result = await list_licensing_models()
        assert "items" in result
        mock_get.assert_called_once_with("/utility/licensingModels")


@pytest.mark.asyncio
async def test_list_license_types(utility_response):
    mock_get = AsyncMock(return_value=utility_response)
    with patch("netlicensing_mcp.tools.utilities.nl_get", new=mock_get):
        from netlicensing_mcp.tools.utilities import list_license_types

        result = await list_license_types()
        assert "items" in result
        mock_get.assert_called_once_with("/utility/licenseTypes")


@pytest.mark.asyncio
async def test_list_countries(utility_response):
    mock_get = AsyncMock(return_value=utility_response)
    with patch("netlicensing_mcp.tools.utilities.nl_get", new=mock_get):
        from netlicensing_mcp.tools.utilities import list_countries

        result = await list_countries()
        assert "items" in result
        mock_get.assert_called_once_with("/utility/countries")


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
                if fn.__name__ == "audit_full":
                    msgs = fn("P001")
                    captured["text"] = msgs[0].content.text
                return fn

            return decorator

    server = CaptureMCP("test")
    register_audit_prompts(server)

    if captured:
        assert "P001" in captured["text"]
        assert "Step 1" in captured["text"]
        assert "online license and" in captured["text"]
        assert "entitlements management system" in captured["text"]


def test_server_instructions_positioning():
    from netlicensing_mcp.server import mcp

    assert "online license and entitlements management system" in (mcp.instructions or "")
