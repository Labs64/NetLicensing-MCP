"""Fixes for the v1.1.4 connector audit (MCP-layer findings)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp import server
from netlicensing_mcp.client import ClientValidationError, NetLicensingError
from netlicensing_mcp.redaction import redact


def _item(kind: str, **props: str) -> dict:
    return {"type": kind, "property": [{"name": k, "value": v} for k, v in props.items()]}


def _resp(*items: dict) -> dict:
    return {"items": {"item": list(items)}}


# ── F2: update_license gate ──────────────────────────────────────────────────


async def test_update_license_sensitive_change_needs_a_token():
    current = _resp(_item("License", number="L1", active="true", price="1.00", currency="EUR"))
    post = AsyncMock(return_value=current)
    with (
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=current)),
        patch("netlicensing_mcp.tools.licenses.nl_post", post),
    ):
        preview = json.loads(await server.netlicensing_update_license("L1", active=False))
        assert "confirmation_token" in preview
        post.assert_not_called()
        # the token is bound to the previewed change
        wrong = json.loads(
            await server.netlicensing_update_license(
                "L1", active=True, confirm_token=preview["confirmation_token"]
            )
        )
        assert wrong["error"] is True
        post.assert_not_called()
        ok = json.loads(
            await server.netlicensing_update_license(
                "L1", active=False, confirm_token=preview["confirmation_token"]
            )
        )
        assert ok.get("error") is not True
        assert post.call_args[0][1]["active"] == "false"


async def test_update_license_non_sensitive_change_is_direct():
    resp = _resp(_item("License", number="L1", name="x"))
    with patch("netlicensing_mcp.tools.licenses.nl_post", AsyncMock(return_value=resp)) as post:
        out = json.loads(await server.netlicensing_update_license("L1", name="x"))
    assert "confirmation_token" not in out
    post.assert_called_once()


async def test_preview_update_license_validates_price():
    out = json.loads(await server.netlicensing_preview_update_license("L1", price=-1))
    assert out["error"] is True


@pytest.mark.parametrize(
    ("current_quantity", "args", "ok"),
    [("1", {"used_quantity": "9999"}, False), ("10", {"used_quantity": "10"}, True)],
)
async def test_used_quantity_may_not_exceed_quantity(current_quantity, args, ok):
    current = _resp(_item("License", quantity=current_quantity))
    with (
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=current)),
        patch("netlicensing_mcp.tools.licenses.nl_post", AsyncMock(return_value=current)) as post,
    ):
        out = json.loads(await server.netlicensing_update_license("L1", **args))
    assert (out.get("error") is not True) is ok
    assert post.called is ok


async def test_used_quantity_checked_against_new_quantity():
    with (
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock()) as get,
        patch("netlicensing_mcp.tools.licenses.nl_post", AsyncMock(return_value=_resp())),
    ):
        out = json.loads(
            await server.netlicensing_update_license("L1", quantity="20", used_quantity="15")
        )
    assert out.get("error") is not True
    get.assert_not_called()


# ── F3: cascade leaves bundles behind ────────────────────────────────────────


async def test_cascade_delete_reports_orphaned_bundles():
    from netlicensing_mcp.mcp_tools import products as mp

    preview = json.loads(await server.netlicensing_preview_delete_product("P1"))  # noqa: F841
    with (
        patch.object(mp, "_product_bundle_numbers", AsyncMock(return_value=["B1"])),
        patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)),
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value={})),
        patch.object(mp, "_product_delete_preview", AsyncMock(return_value="{}")),
    ):
        from netlicensing_mcp import safety

        token, _ = safety.issue_token("delete_product", "P1", True)
        out = json.loads(
            await server.netlicensing_delete_product("P1", force_cascade=True, confirm_token=token)
        )
    assert out["orphaned_bundles"] == ["B1"]
    assert "not deleted" in out["warnings"][0]
    assert 'netlicensing_preview_delete_bundle(bundle_number="B1")' in out["suggested_actions"]


# ── F4: indexed node secrets ─────────────────────────────────────────────────


def test_indexed_node_secret_is_masked():
    secret = "device-secret-0123456789"
    out = redact({"nodeSecret0": secret, "property": [{"name": "nodeSecret1", "value": secret}]})
    assert secret not in json.dumps(out)


# ── F6: transaction dates ────────────────────────────────────────────────────


async def test_transaction_dates_rejected_by_tool():
    out = json.loads(
        await server.netlicensing_create_transaction(status="PENDING", date_created="2030-01-01")
    )
    assert out["error"] is True and "date_created" in out["detail"]


# ── CB-01: obtain_bundle guard ───────────────────────────────────────────────


async def test_obtain_bundle_refuses_a_repeat():
    bundle = _resp(_item("Bundle", number="B1", licenseTemplateNumbers="T1,T2"))
    held = _resp(_item("License", number="L1", licenseTemplateNumber="T2"))
    post = AsyncMock(return_value=_resp(_item("License", number="L9")))
    with (
        patch("netlicensing_mcp.tools.bundles.nl_get", AsyncMock(return_value=bundle)),
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=held)),
        patch("netlicensing_mcp.tools.bundles.nl_post", post),
    ):
        out = json.loads(await server.netlicensing_obtain_bundle("B1", "I1"))
        assert out["error"] is True and "allow_duplicate" in out["detail"]
        post.assert_not_called()
        again = json.loads(
            await server.netlicensing_obtain_bundle("B1", "I1", allow_duplicate=True)
        )
    assert again.get("error") is not True
    post.assert_called_once()


async def test_obtain_bundle_first_time_goes_through():
    bundle = _resp(_item("Bundle", number="B1", licenseTemplateNumbers="T1"))
    post = AsyncMock(return_value=_resp(_item("License", number="L9")))
    with (
        patch("netlicensing_mcp.tools.bundles.nl_get", AsyncMock(return_value=bundle)),
        patch("netlicensing_mcp.tools.licenses.nl_get", AsyncMock(return_value=_resp())),
        patch("netlicensing_mcp.tools.bundles.nl_post", post),
    ):
        out = json.loads(await server.netlicensing_obtain_bundle("B1", "I1"))
    assert out.get("error") is not True
    post.assert_called_once()


# ── RW-02: gateway block is transient ────────────────────────────────────────


def test_gateway_block_is_retryable_role_403_is_not():
    from netlicensing_mcp.errors import error_hint

    gw = NetLicensingError(403, "blocked", non_json=True)
    assert error_hint(gw, "netlicensing_delete_license")["retryable"] is True
    assert (
        error_hint(NetLicensingError(403, "no"), "netlicensing_delete_license")["retryable"]
        is False
    )


# ── Low items ────────────────────────────────────────────────────────────────


async def test_unknown_filter_key_is_rejected_not_ignored():
    out = json.loads(await server.netlicensing_list_products(filter="name=*"))
    assert out["error"] is True and "name" in out["detail"]


async def test_overlong_name_is_rejected_before_any_request():
    from netlicensing_mcp.tools.helpers import validate_form_data

    with pytest.raises(ClientValidationError, match="255"):
        validate_form_data({"name": "x" * 300})
    with pytest.raises(ClientValidationError) as exc:
        validate_form_data({"description": "y" * 5001})
    assert "y" * 50 not in str(exc.value)


def test_validation_error_never_echoes_huge_input():
    err = ClientValidationError("bad " + "z" * 5000)
    assert len(err.detail) < 400


async def test_out_of_range_page_is_flagged():
    from netlicensing_mcp.responses import wrap

    env = wrap(
        {"items": {"item": [], "pagenumber": "99", "totalpages": "1"}},
        "Product",
        as_list=True,
        paging_filter="page=99",
    )
    assert env["has_more"] is False
    assert any("past the last page" in w for w in env["warnings"])


# ── F5: explain_validation honours a supplied session ────────────────────────


def test_explain_does_not_claim_session_missing_when_supplied():
    from netlicensing_mcp.workflows.validation_explain import explain_validation

    payload = {
        "items": {
            "item": [
                _item(
                    "ProductModuleValidation",
                    productModuleNumber="M1",
                    licensingModel="Floating",
                    valid="false",
                )
            ]
        }
    }
    plain = explain_validation(payload)["modules"][0]
    given = explain_validation(payload, session_modules=frozenset({"M1"}))["modules"][0]
    assert "no session id was supplied" in plain["explanation"]
    assert "no session id was supplied" not in given["explanation"]
    assert all("checkOut" not in a for a in given["suggested_actions"])
