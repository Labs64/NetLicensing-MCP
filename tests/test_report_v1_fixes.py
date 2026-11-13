"""Regression tests for the MCP defects M1–M8 in REPORT_v1.0.md, section 6."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import netlicensing_mcp.client as client
from netlicensing_mcp import safety
from netlicensing_mcp.client import NetLicensingError


def _item(type_: str, **props: str) -> dict:
    return {
        "type": type_,
        "property": [{"name": k, "value": v} for k, v in props.items()],
    }


def scoped_filter(*args, **kwargs):
    from netlicensing_mcp.tools.helpers import scoped_filter as impl

    return impl(*args, **kwargs)


def _resp(*items: dict, **meta: str) -> dict:
    return {"items": {"item": list(items), **meta}}


@pytest.fixture(autouse=True)
def _clear_tokens():
    safety._store.clear()
    yield
    safety._store.clear()


# ── M1: list tools must scope to the parent through `filter` ─────────────────


@pytest.mark.parametrize(
    ("module", "func", "path", "key"),
    [
        ("licensees", "list_licensees", "/licensee", "productNumber"),
        ("product_modules", "list_product_modules", "/productmodule", "productNumber"),
        ("license_templates", "list_license_templates", "/licensetemplate", "productModuleNumber"),
        ("licenses", "list_licenses", "/license", "licenseeNumber"),
    ],
)
async def test_m1_unpaged_list_scopes_via_filter(module, func, path, key):
    mock_get = AsyncMock(return_value=_resp())
    with patch(f"netlicensing_mcp.tools.{module}.nl_get", new=mock_get):
        mod = __import__(f"netlicensing_mcp.tools.{module}", fromlist=[func])
        await getattr(mod, func)("X1")
    # A bare `?productNumber=X1` is ignored by the API and returns the whole account.
    mock_get.assert_called_once_with(path, {"filter": f"{key}=X1"})


def test_m1_scoped_filter_combines_paging_and_user_filter():
    assert scoped_filter("productNumber", "P1", "active=true", 0, 100) == {
        "filter": "productNumber=P1;page=0;items=100;active=true"
    }


@pytest.mark.parametrize("value", ["", "P1;licenseeNumber=X", "P1=2"])
def test_m1_scoped_filter_rejects_scope_breakout(value):
    with pytest.raises(NetLicensingError) as e:
        scoped_filter("productNumber", value)
    assert e.value.status_code == 400


def test_m1_scoped_filter_rejects_overriding_scope_key():
    with pytest.raises(NetLicensingError):
        scoped_filter("productNumber", "P1", "active=true; productNumber=OTHER")


async def test_m1_list_tool_returns_error_json_on_bad_filter():
    from netlicensing_mcp.server import netlicensing_list_licensees

    out = json.loads(await netlicensing_list_licensees("P1", filter="productNumber=P2"))
    assert out["error"] is True and out["status"] == 400


async def test_m1_customer_health_reads_all_license_pages():
    page0 = _resp(
        _item("License", number="L1", productModuleNumber="M1", active="true"),
        totalpages="2",
    )
    page1 = _resp(_item("License", number="L2", productModuleNumber="M2", active="true"))
    licensee = _resp(_item("Licensee", number="I1", active="true"))
    lic_get = AsyncMock(side_effect=[page0, page1])
    with (
        patch("netlicensing_mcp.tools.licenses.nl_get", new=lic_get),
        patch("netlicensing_mcp.tools.licensees.nl_get", new=AsyncMock(return_value=licensee)),
    ):
        from netlicensing_mcp.server import netlicensing_get_customer_health

        out = json.loads(await netlicensing_get_customer_health("I1"))
    assert lic_get.await_args_list[0].args == (
        "/license",
        {"filter": "licenseeNumber=I1;page=0;items=100"},
    )
    assert lic_get.await_args_list[1].args[1] == {"filter": "licenseeNumber=I1;page=1;items=100"}
    assert {m["module_number"] for m in out["modules"]} == {"M1", "M2"}


# ── M2: bundles carry `licenseTemplateNumbers` ───────────────────────────────


async def test_m2_create_bundle_sends_plural_template_numbers():
    mock_post = AsyncMock(return_value=_resp(_item("Bundle", number="B1")))
    with patch("netlicensing_mcp.tools.bundles.nl_post", new=mock_post):
        from netlicensing_mcp.tools.bundles import create_bundle

        await create_bundle("B1", "Bundle", ["LT1", "LT2"])
    data = mock_post.call_args.args[1]
    assert data["licenseTemplateNumbers"] == "LT1,LT2"
    assert "licenseTemplateNumber" not in data


async def test_m2_update_bundle_sends_plural_template_numbers():
    mock_post = AsyncMock(return_value=_resp(_item("Bundle", number="B1")))
    with patch("netlicensing_mcp.tools.bundles.nl_post", new=mock_post):
        from netlicensing_mcp.tools.bundles import update_bundle

        await update_bundle("B1", license_template_numbers=["LT3"])
    data = mock_post.call_args.args[1]
    assert data["licenseTemplateNumbers"] == "LT3"
    assert "licenseTemplateNumber" not in data


# ── M3: empty 204 success bodies ─────────────────────────────────────────────


@pytest.fixture
def fake_http():
    fake = AsyncMock()
    with patch("netlicensing_mcp.client._get_client", return_value=fake):
        tok = client.api_key_ctx.set("k")
        try:
            yield fake
        finally:
            client.api_key_ctx.reset(tok)


async def test_m3_204_is_success_not_502(fake_http):
    fake_http.post.return_value = httpx.Response(204)
    assert await client.nl_post("/licensee/I2/transfer", {"sourceLicenseeNumber": "I1"}) == {}


async def test_m3_transfer_tool_reports_success(fake_http):
    fake_http.post.return_value = httpx.Response(204)
    from netlicensing_mcp.server import netlicensing_transfer_licenses

    out = json.loads(await netlicensing_transfer_licenses("I1", "I2"))
    assert out["transferred"] is True
    assert out["from_licensee_number"] == "I1"
    assert "error" not in out


# ── M4: payment methods must not leak provider credentials ───────────────────

_SECRET = "sk_test_51ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_REFRESH = "rt_ABCDEFGHIJKLMNOPQRSTUVWXYZ987654"
_EMAIL = "merchant-owner@example.com"


def _pm_response() -> dict:
    return _resp(
        _item(
            "PaymentMethod",
            number="STRIPE_TESTING",
            active="true",
            **{
                "stripe.accessToken": _SECRET,
                "stripe.refreshToken": _REFRESH,
                "stripe.publishableKey": "pk_test_ABCDEFGHIJKLMNOP1234",
            },
        ),
        _item("PaymentMethod", number="PAYPAL", active="false", **{"paypal.subject": _EMAIL}),
    )


def _assert_no_secrets(text: str) -> None:
    for secret in (_SECRET, _REFRESH, _EMAIL, "pk_test_ABCDEFGHIJKLMNOP1234"):
        assert secret not in text


@pytest.mark.parametrize("include_raw", [False, True])
async def test_m4_list_payment_methods_masks_custom_properties(include_raw):
    with patch(
        "netlicensing_mcp.tools.payment_methods.nl_get",
        new=AsyncMock(return_value=_pm_response()),
    ):
        from netlicensing_mcp.server import netlicensing_list_payment_methods

        text = await netlicensing_list_payment_methods(include_raw=include_raw)
    _assert_no_secrets(text)
    out = json.loads(text)
    stripe = out["items"][0]
    assert stripe["number"] == "STRIPE_TESTING"  # allowlisted, clear
    assert stripe["active"] is True
    assert stripe["stripe.accessToken"] == "sk_****6789"


async def test_m4_get_and_update_payment_method_mask_too():
    single = _resp(_pm_response()["items"]["item"][1])
    with (
        patch(
            "netlicensing_mcp.tools.payment_methods.nl_get",
            new=AsyncMock(return_value=single),
        ),
        patch(
            "netlicensing_mcp.tools.payment_methods.nl_post",
            new=AsyncMock(return_value=single),
        ),
    ):
        from netlicensing_mcp.server import (
            netlicensing_get_payment_method,
            netlicensing_update_payment_method,
        )

        _assert_no_secrets(await netlicensing_get_payment_method("PAYPAL", include_raw=True))
        _assert_no_secrets(
            await netlicensing_update_payment_method("PAYPAL", paypal_subject="x@example.org")
        )


# ── M5: shop token sends licensee XOR product ────────────────────────────────


async def test_m5_shop_token_drops_product_when_licensee_given():
    mock_post = AsyncMock(return_value=_resp(_item("Token", number="T1")))
    with patch("netlicensing_mcp.tools.tokens.nl_post", new=mock_post):
        from netlicensing_mcp.tools.tokens import create_shop_token

        await create_shop_token("I1", product_number="P1")
    data = mock_post.call_args.args[1]
    assert data["licenseeNumber"] == "I1"
    assert "productNumber" not in data


async def test_m5_shop_token_product_only():
    mock_post = AsyncMock(return_value=_resp(_item("Token", number="T1")))
    with patch("netlicensing_mcp.tools.tokens.nl_post", new=mock_post):
        from netlicensing_mcp.server import netlicensing_create_shop_token

        await netlicensing_create_shop_token(product_number="P1")
    data = mock_post.call_args.args[1]
    assert data["productNumber"] == "P1"
    assert "licenseeNumber" not in data


async def test_m5_shop_token_needs_licensee_or_product():
    from netlicensing_mcp.server import netlicensing_create_shop_token

    out = json.loads(await netlicensing_create_shop_token())
    assert out["error"] is True and out["status"] == 400


# ── M6: price updates carry the current currency ─────────────────────────────


@pytest.mark.parametrize(
    ("module", "func", "arg", "path"),
    [
        ("license_templates", "update_license_template", "LT1", "/licensetemplate/LT1"),
        ("licenses", "update_license", "L1", "/license/L1"),
        ("bundles", "update_bundle", "B1", "/bundle/B1"),
    ],
)
async def test_m6_price_without_currency_keeps_current(module, func, arg, path):
    current = _resp(_item("X", number=arg, price="5.00", currency="EUR"))
    mock_get = AsyncMock(return_value=current)
    mock_post = AsyncMock(return_value=current)
    with (
        patch(f"netlicensing_mcp.tools.{module}.nl_get", new=mock_get),
        patch(f"netlicensing_mcp.tools.{module}.nl_post", new=mock_post),
    ):
        mod = __import__(f"netlicensing_mcp.tools.{module}", fromlist=[func])
        await getattr(mod, func)(arg, price=6.0)
    mock_get.assert_awaited_once_with(path)
    assert mock_post.call_args.args[1]["currency"] == "EUR"
    assert mock_post.call_args.args[1]["price"] == "6.0"


async def test_m6_explicit_currency_skips_lookup():
    mock_get = AsyncMock()
    mock_post = AsyncMock(return_value=_resp(_item("LicenseTemplate", number="LT1")))
    with (
        patch("netlicensing_mcp.tools.license_templates.nl_get", new=mock_get),
        patch("netlicensing_mcp.tools.license_templates.nl_post", new=mock_post),
    ):
        from netlicensing_mcp.tools.license_templates import update_license_template

        await update_license_template("LT1", price=6.0, currency="USD")
    mock_get.assert_not_awaited()
    assert mock_post.call_args.args[1]["currency"] == "USD"


@pytest.mark.parametrize(("currency", "fragment"), [("EUR", "unchanged"), (None, "no current")])
async def test_m6_preview_shows_currency_row(currency, fragment):
    props = {"number": "LT1", "price": "5.00"}
    if currency:
        props["currency"] = currency
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get",
        new=AsyncMock(return_value=_resp(_item("LicenseTemplate", **props))),
    ):
        from netlicensing_mcp.server import netlicensing_preview_update_license_template

        out = json.loads(await netlicensing_preview_update_license_template("LT1", price=6.0))
    row = next(c for c in out["changes"] if c["field"] == "currency")
    assert row["to"] == currency
    assert fragment in row["note"]


# ── M7: no confirmation token for an entity that does not exist ──────────────


@pytest.mark.parametrize(
    ("tool", "arg"),
    [
        ("netlicensing_preview_delete_licensee", "I-GONE"),
        ("netlicensing_delete_licensee", "I-GONE"),
        ("netlicensing_preview_delete_product", "P-GONE"),
        ("netlicensing_delete_product", "P-GONE"),
        ("netlicensing_preview_delete_product_module", "M-GONE"),
        ("netlicensing_delete_product_module", "M-GONE"),
    ],
)
async def test_m7_delete_preview_refuses_missing_entity(tool, arg, fake_http):
    not_found = {"infos": {"info": [{"id": "NotFoundException", "value": "not found"}]}}

    async def fake_get(url, **kwargs):
        # The entity itself is gone; its child lists are (correctly) empty.
        if url.endswith(f"/{arg}"):
            return httpx.Response(400, json=not_found)
        return httpx.Response(200, json=_resp(totalitems="0"))

    fake_http.get.side_effect = fake_get
    import netlicensing_mcp.server as server

    out = json.loads(await getattr(server, tool)(arg))
    assert out["error"] is True and out["status"] == 400
    assert "confirmation_token" not in out


# ── M8: module parameters without a module are rejected ──────────────────────


@pytest.mark.parametrize(
    "kwargs",
    [
        {"session_id": "s1"},
        {"action": "checkOut"},
        {"node_secret": "n1"},
        {"product_module_number": "M1", "session_id": "s1", "action": "grab"},
    ],
)
async def test_m8_validate_rejects_orphan_module_params(kwargs):
    mock_post = AsyncMock()
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.server import netlicensing_validate_licensee

        out = json.loads(await netlicensing_validate_licensee("I1", **kwargs))
    assert out["error"] is True and out["status"] == 400
    mock_post.assert_not_awaited()


async def test_m8_validate_with_module_sends_params():
    mock_post = AsyncMock(return_value=_resp())
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.tools.licensees import validate_licensee

        await validate_licensee("I1", product_module_number="M1", session_id="s1", action="checkIn")
    data = mock_post.call_args.args[1]
    # Indexed form, like the Java reference client (REPORT_v1.1 N1).
    assert data == {"productModuleNumber0": "M1", "sessionId0": "s1", "action0": "checkIn"}
