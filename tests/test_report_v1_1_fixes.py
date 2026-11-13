"""Regression tests for the MCP findings N1–N6 in REPORT_v1.1.md (v0.1.13)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qsl

import httpx
import pytest

import netlicensing_mcp.client as client
from netlicensing_mcp import safety
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.redaction import _mask, redact_payment_method
from netlicensing_mcp.responses import wrap
from netlicensing_mcp.workflows.customer_health import build_health
from netlicensing_mcp.workflows.validation_explain import explain_validation

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def _item(type_: str, **props: str) -> dict:
    return {
        "type": type_,
        "property": [{"name": k, "value": v} for k, v in props.items()],
    }


def _resp(*items: dict, **meta: object) -> dict:
    return {"items": {"item": list(items)}, **meta}


@pytest.fixture(autouse=True)
def _clear_tokens():
    safety._store.clear()
    yield
    safety._store.clear()


# ── N1: validate sends module parameters in indexed form ─────────────────────


@pytest.fixture
def wire():
    """Swap the shared httpx client for a MockTransport that records requests."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json=_resp(_item("ProductModuleValidation", productModuleNumber="M1", valid="true")),
        )

    old = client._client
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    token = client.api_key_ctx.set("test-key")
    yield captured
    client.api_key_ctx.reset(token)
    client._client = old


async def test_n1_wire_body_indexed_for_one_module(wire):
    from netlicensing_mcp.tools.licensees import validate_licensee

    await validate_licensee(
        "I1",
        product_number="P1",
        product_module_number="M1",
        session_id="s1",
        action="checkOut",
        dry_run=True,
    )
    req = wire[0]
    assert req.method == "POST"
    assert req.url.path.endswith("/licensee/I1/validate")
    body = req.content.decode()
    pairs = parse_qsl(body)
    assert dict(pairs) == {
        "productNumber": "P1",
        "productModuleNumber0": "M1",
        "sessionId0": "s1",
        "action0": "checkOut",
        "dryRun": "true",
    }
    # Exact encoded form as on the wire.
    assert "productModuleNumber0=M1&sessionId0=s1&action0=checkOut" in body


async def test_n1_wire_body_node_secret_indexed(wire):
    from netlicensing_mcp.tools.licensees import validate_licensee

    await validate_licensee("I1", product_module_number="M2", node_secret="node-A")
    assert wire[0].content.decode() == "productModuleNumber0=M2&nodeSecret0=node-A"


async def test_n1_wire_body_without_module_has_no_index(wire):
    from netlicensing_mcp.tools.licensees import validate_licensee

    await validate_licensee("I1", product_number="P1", licensee_name="ACME", dry_run=True)
    body = wire[0].content.decode()
    assert body == "productNumber=P1&licenseeName=ACME&dryRun=true"
    assert not any(k[-1].isdigit() for k, _ in parse_qsl(body))


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"session_id": "s1"}, "requires product_module_number"),
        ({"product_module_number": "M1", "action": "borrow", "session_id": "s"}, "checkOut"),
        ({"product_module_number": "M1", "action": "checkOut"}, "requires session_id"),
        ({"product_module_number": "M1", "action": "checkIn"}, "requires session_id"),
    ],
)
async def test_n1_guards(kwargs, fragment, wire):
    from netlicensing_mcp.tools.licensees import validate_licensee

    with pytest.raises(NetLicensingError) as exc:
        await validate_licensee("I1", **kwargs)
    assert exc.value.status_code == 400
    assert fragment in exc.value.detail
    assert wire == []


async def test_n1_server_tool_passes_dry_run():
    mock_post = AsyncMock(return_value=_resp())
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.server import netlicensing_validate_licensee

        await netlicensing_validate_licensee("I1", dry_run=True)
    assert mock_post.call_args.args[1] == {"dryRun": "true"}


async def test_n1_server_tool_dry_run_defaults_false():
    mock_post = AsyncMock(return_value=_resp())
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.server import netlicensing_validate_licensee

        await netlicensing_validate_licensee("I1")
    assert "dryRun" not in mock_post.call_args.args[1]


async def test_n1_server_tool_reports_missing_session_id():
    from netlicensing_mcp.server import netlicensing_validate_licensee

    out = json.loads(
        await netlicensing_validate_licensee("I1", product_module_number="M1", action="checkOut")
    )
    assert out["error"] is True and out["status"] == 400
    assert "session_id" in out["detail"]


def test_n1_floating_result_keeps_session_data_and_infos():
    floating = _item(
        "ProductModuleValidation",
        productModuleNumber="M-FLT",
        licensingModel="Floating",
        valid="false",
        expires="2026-11-13T10:00:00Z",
    )
    floating["list"] = [
        {"name": "s1", "property": [{"name": "expirationTimestamp", "value": "x"}]},
        {"name": "s2", "property": [{"name": "expirationTimestamp", "value": "y"}]},
    ]
    payload = _resp(
        floating,
        infos={"info": [{"id": "NoFreeSessions", "type": "WARNING", "value": "No free sessions"}]},
    )
    env = wrap(payload, "ProductModuleValidation", as_list=True)
    item = env["items"][0]
    assert item["valid"] == "false"
    assert item["expires"] == "2026-11-13T10:00:00Z"
    assert item["s1"] == {"expirationTimestamp": "x"}
    assert item["s2"] == {"expirationTimestamp": "y"}
    assert env["infos"] == payload["infos"]
    assert "No free sessions" in env["warnings"]


def test_n1_repeated_list_names_become_a_list():
    it = _item("ProductModuleValidation", productModuleNumber="M1")
    it["list"] = [
        {"name": "session", "property": [{"name": "id", "value": "a"}]},
        {"name": "session", "property": [{"name": "id", "value": "b"}]},
    ]
    env = wrap(_resp(it), as_list=True)
    assert env["items"][0]["session"] == [{"id": "a"}, {"id": "b"}]


# ── N2: list tools always return the list envelope ───────────────────────────

_LIST_TOOLS = [
    ("netlicensing_list_products", "products.list_products", (), "Product"),
    ("netlicensing_list_product_modules", "product_modules.list_product_modules", ("P1",), "ProductModule"),
    ("netlicensing_list_license_templates", "license_templates.list_license_templates", ("M1",), "LicenseTemplate"),
    ("netlicensing_list_licensees", "licensees.list_licensees", ("P1",), "Licensee"),
    ("netlicensing_list_licenses", "licenses.list_licenses", ("I1",), "License"),
    ("netlicensing_list_bundles", "bundles.list_bundles", (), "Bundle"),
    ("netlicensing_obtain_bundle", "bundles.obtain_bundle", ("B1", "I1"), "License"),
    ("netlicensing_list_tokens", "tokens.list_tokens", (), "Token"),
    ("netlicensing_list_transactions", "transactions.list_transactions", (), "Transaction"),
    ("netlicensing_list_payment_methods", "payment_methods.list_payment_methods", (), "PaymentMethod"),
    ("netlicensing_list_countries", "utilities.list_countries", (), "Country"),
    ("netlicensing_list_license_types", "utilities.list_license_types", (), "LicenseType"),
    ("netlicensing_list_licensing_models", "utilities.list_licensing_models", (), "LicensingModel"),
    ("netlicensing_validate_licensee", "licensees.validate_licensee", ("I1",), "ProductModuleValidation"),
]  # fmt: skip


@pytest.mark.parametrize("n", [0, 1, 2])
@pytest.mark.parametrize(("tool", "target", "args", "kind"), _LIST_TOOLS)
async def test_n2_list_envelope_for_any_count(tool, target, args, kind, n):
    items = [_item(kind, number=f"X{i}", name=f"n{i}") for i in range(n)]
    with patch(f"netlicensing_mcp.tools.{target}", new=AsyncMock(return_value=_resp(*items))):
        import netlicensing_mcp.server as server

        out = json.loads(await getattr(server, tool)(*args))
    assert out["type"] == "list"
    assert out["kind"] == kind
    assert out["count"] == n
    assert len(out["items"]) == n


def test_n2_get_path_still_single_envelope():
    env = wrap(_resp(_item("Product", number="P1", active="true")), "Product")
    assert env["type"] == "Product" and env["number"] == "P1"


# ── N3: invalid modules are never healthy ────────────────────────────────────


def _licensee(number: str = "I1") -> dict:
    return _resp(_item("Licensee", number=number, active="true"))


def _licenses(*modules: str) -> dict:
    return _resp(
        *(_item("License", number=f"L{i}", productModuleNumber=m) for i, m in enumerate(modules))
    )


def test_n3_invalid_green_module_is_critical():
    validation = _resp(
        _item(
            "ProductModuleValidation",
            productModuleNumber="WAFT1113-M2",
            licensingModel="Floating",
            valid="false",
            warningLevel="GREEN",
        )
    )
    env = build_health(_licensee(), _licenses("WAFT1113-M2"), validation, now=NOW)
    assert env["overall_status"] == "critical"
    assert any("WAFT1113-M2" in w for w in env["warnings"])
    assert "Module WAFT1113-M2 is invalid" in env["summary"]
    assert "healthy" not in env["summary"]
    assert (
        "Run netlicensing_explain_validation for I1 (module WAFT1113-M2)."
        in env["suggested_actions"]
    )


def test_n3_invalid_module_without_warning_level_is_critical():
    validation = _resp(_item("ProductModuleValidation", productModuleNumber="M-A", valid="false"))
    env = build_health(_licensee(), _licenses("M-A"), validation, now=NOW)
    assert env["overall_status"] == "critical"


def test_n3_all_valid_is_ok():
    validation = _resp(
        _item("ProductModuleValidation", productModuleNumber="M1", valid="true", warningLevel="GREEN"),
        _item("ProductModuleValidation", productModuleNumber="M2", valid="true", warningLevel="GREEN"),
    )  # fmt: skip
    env = build_health(_licensee(), _licenses("M1", "M2"), validation, now=NOW)
    assert env["overall_status"] == "ok"
    assert env["summary"] == "All 2 modules are healthy."


def test_n3_error_info_without_module_data_is_a_warning():
    msg = "Product module 'WAFT1113-M2' validation error: Property 'sessionId' must be provided"
    validation = {"infos": {"info": [{"id": "x", "type": "ERROR", "value": msg}]}}
    env = build_health(_licensee(), _licenses(), validation, now=NOW)
    assert f"Module WAFT1113-M2: {msg}" in env["warnings"]
    assert env["overall_status"] != "ok"


def test_n3_info_not_duplicated():
    msg = "Some warning"
    validation = {
        "infos": {"info": [{"type": "WARNING", "value": msg}, {"type": "WARNING", "value": msg}]}
    }
    env = build_health(_licensee(), _licenses(), validation, now=NOW)
    assert env["warnings"].count(msg) == 1


def test_n3_summary_keeps_module_case():
    validation = _resp(
        _item(
            "ProductModuleValidation",
            productModuleNumber="WAFT-Sub",
            licensingModel="Subscription",
            valid="true",
            warningLevel="YELLOW",
            expires="2026-11-20T00:00:00Z",
        )
    )
    env = build_health(_licensee(), _licenses("WAFT-Sub"), validation, now=NOW)
    assert "(module WAFT-Sub)" in env["summary"]
    assert env["summary"][0].isupper()


def test_n3_explain_invalid_is_critical_with_warning():
    payload = _resp(
        _item(
            "ProductModuleValidation",
            productModuleNumber="WAFT1113-M2",
            licensingModel="Floating",
            valid="false",
            warningLevel="GREEN",
        ),
        infos={"info": [{"type": "ERROR", "value": "boom"}]},
    )
    env = explain_validation(payload, now=NOW)
    assert env["overall_status"] == "critical"
    assert "boom" in env["warnings"]
    assert "WAFT1113-M2" in env["summary"]


# ── N4: secrets shorter than 16 characters are fully masked ──────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a" * 8, "****"),
        ("abcdefghijklmno", "****"),  # 15
        ("abcdefghijklmnop", "abc****mnop"),  # 16
        ("abcdefghijklmnopq", "abc****nopq"),  # 17
    ],
)
def test_n4_mask_boundaries(value, expected):
    assert _mask(value) == expected


def test_n4_payment_method_short_values_fully_masked():
    resp = _resp(
        _item(
            "PaymentMethod",
            number="PAYPAL",
            active="true",
            email="cus@ex.com",  # e-mail: same rule, no special case
            secretKey="pk_live_51H8xYzW3Od",
        )
    )
    props = {
        p["name"]: p["value"] for p in redact_payment_method(resp)["items"]["item"][0]["property"]
    }
    assert props["email"] == "****"
    assert props["secretKey"] == "pk_****W3Od"
    assert props["number"] == "PAYPAL"


# ── N5: prices with two decimals and currency ────────────────────────────────


async def test_n5_template_preview_price_format():
    current = _resp(_item("LicenseTemplate", number="LT1", price="60.0", currency="EUR"))
    with patch(
        "netlicensing_mcp.tools.license_templates.nl_get", new=AsyncMock(return_value=current)
    ):
        from netlicensing_mcp.server import netlicensing_preview_update_license_template

        out = json.loads(await netlicensing_preview_update_license_template("LT1", price=75))
    row = next(c for c in out["changes"] if c["field"] == "price")
    assert row["from"] == "60.00 EUR"
    assert row["to"] == "75.00 EUR"


async def test_n5_bundle_and_license_delete_previews_format_price():
    bundle = _resp(_item("Bundle", number="B1", name="b", price="10", currency="USD"))
    lic = _resp(_item("License", number="L1", price="5.5", currency="EUR"))
    with (
        patch("netlicensing_mcp.tools.bundles.nl_get", new=AsyncMock(return_value=bundle)),
        patch("netlicensing_mcp.tools.licenses.nl_get", new=AsyncMock(return_value=lic)),
    ):
        from netlicensing_mcp.server import (
            netlicensing_preview_delete_bundle,
            netlicensing_preview_delete_license,
        )

        b = json.loads(await netlicensing_preview_delete_bundle("B1"))
        lout = json.loads(await netlicensing_preview_delete_license("L1"))
    assert b["samples"]["price"] == "10.00 USD"
    assert lout["samples"]["price"] == "5.50 EUR"


def test_n5_fmt_price_edge_cases():
    from netlicensing_mcp.server import _fmt_price

    assert _fmt_price(None) is None
    assert _fmt_price("") is None
    assert _fmt_price(60.0) == "60.00"
    assert _fmt_price("abc", "EUR") == "abc EUR"


# ── N6: server_info ──────────────────────────────────────────────────────────


async def test_n6_server_info(monkeypatch):
    from importlib.metadata import version

    from netlicensing_mcp.server import netlicensing_server_info

    monkeypatch.setattr(client, "BASE_URL", "https://user:pw@go.netlicensing.io/core/v2/rest")
    token = client.api_key_ctx.set("secret-key")
    try:
        out = json.loads(await netlicensing_server_info())
    finally:
        client.api_key_ctx.reset(token)
    assert out == {
        "version": version("netlicensing-mcp"),
        "base_url": "go.netlicensing.io",
        "demo_mode": False,
    }


async def test_n1_validate_surfaces_info_refusal():
    payload = _resp(
        _item("ProductModuleValidation", productModuleNumber="M2", valid="false"),
        infos={
            "info": [
                {
                    "id": "NoFreeSessions",
                    "type": "INFO",
                    "value": "No free floating licenses found.",
                }
            ]
        },
    )
    with patch("netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=payload)):
        from netlicensing_mcp.server import netlicensing_validate_licensee

        out = json.loads(
            await netlicensing_validate_licensee(
                "I1", product_module_number="M2", session_id="s3", action="checkOut"
            )
        )
    assert out["items"][0]["valid"] == "false"
    assert "No free floating licenses found." in out["warnings"]


def test_n2_list_paging_infos_are_not_warnings():
    payload = _resp(infos={"info": [{"type": "INFO", "value": "Page index is not provided."}]})
    assert wrap(payload, "License", as_list=True)["warnings"] == []
