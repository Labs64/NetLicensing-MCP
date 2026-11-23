"""Fixes for the v1.1.3 audit: F-2 (client-side filter), F-3 (Floating), F-4 (token kept on failure)."""

import json
from unittest.mock import AsyncMock, patch


from netlicensing_mcp import safety
from netlicensing_mcp.client import _apply_client_filter
from netlicensing_mcp.mcp_tools.products import netlicensing_update_product
from netlicensing_mcp.workflows.validation_explain import explain_validation


def _prop_item(**props):
    return {"property": [{"name": k, "value": v} for k, v in props.items()]}


def test_f2_status_filter_drops_totals_and_warns():
    body = {
        "items": {
            "totalitems": "414",
            "totalpages": "5",
            "hasnext": "true",
            "item": [_prop_item(status="CLOSED")],
        }
    }
    out = _apply_client_filter(body, "status=CLOSED")
    assert "totalitems" not in out["items"] and out["items"]["hasnext"] == "true"
    assert any(i["type"] == "WARNING" for i in out["infos"]["info"])


def test_f2_empty_page_with_more_pages_warns():
    body = {"items": {"hasnext": "true", "item": [_prop_item(status="CLOSED")]}}
    out = _apply_client_filter(body, "status=PENDING")
    assert out["items"]["item"] == []
    assert out["infos"]["info"]


def test_f2_honoured_filter_keeps_totals():
    body = {"items": {"totalitems": "1", "item": [_prop_item(active="true")]}}
    assert _apply_client_filter(body, "active=true") == body


def _floating(valid="false", **extra):
    return {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M"},
                        {"name": "licensingModel", "value": "Floating"},
                        {"name": "valid", "value": valid},
                        *({"name": k, "value": v} for k, v in extra.items()),
                    ],
                }
            ]
        }
    }


def test_f3_floating_without_session_is_unknown_not_no_seat():
    out = explain_validation(_floating())
    m = out["modules"][0]
    assert m["state"] == "unknown"
    assert "no free session" not in m["explanation"]
    assert "session" in m["explanation"]
    assert not any("raise maxSessions" in a for a in m["suggested_actions"])


def test_f3_floating_saturated_still_reported():
    out = explain_validation(_floating(maxSessions="1", activeSessions="1"))
    assert out["modules"][0]["state"] == "invalid"


async def test_f4_token_survives_upstream_failure():
    token, _ = safety.issue_token("update_product", "P", changes=(("vat_mode", "NET"),))
    from netlicensing_mcp.client import NetLicensingError

    with (
        patch(
            "netlicensing_mcp.mcp_tools.products.products.update_product",
            AsyncMock(side_effect=NetLicensingError(400, "nope")),
        ),
        patch(
            "netlicensing_mcp.mcp_tools.products.products.get_product",
            AsyncMock(return_value={"items": {"item": [_prop_item(vatMode="GROSS")]}}),
        ),
    ):
        r = json.loads(await netlicensing_update_product("P", vat_mode="NET", confirm_token=token))
    assert r["error"] is True
    # Not consumed for good: the same token passes validation again.
    safety.validate_and_consume(token, "update_product", "P", changes=(("vat_mode", "NET"),))
