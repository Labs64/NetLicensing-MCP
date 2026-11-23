"""Regression tests for the MCP-layer issues of the 1.1.2 audit (ISSUE-01 … ISSUE-20)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from netlicensing_mcp import app, safety, server
from netlicensing_mcp.client import ClientValidationError
from netlicensing_mcp.errors import error_hint
from netlicensing_mcp.responses import wrap
from netlicensing_mcp.tools import helpers
from netlicensing_mcp.workflows.customer_health import build_health
from netlicensing_mcp.workflows.validation_explain import explain_validation


def _item(type_: str, **props: str) -> dict:
    return {"type": type_, "property": [{"name": k, "value": v} for k, v in props.items()]}


def _resp(*items: dict, **meta: str) -> dict:
    return {"items": {"item": list(items), **meta}}


@pytest.fixture(autouse=True)
def _clear_tokens():
    safety._store.clear()
    yield
    safety._store.clear()


@pytest.fixture
def no_request():
    """Fails the test if any HTTP request is attempted."""
    with patch("netlicensing_mcp.client._send", AsyncMock(side_effect=AssertionError("sent"))) as m:
        yield m


# ── ISSUE-01: product delete preview covers the whole cascade ───────────────────


async def test_issue01_product_preview_counts_whole_cascade():
    modules = _resp(_item("ProductModule", number="M1"), totalitems="1")
    licensees = _resp(
        _item("Licensee", number="C1"), _item("Licensee", number="C2"), totalitems="2"
    )
    templates = _resp(_item("LicenseTemplate", number="T1"), totalitems="1")
    bundles = _resp(
        _item("Bundle", number="B1", licenseTemplateNumbers="T1,T9"),
        _item("Bundle", number="B2", licenseTemplateNumbers="T7"),
        hasnext="false",
    )

    async def licenses_for(licensee, **kw):
        return _resp(totalitems="2" if licensee == "C1" else "1")

    with (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value={})),
        patch("netlicensing_mcp.tools.product_modules.nl_get", AsyncMock(return_value=modules)),
        patch("netlicensing_mcp.tools.licensees.nl_get", AsyncMock(return_value=licensees)),
        patch("netlicensing_mcp.tools.license_templates.nl_get", AsyncMock(return_value=templates)),
        patch("netlicensing_mcp.tools.bundles.nl_get", AsyncMock(return_value=bundles)),
        patch("netlicensing_mcp.tools.licenses.list_licenses", side_effect=licenses_for),
    ):
        preview = json.loads(await server.netlicensing_preview_delete_product("P", True))
        no_token = json.loads(await server.netlicensing_delete_product("P", True))
    assert preview["affected"] == {
        "product_modules": 1,
        "license_templates": 1,
        "licensees": 2,
        "licenses": 3,
        "bundles": 1,
    }
    assert preview["samples"]["bundles"] == ["B1"]
    assert preview["blocking_dependencies"] == {
        "product_modules": 1,
        "license_templates": 1,
        "licensees": 2,
        "licenses": 3,
        "bundles": 1,
    }
    assert no_token["affected"] == preview["affected"]


async def test_issue01_uncountable_values_are_reported_unknown():
    with (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value={})),
        patch(
            "netlicensing_mcp.tools.product_modules.nl_get",
            AsyncMock(return_value=_resp(_item("ProductModule", number="M1"), totalitems="1")),
        ),
        patch(
            "netlicensing_mcp.tools.licensees.nl_get",
            AsyncMock(return_value=_resp(totalitems="500")),
        ),
        patch(
            "netlicensing_mcp.tools.license_templates.nl_get",
            AsyncMock(return_value=_resp(totalitems="0")),
        ),
        patch(
            "netlicensing_mcp.tools.bundles.nl_get",
            AsyncMock(return_value=_resp(hasnext="false")),
        ),
    ):
        out = json.loads(await server.netlicensing_preview_delete_product("P"))
    assert out["affected"]["licenses"] == "unknown"
    assert out["affected"]["licensees"] == 500
    assert "licenses" in out["warnings"][0]


# ── ISSUE-02: update_transaction never sends a creation date ──────────────────


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"name": "x"}, {"status": "PENDING", "name": "x"}),
        ({"status": "CANCELLED", "name": "x"}, {"status": "CANCELLED", "name": "x"}),
        ({"status": "CLOSED"}, {"status": "CLOSED"}),
    ],
)
async def test_issue02_update_transaction_sends_no_creation_date(kwargs, expected):
    current = _resp(_item("Transaction", number="T", status="PENDING"))
    with (
        patch("netlicensing_mcp.tools.transactions.nl_get", AsyncMock(return_value=current)),
        patch("netlicensing_mcp.tools.transactions.nl_post", AsyncMock(return_value=current)) as p,
    ):
        await server.netlicensing_update_transaction("T", **kwargs)
    sent = p.call_args.args[1]
    assert sent == expected
    assert not {"dateCreated", "datecreated", "dateClosed"} & set(sent)


# ── ISSUE-03: redirect URLs ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/ok",
        "http://localhost:3000/ok",
        "http://127.0.0.1/ok",
    ],
)
def test_issue03_accepts_https_and_local_http(url):
    helpers.require_redirect_url("success_url", url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "file:///etc/passwd",
        "/relative/path",
        "http://example.com",
        "https://",
        "https://exa mple.com",
    ],
)
async def test_issue03_rejects_other_urls_before_any_request(url, no_request):
    out = json.loads(
        await server.netlicensing_create_shop_token(licensee_number="L", cancel_url=url)
    )
    assert out["error"] is True and out["status"] == 400
    assert "cancel_url" in out["detail"] and "https://" in out["detail"]
    no_request.assert_not_called()


async def test_issue03_titles_reject_control_characters(no_request):
    out = json.loads(
        await server.netlicensing_create_shop_token(licensee_number="L", success_url_title="a\x00b")
    )
    assert out["error"] is True and "success_url_title" in out["detail"]


# ── ISSUE-04: free text and numbers ───────────────────────────────────────────


async def test_issue04_number_with_markup_is_rejected_locally(no_request):
    out = json.loads(
        await server.netlicensing_create_product(number="ZZ-BAD ../;'\"<script>", name="n")
    )
    assert out["error"] is True and "Invalid number" in out["detail"]
    no_request.assert_not_called()


@pytest.mark.parametrize("bad", ["a\x00b", "a\x07b", "line1\nline2"])
async def test_issue04_control_characters_rejected_in_names(bad, no_request):
    out = json.loads(await server.netlicensing_create_product(number="P1", name=bad))
    assert out["error"] is True
    assert "name" in out["detail"] and "control characters" in out["detail"]


async def test_issue04_description_may_contain_newline_and_tab():
    helpers.validate_form_data({"description": "a\nb\tc", "number": "cust02@local.local"})
    with pytest.raises(ClientValidationError, match="description"):
        helpers.validate_form_data({"description": "a\x00b"})


# ── ISSUE-05: filter validation ───────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["bogus=;;&&", "a=1;;b=2", "=x", "active", "active=true&x=1"])
async def test_issue05_malformed_filter_is_an_error(bad, no_request):
    out = json.loads(await server.netlicensing_list_products(filter=bad))
    assert out["error"] is True and "filter" in out["detail"].lower()
    no_request.assert_not_called()


async def test_issue05_unsupported_key_is_warned_supported_is_not():
    with patch("netlicensing_mcp.tools.products.nl_get", AsyncMock(return_value=_resp())):
        warned = json.loads(await server.netlicensing_list_products(filter="name=MCP-Test"))
        clean = json.loads(await server.netlicensing_list_products(filter="active=true"))
    assert "filter key 'name' is not supported and was ignored" in warned["warnings"]
    assert clean["warnings"] == []


@pytest.mark.parametrize(
    "tool, args, key",
    [
        ("netlicensing_list_transactions", {}, "status"),
        ("netlicensing_list_tokens", {}, "tokenType"),
        ("netlicensing_list_bundles", {}, "active"),
    ],
)
async def test_issue05_each_group_supports_its_key(tool, args, key):
    mod = {"netlicensing_list_transactions": "transactions", "netlicensing_list_tokens": "tokens"}
    target = f"netlicensing_mcp.tools.{mod.get(tool, 'bundles')}.nl_get"
    with patch(target, AsyncMock(return_value=_resp())):
        out = json.loads(await getattr(server, tool)(filter=f"{key}=x;bogus=1", **args))
    assert out["warnings"] == ["filter key 'bogus' is not supported and was ignored"]


# ── ISSUE-06: elicitation ─────────────────────────────────────────────────────


async def _delete_with_token(approve):
    preview = json.loads(await server.netlicensing_preview_delete_license("L1"))
    with (
        patch("netlicensing_mcp.app._elicit_confirm", AsyncMock(return_value=approve)),
        patch("netlicensing_mcp.tools.licenses.nl_delete", AsyncMock(return_value=204)) as d,
    ):
        result = await _call_registered(
            "netlicensing_delete_license",
            {"license_number": "L1", "confirm_token": preview["confirmation_token"]},
        )
    return result, d


async def _call_registered(name, args):
    return await app.mcp._tool_manager.get_tool(name).fn(**args)


@pytest.fixture
def licenses_mock():
    with patch(
        "netlicensing_mcp.tools.licenses.nl_get",
        AsyncMock(return_value=_resp(_item("License", number="L1", licenseeNumber="C"))),
    ):
        yield


async def test_issue06_user_approval_lets_the_delete_run(licenses_mock):
    result, deleted = await _delete_with_token(True)
    assert not result.isError
    deleted.assert_awaited_once()


async def test_issue06_user_decline_stops_the_delete(licenses_mock):
    result, deleted = await _delete_with_token(False)
    assert result.isError
    assert "did not approve" in result.structuredContent["detail"]
    deleted.assert_not_awaited()


async def test_issue06_unsupported_client_falls_back_unless_required(licenses_mock, monkeypatch):
    result, deleted = await _delete_with_token(None)
    assert not result.isError
    deleted.assert_awaited_once()

    monkeypatch.setenv("NETLICENSING_MCP_REQUIRE_ELICITATION", "true")
    result, deleted = await _delete_with_token(None)
    assert result.isError
    assert "elicitation" in result.structuredContent["detail"]
    deleted.assert_not_awaited()


# ── ISSUE-07: secrets in create responses ──────────────────────────────────────


def _api_token():
    return _resp(
        _item(
            "Token",
            number="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            tokenType="APIKEY",
            apiKeyRole="ROLE_APIKEY_ADMIN",
        )
    )


async def test_issue07_default_returns_secret_once():
    secret = "a1b2c3d4-e5f6-7890-abcd-1234567890ab"
    with patch("netlicensing_mcp.tools.tokens.nl_post", AsyncMock(return_value=_api_token())):
        out = json.loads(await server.netlicensing_create_api_token())
    assert out["shown_once"] is True and secret[:3] in json.dumps(out)


async def test_issue07_redact_setting_masks_number_and_shop_url(monkeypatch):
    monkeypatch.setenv("NETLICENSING_MCP_REDACT_SECRETS", "true")
    secret = "a1b2c3d4-e5f6-7890-abcd-1234567890ab"
    shop = _resp(
        _item(
            "Token",
            number=secret,
            tokenType="SHOP",
            shopURL=f"https://go.netlicensing.io/shop/v2/?shoptoken={secret}",
        )
    )
    with patch("netlicensing_mcp.tools.tokens.nl_post", AsyncMock(return_value=_api_token())):
        api = await server.netlicensing_create_api_token(include_raw=True)
    with patch("netlicensing_mcp.tools.tokens.nl_post", AsyncMock(return_value=shop)):
        shop_out = await server.netlicensing_create_shop_token(
            licensee_number="L", include_raw=True
        )
    for text in (api, shop_out):
        assert secret not in text
        assert json.loads(text)["secret_masked"] is True
        assert "shown_once" not in json.loads(text)


# ── ISSUE-08: module-scoped validation arguments ──────────────────────────────


@pytest.mark.parametrize(
    "kwargs, fragment",
    [
        ({"session_id": "abc"}, "product_module_number"),
        ({"node_secret": "n"}, "product_module_number"),
        ({"action": "checkOut"}, "product_module_number"),
        ({"action": "checkOut", "product_module_number": "M"}, "session_id"),
        ({"action": "bogus", "session_id": "s", "product_module_number": "M"}, "checkOut"),
    ],
)
async def test_issue08_invalid_combinations_fail_before_the_request(kwargs, fragment, no_request):
    out = json.loads(await server.netlicensing_validate_licensee("L", **kwargs))
    assert out["error"] is True and fragment in out["detail"]
    no_request.assert_not_called()


# ── ISSUE-09 / ISSUE-10: health and explain ───────────────────────────────────


def _feature(number: str, valid: str) -> dict:
    return {
        "name": number,
        "property": [{"name": "featureName", "value": number}, {"name": "valid", "value": valid}],
    }


def _multifeature(module: str, *valids: str) -> dict:
    item = _item(
        "ProductModuleValidation",
        productModuleNumber=module,
        licensingModel="MultiFeature",
        valid="true",
    )
    item["list"] = [_feature(f"F{i}", v) for i, v in enumerate(valids)]
    return item


def test_issue09_all_features_invalid_is_degraded_not_a_clean_pass():
    payload = _resp(_multifeature("M1", "false", "false"), _multifeature("M2", "true", "false"))
    out = explain_validation(payload)
    states = {m["module_number"]: m["state"] for m in out["modules"]}
    assert states == {"M1": "degraded", "M2": "valid"}
    assert out["overall_status"] == "warning"
    assert "Validation passed for 1 of 2 modules" in out["summary"]
    assert "Valid but no valid features (1): M1" in out["summary"]


def test_issue09_health_marks_degraded_module():
    licensee = _resp(_item("Licensee", number="C", active="true"))
    licenses = _resp(_item("License", number="L", productModuleNumber="M1", active="true"))
    out = build_health(licensee, licenses, _resp(_multifeature("M1", "false", "false")))
    row = out["modules"][0]
    assert row["state"] == "degraded" and row["features_valid"] == 0
    assert out["overall_status"] == "warning"
    assert out["validation_counts"] == {"valid": 0, "degraded": 1, "invalid": 0, "unknown": 0}
    ok = build_health(licensee, licenses, _resp(_multifeature("M1", "true", "false")))
    assert ok["modules"][0]["state"] == "valid"


def test_issue10_every_health_row_has_valid_and_null_is_not_ok():
    licensee = _resp(_item("Licensee", number="C", active="true"))
    licenses = _resp(
        _item("License", number="L1", productModuleNumber="M1", active="true"),
        _item("License", number="L2", productModuleNumber="M2", active="true"),
    )
    validation = _resp(
        _item("ProductModuleValidation", productModuleNumber="M1", valid="true"),
        _item("ProductModuleValidation", productModuleNumber="M2", licensingModel="Rental"),
    )
    out = build_health(licensee, licenses, validation)
    assert {m["module_number"]: m["valid"] for m in out["modules"]} == {"M1": True, "M2": None}
    assert all("valid" in m for m in out["modules"])
    assert out["overall_status"] != "ok"


# ── ISSUE-11: duplicate infos ─────────────────────────────────────────────────


def test_issue11_identical_infos_appear_once():
    info = {"id": "X", "value": "No active licenses found for given licensee.", "type": "WARNING"}
    env = wrap({"items": {"item": []}, "infos": {"info": [info, dict(info), dict(info)]}}, "L")
    assert env["infos"]["info"] == [info]
    assert env["warnings"] == [info["value"]]


# ── ISSUE-12: previews validate before issuing a token ────────────────────────


@pytest.mark.parametrize(
    "tool, args, fragment",
    [
        (
            "netlicensing_preview_update_product",
            {"product_number": "P", "vat_mode": "BOGUS"},
            "vat_mode",
        ),
        (
            "netlicensing_preview_update_license_template",
            {"template_number": "T", "price": -1.0, "currency": "EUR"},
            "price",
        ),
        (
            "netlicensing_preview_update_license_template",
            {"template_number": "T", "price": 1.0, "currency": "XXXX"},
            "currency",
        ),
    ],
)
async def test_issue12_invalid_values_get_no_token(tool, args, fragment, no_request):
    out = json.loads(await getattr(server, tool)(**args))
    assert out["error"] is True and fragment in out["detail"]
    assert safety._store == {}
    no_request.assert_not_called()


# ── ISSUE-13: currency ────────────────────────────────────────────────────────


@pytest.mark.parametrize("code", ["EUR", "USD"])
def test_issue13_valid_currency(code):
    helpers.require_currency(code)


@pytest.mark.parametrize("code", ["XXXX", "eur", "E1R", "EU"])
def test_issue13_invalid_currency_message(code):
    with pytest.raises(ClientValidationError) as e:
        helpers.require_currency(code)
    assert (
        str(e.value.detail) == f"Invalid currency '{code}': expected an ISO 4217 code such as EUR"
    )


async def test_issue13_create_license_template_rejects_before_request(no_request):
    out = json.loads(
        await server.netlicensing_create_license_template(
            module_number="M", number="T", name="n", license_type="FEATURE", currency="XXXX"
        )
    )
    assert out["error"] is True and "Invalid currency" in out["detail"]


# ── ISSUE-14: token delete preview ────────────────────────────────────────────


async def test_issue14_preview_shows_role_and_scope_and_omits_missing():
    api = _resp(
        _item(
            "Token",
            number="k",
            tokenType="APIKEY",
            apiKeyRole="ROLE_APIKEY_LICENSEE",
            licenseeNumber="C1",
            productNumber="P1",
        )
    )
    shop = _resp(_item("Token", number="s", tokenType="SHOP"))
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=api)):
        a = json.loads(await server.netlicensing_preview_delete_token("k"))
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=shop)):
        s = json.loads(await server.netlicensing_preview_delete_token("s"))
    assert a["affected"] == {
        "token_type": "APIKEY",
        "role": "ROLE_APIKEY_LICENSEE",
        "licensee_number": "C1",
        "product_number": "P1",
    }
    assert s["affected"] == {"token_type": "SHOP"}


# ── ISSUE-15: pagination ──────────────────────────────────────────────────────


def test_issue15_hint_names_page_and_page_size():
    meta = {"pagenumber": "0", "itemsnumber": "25", "hasnext": "true", "totalitems": "60"}
    env = wrap(
        _resp(_item("Product", number="P"), **meta), "Product", as_list=True, paging_filter=""
    )
    assert "page=1 (page_size=25)" in env["next_page_hint"]


def test_issue15_envelope_has_paging_fields_when_upstream_sends_none():
    env = wrap(
        _resp(_item("License", number="L")),
        "License",
        as_list=True,
        paging_filter="active=true;page=0;items=2",
    )
    assert (env["count"], env["total"], env["page"], env["total_pages"], env["has_more"]) == (
        1,
        1,
        0,
        1,
        False,
    )


# ── ISSUE-16 / ISSUE-17: errors ───────────────────────────────────────────────


def test_issue16_client_errors_get_their_own_hint():
    from netlicensing_mcp.client import NetLicensingError

    mine = error_hint(ClientValidationError("Invalid vat_mode"), "netlicensing_update_product")
    api = error_hint(NetLicensingError(400, "Invalid vat_mode"), "netlicensing_update_product")
    assert "This server rejected the arguments" in mine["hint"]
    assert mine["retryable"] is False
    assert "This server rejected" not in api["hint"]


async def test_issue16_enum_error_blob_uses_client_hint(no_request):
    out = json.loads(await server.netlicensing_create_product(number="P", name="n", vat_mode="X"))
    assert "This server rejected the arguments" in out["hint"]


async def test_issue17_token_errors_share_envelope_and_reveal_nothing():
    token, _ = safety.issue_token("delete_product", "SECRET-TARGET")
    wrong_target = json.loads(
        await server.netlicensing_delete_product("OTHER", confirm_token=token)
    )
    unknown = json.loads(
        await server.netlicensing_delete_product("OTHER", confirm_token="CONF-NOPE0000")
    )
    safety._store.clear()
    for blob in (wrong_target, unknown):
        assert blob["error"] is True and blob["status"] == 400 and blob["retryable"] is False
    text = json.dumps(wrong_target)
    assert "SECRET-TARGET" not in text and "delete_product" not in wrong_target["detail"]


# ── ISSUE-18: descriptions come from the validator constants ──────────────────


@pytest.mark.parametrize(
    "tool, constant",
    [
        ("netlicensing_create_product_module", helpers.LICENSING_MODELS),
        ("netlicensing_create_license_template", helpers.LICENSE_TYPES),
        ("netlicensing_create_license_template", helpers.TIME_VOLUME_PERIODS),
        ("netlicensing_update_license_template", helpers.TIME_VOLUME_PERIODS),
        ("netlicensing_create_license", helpers.TIME_VOLUME_PERIODS),
        ("netlicensing_create_product", helpers.VAT_MODES),
        ("netlicensing_create_product", helpers.LICENSEE_SECRET_MODES),
        ("netlicensing_create_transaction", helpers.TRANSACTION_STATUSES),
        ("netlicensing_update_transaction", helpers.TRANSACTION_STATUSES),
        ("netlicensing_create_transaction", helpers.TRANSACTION_SOURCES),
        ("netlicensing_create_api_token", helpers.API_KEY_ROLES),
    ],
)
def test_issue18_docstring_lists_every_validator_value(tool, constant):
    doc = getattr(server, tool).__doc__ or ""
    missing = [v for v in constant if v not in doc]
    assert not missing, f"{tool} docstring omits {missing}"


# ── ISSUE-20: one serializer ──────────────────────────────────────────────────


async def test_issue20_delete_results_are_indented_like_other_tools():
    out = helpers.delete_result("delete_license", "License", "L1", 204)
    assert out == json.dumps(json.loads(out), indent=2)


# keep ``httpx`` imported for fixtures that build responses in future tests
_ = httpx
