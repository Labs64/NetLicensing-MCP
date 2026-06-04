"""Tests for P0.4: Destructive-operation safety — preview + confirmation tokens."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp import safety


@pytest.fixture(autouse=True)
def clear_token_store():
    safety._store.clear()
    yield
    safety._store.clear()


# ─── Unit: token store ────────────────────────────────────────────────────────


def test_issue_token_format():
    token, expires_at = safety.issue_token("delete_product", "P001")
    assert token.startswith("CONF-")
    assert isinstance(expires_at, datetime)
    assert expires_at.tzinfo is not None


def test_issue_token_expires_in_5_minutes():
    _, expires_at = safety.issue_token("delete_product", "P001")
    delta = expires_at - datetime.now(timezone.utc)
    assert timedelta(minutes=4, seconds=55) < delta <= timedelta(minutes=5, seconds=5)


def test_issue_token_unique_for_same_target():
    t1, _ = safety.issue_token("delete_product", "P001")
    t2, _ = safety.issue_token("delete_product", "P001")
    assert t1 != t2


def test_second_issue_invalidates_first():
    t1, _ = safety.issue_token("delete_product", "P001")
    safety.issue_token("delete_product", "P001")
    with pytest.raises(ValueError, match="Invalid"):
        safety.validate_and_consume(t1, "delete_product", "P001")


def test_validate_and_consume_success():
    token, _ = safety.issue_token("delete_product", "P001")
    safety.validate_and_consume(token, "delete_product", "P001")  # must not raise


def test_validate_wrong_operation():
    token, _ = safety.issue_token("delete_product", "P001")
    with pytest.raises(ValueError):
        safety.validate_and_consume(token, "delete_licensee", "P001")


def test_validate_wrong_target():
    token, _ = safety.issue_token("delete_product", "P001")
    with pytest.raises(ValueError):
        safety.validate_and_consume(token, "delete_product", "P002")


def test_validate_single_use():
    token, _ = safety.issue_token("delete_product", "P001")
    safety.validate_and_consume(token, "delete_product", "P001")
    with pytest.raises(ValueError, match="Invalid"):
        safety.validate_and_consume(token, "delete_product", "P001")


def test_validate_expired():
    token = "CONF-P001XXXX-TEST"
    safety._store[token] = (
        "delete_product",
        "P001",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="expired"):
        safety.validate_and_consume(token, "delete_product", "P001")


def test_validate_unknown_token():
    with pytest.raises(ValueError, match="Invalid"):
        safety.validate_and_consume("CONF-NOSUCH01-XXXX", "delete_product", "P001")


# ─── Unit: preview builders ───────────────────────────────────────────────────


def test_make_delete_preview_shape():
    preview = safety.make_delete_preview(
        "delete_product",
        "P001",
        affected={"product_modules": 2, "licensees": 5},
        samples={"licensees": ["I001", "I002"]},
    )
    assert preview["operation"] == "delete_product"
    assert preview["target"] == "P001"
    assert "confirmation_token" in preview
    assert "expires_at" in preview
    assert "instructions" in preview
    assert preview["affected"]["product_modules"] == 2
    # The token must be consumable once
    safety.validate_and_consume(preview["confirmation_token"], "delete_product", "P001")


def test_make_update_preview_shape():
    preview = safety.make_update_preview(
        "update_license_template",
        "LT01",
        diff=[{"field": "price", "from": "9.99", "to": "19.99"}],
    )
    assert preview["operation"] == "update_license_template"
    assert preview["target"] == "LT01"
    assert "confirmation_token" in preview
    assert "expires_at" in preview
    assert preview["changes"][0]["field"] == "price"
    safety.validate_and_consume(preview["confirmation_token"], "update_license_template", "LT01")


# ─── Acceptance: server-level delete behavior ────────────────────────────────


@pytest.fixture
def empty_items():
    return {"items": {"item": []}}


@pytest.fixture
def modules_one():
    return {
        "items": {
            "item": [
                {
                    "type": "ProductModule",
                    "property": [{"name": "number", "value": "M01"}],
                }
            ]
        }
    }


@pytest.fixture
def licenses_one():
    return {
        "items": {
            "item": [
                {
                    "type": "License",
                    "property": [{"name": "number", "value": "L001"}],
                }
            ]
        }
    }


@pytest.fixture
def templates_one():
    return {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [{"name": "number", "value": "LT01"}],
                }
            ]
        }
    }


@pytest.fixture
def apikey_token_resp():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "TK001"},
                        {"name": "tokenType", "value": "APIKEY"},
                        {"name": "role", "value": "ROLE_APIKEY_ADMIN"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def shop_token_resp():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "TK002"},
                        {"name": "tokenType", "value": "SHOP"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_delete_product_returns_preview_when_has_modules(modules_one, empty_items):
    """delete_product without token on populated product returns preview, not deletion."""
    with (
        patch(
            "netlicensing_mcp.tools.product_modules.nl_get",
            AsyncMock(return_value=modules_one),
        ),
        patch(
            "netlicensing_mcp.tools.licensees.nl_get",
            AsyncMock(return_value=empty_items),
        ),
    ):
        from netlicensing_mcp.server import netlicensing_delete_product

        result = json.loads(await netlicensing_delete_product("P001"))
        assert result["operation"] == "delete_product"
        assert result["target"] == "P001"
        assert "confirmation_token" in result
        assert result["affected"]["product_modules"] == 1


@pytest.mark.asyncio
async def test_delete_product_always_requires_confirmation(empty_items):
    """delete_product without token always returns preview — even for products with no dependents."""
    with (
        patch(
            "netlicensing_mcp.tools.product_modules.nl_get",
            AsyncMock(return_value=empty_items),
        ),
        patch(
            "netlicensing_mcp.tools.licensees.nl_get",
            AsyncMock(return_value=empty_items),
        ),
    ):
        from netlicensing_mcp.server import netlicensing_delete_product

        result = json.loads(await netlicensing_delete_product("P001"))
        assert result["operation"] == "delete_product"
        assert "confirmation_token" in result
        assert result["affected"]["product_modules"] == 0
        assert result["affected"]["licensees"] == 0


@pytest.mark.asyncio
async def test_delete_product_with_valid_token_executes():
    """delete_product with valid confirm_token executes without dependent-check."""
    token, _ = safety.issue_token("delete_product", "P001")
    with patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=200)):
        from netlicensing_mcp.server import netlicensing_delete_product

        result = await netlicensing_delete_product("P001", confirm_token=token)
        assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_delete_product_invalid_token_returns_error():
    """delete_product with invalid confirm_token returns a structured error."""
    from netlicensing_mcp.server import netlicensing_delete_product

    result = json.loads(
        await netlicensing_delete_product("P001", confirm_token="CONF-FAKEFAKE-XXXX")
    )
    assert result.get("error") is True
    assert "Invalid" in result.get("detail", "")


@pytest.mark.asyncio
async def test_delete_product_token_not_reusable():
    """Supplying a confirmation token a second time returns an error."""
    token, _ = safety.issue_token("delete_product", "P001")
    with patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=200)):
        from netlicensing_mcp.server import netlicensing_delete_product

        r1 = await netlicensing_delete_product("P001", confirm_token=token)
        assert "deleted" in r1.lower()

        r2 = json.loads(await netlicensing_delete_product("P001", confirm_token=token))
        assert r2.get("error") is True


@pytest.mark.asyncio
async def test_preview_delete_product_always_returns_preview(modules_one, empty_items):
    """netlicensing_preview_delete_product always returns a preview with token."""
    with (
        patch(
            "netlicensing_mcp.tools.product_modules.nl_get",
            AsyncMock(return_value=modules_one),
        ),
        patch(
            "netlicensing_mcp.tools.licensees.nl_get",
            AsyncMock(return_value=empty_items),
        ),
    ):
        from netlicensing_mcp.server import netlicensing_preview_delete_product

        result = json.loads(await netlicensing_preview_delete_product("P001"))
        assert result["operation"] == "delete_product"
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_delete_licensee_returns_preview_when_has_licenses(licenses_one):
    """delete_licensee without token returns preview when licensee has licenses."""
    with patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=licenses_one)):
        from netlicensing_mcp.server import netlicensing_delete_licensee

        result = json.loads(await netlicensing_delete_licensee("I001"))
        assert result["operation"] == "delete_licensee"
        assert result["affected"]["licenses"] == 1
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_delete_licensee_always_requires_confirmation(empty_items):
    """delete_licensee without token always returns preview — even when licensee has no licenses."""
    with patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=empty_items)):
        from netlicensing_mcp.server import netlicensing_delete_licensee

        result = json.loads(await netlicensing_delete_licensee("I001"))
        assert result["operation"] == "delete_licensee"
        assert "confirmation_token" in result
        assert result["affected"]["licenses"] == 0


@pytest.mark.asyncio
async def test_delete_product_module_always_requires_confirmation(empty_items):
    """delete_product_module without token always returns preview — even for empty modules."""
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        AsyncMock(return_value=empty_items),
    ):
        from netlicensing_mcp.server import netlicensing_delete_product_module

        result = json.loads(await netlicensing_delete_product_module("M01"))
        assert result["operation"] == "delete_product_module"
        assert result["affected"]["license_templates"] == 0
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_delete_license_template_always_requires_confirmation():
    """delete_license_template without token always returns preview (cannot cheaply
    check for dependent licenses without enumerating all licensees)."""
    template_resp = {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [
                        {"name": "number", "value": "LT01"},
                        {"name": "name", "value": "Standard"},
                        {"name": "price", "value": "9.99"},
                    ],
                }
            ]
        }
    }
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        AsyncMock(return_value=template_resp),
    ):
        from netlicensing_mcp.server import netlicensing_delete_license_template

        result = json.loads(await netlicensing_delete_license_template("LT01"))
        assert result["operation"] == "delete_license_template"
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_delete_token_apikey_requires_confirmation(apikey_token_resp):
    """delete_token without token returns preview for APIKEY tokens."""
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=apikey_token_resp)):
        from netlicensing_mcp.server import netlicensing_delete_token

        result = json.loads(await netlicensing_delete_token("TK001"))
        assert result["operation"] == "delete_token"
        assert "APIKEY" in str(result.get("affected", {}))
        assert "confirmation_token" in result


@pytest.fixture
def bundle_resp():
    return {
        "items": {
            "item": [
                {
                    "type": "Bundle",
                    "property": [
                        {"name": "number", "value": "B001"},
                        {"name": "name", "value": "Starter Pack"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def license_resp():
    return {
        "items": {
            "item": [
                {
                    "type": "License",
                    "property": [
                        {"name": "number", "value": "L001"},
                        {"name": "licenseeNumber", "value": "I001"},
                        {"name": "licenseTemplateNumber", "value": "LT01"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_delete_bundle_always_requires_confirmation(bundle_resp):
    """delete_bundle without token always returns preview."""
    with patch("netlicensing_mcp.tools.bundles.nl_get", AsyncMock(return_value=bundle_resp)):
        from netlicensing_mcp.server import netlicensing_delete_bundle

        result = json.loads(await netlicensing_delete_bundle("B001"))
        assert result["operation"] == "delete_bundle"
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_delete_bundle_with_valid_token_executes(bundle_resp):
    """delete_bundle executes when a valid confirm_token is supplied."""
    token, _ = safety.issue_token("delete_bundle", "B001")
    with (
        patch("netlicensing_mcp.tools.bundles.nl_get", AsyncMock(return_value=bundle_resp)),
        patch("netlicensing_mcp.tools.bundles.nl_delete", AsyncMock(return_value=200)),
    ):
        from netlicensing_mcp.server import netlicensing_delete_bundle

        result = await netlicensing_delete_bundle("B001", confirm_token=token)
        assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_delete_license_always_requires_confirmation(license_resp):
    """delete_license without token always returns preview."""
    with patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=license_resp)):
        from netlicensing_mcp.server import netlicensing_delete_license

        result = json.loads(await netlicensing_delete_license("L001"))
        assert result["operation"] == "delete_license"
        assert "confirmation_token" in result
        assert result["samples"]["licensee"] == "I001"


@pytest.mark.asyncio
async def test_delete_license_with_valid_token_executes(license_resp):
    """delete_license executes when a valid confirm_token is supplied."""
    token, _ = safety.issue_token("delete_license", "L001")
    with (
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=license_resp)),
        patch("netlicensing_mcp.tools.licenses.nl_delete", AsyncMock(return_value=200)),
    ):
        from netlicensing_mcp.server import netlicensing_delete_license

        result = await netlicensing_delete_license("L001", confirm_token=token)
        assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_delete_licensee_with_valid_token_executes():
    """delete_licensee executes when a valid confirm_token is supplied."""
    token, _ = safety.issue_token("delete_licensee", "I001")
    with patch("netlicensing_mcp.tools.licensees.nl_delete", AsyncMock(return_value=200)):
        from netlicensing_mcp.server import netlicensing_delete_licensee

        result = await netlicensing_delete_licensee("I001", confirm_token=token)
        assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_delete_token_always_requires_confirmation(shop_token_resp):
    """delete_token without token always returns preview — for both SHOP and APIKEY tokens."""
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=shop_token_resp)):
        from netlicensing_mcp.server import netlicensing_delete_token

        result = json.loads(await netlicensing_delete_token("TK002"))
        assert result["operation"] == "delete_token"
        assert "confirmation_token" in result
        assert result["affected"]["token_type"] == "SHOP"


@pytest.mark.asyncio
async def test_delete_token_shop_executes_with_valid_token(shop_token_resp):
    """delete_token executes for SHOP tokens when a valid confirm_token is supplied."""
    token, _ = safety.issue_token("delete_token", "TK002")
    with (
        patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=shop_token_resp)),
        patch("netlicensing_mcp.tools.tokens.nl_delete", AsyncMock(return_value=200)),
    ):
        from netlicensing_mcp.server import netlicensing_delete_token

        result = await netlicensing_delete_token("TK002", confirm_token=token)
        assert "deleted" in result.lower()


# ─── Acceptance: server-level update behavior ─────────────────────────────────


@pytest.fixture
def template_resp_with_price():
    return {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [
                        {"name": "number", "value": "LT01"},
                        {"name": "price", "value": "9.99"},
                        {"name": "currency", "value": "EUR"},
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_update_license_template_sensitive_field_requires_confirmation(
    template_resp_with_price,
):
    """update_license_template changing price without token returns a preview."""
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        AsyncMock(return_value=template_resp_with_price),
    ):
        from netlicensing_mcp.server import netlicensing_update_license_template

        result = json.loads(await netlicensing_update_license_template("LT01", price=19.99))
        assert result["operation"] == "update_license_template"
        assert "changes" in result
        price_change = next((c for c in result["changes"] if c["field"] == "price"), None)
        assert price_change is not None
        assert price_change["to"] == "19.99"
        assert "confirmation_token" in result


@pytest.mark.asyncio
async def test_update_license_template_with_valid_token_executes():
    """update_license_template with valid token and sensitive field executes the update."""
    token, _ = safety.issue_token("update_license_template", "LT01")
    updated = {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [
                        {"name": "number", "value": "LT01"},
                        {"name": "price", "value": "19.99"},
                    ],
                }
            ]
        }
    }
    with patch("netlicensing_mcp.tools.license_templates.nl_post", AsyncMock(return_value=updated)):
        from netlicensing_mcp.server import netlicensing_update_license_template

        result = json.loads(
            await netlicensing_update_license_template("LT01", price=19.99, confirm_token=token)
        )
        assert "confirmation_token" not in result


@pytest.mark.asyncio
async def test_update_license_template_non_sensitive_executes_directly():
    """update_license_template changing name (non-sensitive) executes without token."""
    updated = {
        "items": {
            "item": [
                {
                    "type": "LicenseTemplate",
                    "property": [
                        {"name": "number", "value": "LT01"},
                        {"name": "name", "value": "New Name"},
                    ],
                }
            ]
        }
    }
    with patch("netlicensing_mcp.tools.license_templates.nl_post", AsyncMock(return_value=updated)):
        from netlicensing_mcp.server import netlicensing_update_license_template

        result = json.loads(await netlicensing_update_license_template("LT01", name="New Name"))
        assert "confirmation_token" not in result
