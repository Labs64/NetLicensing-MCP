"""Fixes from the MCP-layer audit (M1-M12): bound tokens, identifier validation,
sanitized errors, honest health, enums, masked tokens, client-side filters, paging."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from netlicensing_mcp import client, safety
from netlicensing_mcp.client import NetLicensingError, _apply_client_filter, sanitize_detail
from netlicensing_mcp.errors import error_hint
from netlicensing_mcp.responses import wrap
from netlicensing_mcp.server import (
    netlicensing_create_license_template,
    netlicensing_create_transaction,
    netlicensing_delete_token,
    netlicensing_get_product,
    netlicensing_get_token,
    netlicensing_list_countries,
    netlicensing_list_product_modules,
    netlicensing_list_transactions,
    netlicensing_preview_delete_licensee,
    netlicensing_preview_delete_token,
    netlicensing_preview_update_license_template,
    netlicensing_preview_update_payment_method,
    netlicensing_preview_update_product,
    netlicensing_update_license_template,
    netlicensing_update_product,
    netlicensing_update_transaction,
)
from netlicensing_mcp.workflows.customer_health import build_health
from netlicensing_mcp.workflows.validation_explain import explain_validation


@pytest.fixture(autouse=True)
def clear_store():
    safety._store.clear()
    reset = client.api_key_ctx.set("test-key")
    yield
    client.api_key_ctx.reset(reset)
    safety._store.clear()


def _item(kind: str, lists: list | None = None, **props: str) -> dict:
    return {
        "type": kind,
        "property": [{"name": k, "value": v} for k, v in props.items()],
        "list": lists or [],
    }


def _resp(*items: dict, **attrs: str) -> dict:
    return {"items": {"item": list(items), **attrs}}


# ── M1: tokens are bound to the previewed change ────────────────────────────


def _template(price: str = "1.50") -> dict:
    return _resp(_item("LicenseTemplate", number="T1", price=price, currency="EUR", active="true"))


async def test_m1_template_token_rejects_other_price():
    with (
        patch(
            "netlicensing_mcp.tools.license_templates.nl_get", AsyncMock(return_value=_template())
        ),
        patch(
            "netlicensing_mcp.tools.license_templates.nl_post", AsyncMock(return_value={})
        ) as post,
    ):
        token = json.loads(await netlicensing_preview_update_license_template("T1", price=7.77))[
            "confirmation_token"
        ]
        r = json.loads(
            await netlicensing_update_license_template("T1", price=99, confirm_token=token)
        )
        assert r["error"] is True
        assert "differ" in r["detail"]
        post.assert_not_called()
        # The rejected token was not consumed: the previewed value still works.
        await netlicensing_update_license_template("T1", price=7.77, confirm_token=token)
        post.assert_called_once()


async def test_m1_product_token_rejects_other_vat_mode():
    product = _resp(_item("Product", number="P1"))
    with (
        patch("netlicensing_mcp.tools.products.nl_get", AsyncMock(return_value=product)),
        patch("netlicensing_mcp.tools.products.nl_post", AsyncMock(return_value={})) as post,
    ):
        token = json.loads(await netlicensing_preview_update_product("P1", vat_mode="NET"))[
            "confirmation_token"
        ]
        r = json.loads(
            await netlicensing_update_product("P1", vat_mode="GROSS", confirm_token=token)
        )
        assert r["error"] is True and "differ" in r["detail"]
        post.assert_not_called()
        await netlicensing_update_product("P1", vat_mode="NET", confirm_token=token)
        post.assert_called_once()


def test_m1_change_set_normalizes():
    assert safety.change_set(price=7.77, currency="", active=None) == (("price", "7.77"),)
    assert safety.change_set(price=7, active=True) == (("active", "true"), ("price", "7.0"))


# ── M12: no-op preview, delete previews, descriptions ───────────────────────


async def test_m12_noop_preview_issues_no_token():
    pm = _resp(_item("PaymentMethod", number="STRIPE", active="false"))
    with patch("netlicensing_mcp.tools.payment_methods.nl_get", AsyncMock(return_value=pm)):
        r = json.loads(await netlicensing_preview_update_payment_method("STRIPE", active=False))
    assert r["no_change"] is True
    assert "confirmation_token" not in r
    assert safety._store == {}


async def test_m12_licensee_preview_reports_blocking_licenses():
    licenses = _resp(_item("License", number="L1"), _item("License", number="L2"), totalitems="2")
    with (
        patch("netlicensing_mcp.tools.licensees.nl_get", AsyncMock(return_value=_resp())),
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=licenses)),
    ):
        r = json.loads(await netlicensing_preview_delete_licensee("CUST"))
    assert r["requires_force_cascade"] is True
    assert r["blocking_dependencies"] == {"licenses": 2}


def test_m12_start_date_mentions_now():
    from netlicensing_mcp.app import mcp  # noqa: F401
    from netlicensing_mcp.server import netlicensing_create_license

    assert '"now"' in (netlicensing_create_license.__doc__ or "")


# ── M2 / M8: identifiers ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ident", ["CUST?foo=bar", "CUST#frag", "a'; DROP TABLE x;--", "", "   ", "a%2Fb"]
)
async def test_m2_m8_bad_identifier_makes_no_request(ident):
    with patch("netlicensing_mcp.client._send", AsyncMock()) as send:
        r = json.loads(await netlicensing_get_product(ident))
    assert r["error"] is True and r["status"] == 400
    send.assert_not_called()


# ── M3: sanitized details ───────────────────────────────────────────────────


def test_m3_sanitize_cuts_stack_and_class_names():
    raw = (
        'java.lang.NullPointerException: Cannot invoke "com.labs64.X$Status.toString()" '
        "because this.status is null\n\tat org.glassfish.jersey.Foo(Foo.java:1)\n\tat x"
    )
    out = sanitize_detail(raw)
    assert "\tat " not in out and "java.lang." not in out and "com.labs64." not in out
    assert len(sanitize_detail("x" * 1000)) <= 300


def test_m3_raise_on_error_hides_java_internals():
    body = {
        "infos": {
            "info": [
                {
                    "id": "X",
                    "value": "java.lang.NullPointerException: boom\n\tat com.labs64.Foo.bar(Foo.java:1)",
                }
            ]
        }
    }
    with pytest.raises(NetLicensingError) as exc:
        client._raise_on_error(httpx.Response(500, json=body))
    assert "java.lang" not in exc.value.detail and "\tat" not in exc.value.detail


async def test_m3_update_transaction_name_only_sends_existing_status():
    current = _resp(_item("Transaction", number="TX", status="CLOSED"))
    with (
        patch("netlicensing_mcp.tools.transactions.nl_get", AsyncMock(return_value=current)),
        patch(
            "netlicensing_mcp.tools.transactions.nl_post", AsyncMock(return_value=current)
        ) as post,
    ):
        await netlicensing_update_transaction("TX", name="renamed")
    sent = post.call_args.args[1]
    assert sent == {"status": "CLOSED", "name": "renamed"}


# ── M4: customer health ─────────────────────────────────────────────────────


def test_m4_health_without_validation_is_not_ok():
    licensee = _resp(_item("Licensee", number="C", active="true"))
    licenses = _resp(_item("License", number="L", productModuleNumber="M1", active="true"))
    env = build_health(licensee, licenses, None)
    assert env["overall_status"] == "unknown"
    assert env["validation_run"] is False
    assert "refresh_warning_level=true" in env["summary"]


# ── M5: explain_validation ──────────────────────────────────────────────────


def _validation() -> dict:
    return {
        "items": {
            "item": [
                _item(
                    "ProductModuleValidation",
                    productModuleNumber="MR",
                    licensingModel="Rental",
                    warningLevel="RED",
                ),
                _item(
                    "ProductModuleValidation",
                    productModuleNumber="MQ",
                    licensingModel="Quota",
                    valid="false",
                ),
                _item(
                    "ProductModuleValidation",
                    productModuleNumber="MP",
                    licensingModel="PayPerUse",
                    valid="false",
                ),
                _item(
                    "ProductModuleValidation",
                    productModuleNumber="MG",
                    licensingModel="GoodOne",
                    valid="true",
                ),
            ]
        },
        "infos": {
            "info": [{"id": "NoActiveLicenses", "type": "WARNING", "value": "No active."}] * 3
        },
    }


def test_m5_missing_valid_is_unknown_and_counts_match():
    env = explain_validation(_validation())
    rental = next(m for m in env["modules"] if m["module_number"] == "MR")
    assert rental["valid"] is None
    assert "unknown" in rental["explanation"].lower()
    invalid = [m["module_number"] for m in env["modules"] if m["valid"] is False]
    assert f"Invalid ({len(invalid)}): {', '.join(invalid)}" in env["summary"]
    assert "Unknown or warning level (1): MR" in env["summary"]
    assert env["warnings"].count("No active.") == 1
    quota = next(m for m in env["modules"] if m["module_number"] == "MQ")
    assert "quota" in quota["explanation"].lower()
    assert any("Top up" in a for a in quota["suggested_actions"])


def test_m5_multifeature_features_and_deduped_infos():
    group = {
        "name": "EF5UJMTA3",
        "property": [
            {"name": "valid", "value": "false"},
            {"name": "featureName", "value": "Feature 1"},
        ],
        "list": [],
    }
    item = _item(
        "ProductModuleValidation",
        lists=[group],
        productModuleNumber="MM",
        licensingModel="MultiFeature",
        valid="true",
    )
    out = wrap({"items": {"item": [item]}}, "ProductModuleValidation", as_list=True)
    row = out["items"][0]
    assert row["features"] == [{"number": "EF5UJMTA3", "name": "Feature 1", "valid": False}]
    assert "EF5UJMTA3" not in row
    env = explain_validation({"items": {"item": [item]}})
    assert env["modules"][0]["features"][0]["valid"] is False


def test_m5_info_warnings_deduped_in_list_envelope():
    payload = _validation()
    out = wrap(payload, "ProductModuleValidation", as_list=True)
    assert out["warnings"].count("No active.") == 1


# ── M6: hints ───────────────────────────────────────────────────────────────


def test_m6_gateway_html_403_is_not_a_role_problem():
    with pytest.raises(NetLicensingError) as exc:
        client._raise_on_error(httpx.Response(403, text="<html><body>403 Forbidden</body></html>"))
    assert "<html>" not in exc.value.detail
    hint = error_hint(exc.value, "netlicensing_get_product")["hint"]
    assert "role" not in hint.lower().replace("not an api key role problem", "")
    assert "gateway" in hint


def test_m6_no_active_modules_is_not_licensee_not_found():
    exc = NetLicensingError(404, "No active product modules available to validate.")
    hint = error_hint(exc, "netlicensing_validate_licensee")["hint"]
    assert "not found" not in hint
    assert "list the product's modules" in hint


# ── M7: enums ───────────────────────────────────────────────────────────────


async def test_m7_bad_enum_fails_locally_and_lists_values():
    with patch("netlicensing_mcp.client._send", AsyncMock()) as send:
        r = json.loads(
            await netlicensing_create_license_template("M", "T", "n", license_type="NOT_A_TYPE")
        )
        assert r["error"] is True and "FEATURE, TIMEVOLUME, FLOATING, QUANTITY" in r["detail"]
        r = json.loads(await netlicensing_create_transaction(status="BOGUS"))
        assert "CANCELLED, CLOSED, PENDING" in r["detail"]
    send.assert_not_called()


# ── M9: masked tokens ───────────────────────────────────────────────────────

_KEY_A = "aacdef0123456789abcdef534c"
_KEY_B = "aac999999999999999999999534c"


def _token_list(*numbers: str) -> dict:
    return _resp(*[_item("Token", number=n, tokenType="APIKEY") for n in numbers], hasnext="false")


async def test_m9_masked_number_resolves_to_one_token():
    from netlicensing_mcp.redaction import mask_token_number

    listing = _token_list(_KEY_A, "zzz-other-token-number-0000")
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=listing)) as get:
        r = json.loads(await netlicensing_preview_delete_token(mask_token_number(_KEY_A)))
    assert "confirmation_token" in r
    assert _KEY_A not in json.dumps(r)
    # The confirmation token is bound to the real number.
    assert [e[1] for e in safety._store.values()] == [_KEY_A]
    assert get.call_args_list[-1].args[0] == f"/token/{_KEY_A}"


async def test_m9_ambiguous_masked_number_is_an_error():
    from netlicensing_mcp.redaction import mask_token_number

    listing = _token_list(_KEY_A, _KEY_B)
    assert mask_token_number(_KEY_A) == mask_token_number(_KEY_B)
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=listing)):
        r = json.loads(await netlicensing_get_token(mask_token_number(_KEY_A)))
        d = json.loads(await netlicensing_delete_token(mask_token_number(_KEY_A)))
    assert r["error"] is True and "ambiguous" in r["detail"]
    assert d["error"] is True


# ── M10: client-side filters ────────────────────────────────────────────────


def test_m10_active_filter_applied_client_side():
    body = _resp(
        _item("ProductModule", number="A", active="false"),
        _item("ProductModule", number="B", active="false"),
        totalitems="2",
    )
    assert len(_apply_client_filter(body, "productNumber=P;active=true")["items"]["item"]) == 0
    kept = _apply_client_filter(body, "productNumber=P;active=false")
    assert len(kept["items"]["item"]) == 2 and kept["items"]["totalitems"] == "2"


async def test_m10_list_modules_filters_active():
    body = _resp(_item("ProductModule", number="A", active="false"))
    with patch(
        "netlicensing_mcp.client._send", AsyncMock(return_value=httpx.Response(200, json=body))
    ):
        on = json.loads(await netlicensing_list_product_modules("P", filter="active=true"))
        off = json.loads(await netlicensing_list_product_modules("P", filter="active=false"))
    assert on["count"] == 0 and off["count"] == 1


async def test_m10_transactions_status_filter():
    body = _resp(_item("Transaction", number="T", status="CLOSED"), totalitems="388")
    with patch(
        "netlicensing_mcp.client._send", AsyncMock(return_value=httpx.Response(200, json=body))
    ):
        r = json.loads(await netlicensing_list_transactions(filter="status=PENDING"))
    assert r["count"] == 0


# ── M11: size and shape ─────────────────────────────────────────────────────


async def test_m11_default_page_size_and_overrides():
    resp = httpx.Response(200, json=_resp())
    with patch("netlicensing_mcp.client._send", AsyncMock(return_value=resp)) as send:
        await netlicensing_list_transactions()
        assert send.call_args.kwargs["params"]["filter"] == "items=25;page=0"
        await netlicensing_list_transactions(filter="status=CLOSED", page=2, page_size=10)
        assert send.call_args.kwargs["params"]["filter"] == "status=CLOSED;items=10;page=2"
        await netlicensing_list_transactions(filter="page=1;items=2")
        assert send.call_args.kwargs["params"]["filter"] == "page=1;items=2"
        bad = json.loads(await netlicensing_list_transactions(page_size=500))
        assert bad["error"] is True


async def test_m11_compact_keeps_few_fields():
    body = _resp(_item("Transaction", number="T", name="n", status="CLOSED", source="SHOP"))
    with patch(
        "netlicensing_mcp.client._send", AsyncMock(return_value=httpx.Response(200, json=body))
    ):
        r = json.loads(await netlicensing_list_transactions(compact=True))
    assert set(r["items"][0]) == {"type", "number", "name", "status"}


def test_m11_warning_level_summary_is_an_object():
    item = _item("Licensee", number="L", warningLevelSummary='{"RED":["M1"],"GREEN":[]}')
    out = wrap({"items": {"item": [item]}}, "Licensee")
    assert out["warningLevelSummary"] == {"RED": ["M1"], "GREEN": []}


async def test_m11_countries_search_and_eu_only():
    def country(code: str, name: str, eu: str) -> dict:
        return _item("Country", code=code, name=name, isEu=eu)

    body = _resp(
        country("DE", "Germany", "true"),
        country("DK", "Denmark", "true"),
        country("US", "United States", "false"),
    )
    with patch("netlicensing_mcp.tools.utilities.nl_get", AsyncMock(return_value=body)):
        eu = json.loads(await netlicensing_list_countries(eu_only=True))
        one = json.loads(await netlicensing_list_countries(search="united"))
    assert eu["count"] == 2 and one["count"] == 1
