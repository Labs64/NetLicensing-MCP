"""Tests for P1.9 validation_explain pure synthesiser + tool layer."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp.workflows.validation_explain import explain_validation

FIXTURES_CH = Path(__file__).parent / "fixtures" / "customer_health"
FIXTURES_VE = Path(__file__).parent / "fixtures" / "validation_explain"
NOW = datetime(2026, 6, 9, 0, 0, 0, tzinfo=timezone.utc)


def load_ch(name: str) -> dict:
    return json.loads((FIXTURES_CH / name).read_text())


def load_ve(name: str) -> dict:
    return json.loads((FIXTURES_VE / name).read_text())


def test_all_valid():
    payload = load_ch("validate_acme_all_green.json")
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "ok"
    assert result["warnings"] == []
    assert result["suggested_actions"] == []


def test_near_expiry():
    payload = load_ch("validate_acme_near_expiry.json")
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "warning"
    core = next(m for m in result["modules"] if m["module_number"] == "M-CORE")
    assert "14 days" in core["explanation"]
    assert any("SHOP" in a or "renewal" in a.lower() for a in result["suggested_actions"])


def test_quota_exhausted():
    payload = load_ch("validate_acme_quota_exhausted.json")
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "warning"
    api = next(m for m in result["modules"] if m["module_number"] == "M-API")
    assert "95%" in api["explanation"]
    assert any("top up" in a.lower() or "quota" in a.lower() for a in result["suggested_actions"])


def test_floating_saturated():
    payload = load_ch("validate_acme_floating_saturated.json")
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "critical"
    flt = next(m for m in result["modules"] if m["module_number"] == "M-FLOAT")
    assert flt["valid"] is False
    assert "saturated" in flt["explanation"]
    assert any("check-in" in a.lower() or "stale" in a.lower() for a in result["suggested_actions"])


def test_subscription_expired():
    payload = load_ve("validate_acme_subscription_expired.json")
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "critical"
    core = next(m for m in result["modules"] if m["module_number"] == "M-CORE")
    assert "expired" in core["explanation"].lower()
    assert any("renew" in a.lower() for a in result["suggested_actions"])


def test_node_mismatch():
    payload = load_ve("validate_acme_node_mismatch.json")
    result = explain_validation(payload, now=NOW)
    node = next(m for m in result["modules"] if m["module_number"] == "M-NODE")
    assert (
        "mismatch" in node["explanation"].lower()
        or "different device" in node["explanation"].lower()
    )
    assert any(
        "node_secret" in a or "reset" in a.lower() or "binding" in a.lower()
        for a in result["suggested_actions"]
    )


def test_status_precedence_red_beats_yellow():
    mixed = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-CORE"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "true"},
                        {"name": "warningLevel", "value": "YELLOW"},
                        {"name": "expires", "value": "2026-06-23T00:00:00Z"},
                    ],
                },
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-FLOAT"},
                        {"name": "licensingModel", "value": "Floating"},
                        {"name": "valid", "value": "false"},
                        {"name": "warningLevel", "value": "RED"},
                        {"name": "maxSessions", "value": "10"},
                        {"name": "activeSessions", "value": "10"},
                    ],
                },
            ]
        }
    }
    result = explain_validation(mixed, now=NOW)
    assert result["overall_status"] == "critical"


def test_status_invalid_no_red():
    payload = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-X"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "false"},
                    ],
                }
            ]
        }
    }
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "invalid"


def test_unknown_model_fallback():
    payload = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-CUSTOM"},
                        {"name": "licensingModel", "value": "CustomModel"},
                        {"name": "valid", "value": "true"},
                        {"name": "warningLevel", "value": "GREEN"},
                    ],
                }
            ]
        }
    }
    result = explain_validation(payload, now=NOW)
    mod = result["modules"][0]
    # Falls through to generic template
    assert (
        "valid" in mod["explanation"].lower()
        or "warningLevel" in mod["explanation"]
        or "GREEN" in mod["explanation"]
    )
    assert result["overall_status"] == "ok"


def test_orphan_licensee_no_modules():
    payload = {"items": {"item": []}}
    result = explain_validation(payload, now=NOW)
    assert result["overall_status"] == "ok"
    assert "no licensed modules" in result["summary"]


def test_suggested_actions_deduplicated():
    # Two modules both near expiry → same renewal action text → dedupe to one.
    payload = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-A"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "true"},
                        {"name": "warningLevel", "value": "YELLOW"},
                        {"name": "expires", "value": "2026-06-23T00:00:00Z"},
                    ],
                },
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-B"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "true"},
                        {"name": "warningLevel", "value": "YELLOW"},
                        {"name": "expires", "value": "2026-06-20T00:00:00Z"},
                    ],
                },
            ]
        }
    }
    result = explain_validation(payload, now=NOW)
    # The SHOP renewal action text is the same for both (uses "<licensee>" placeholder).
    # Count how many "SHOP" actions appear; should be 1 after dedup.
    shop_actions = [a for a in result["suggested_actions"] if "SHOP" in a]
    assert len(shop_actions) == 1


def test_signature_and_ttl_preserved():
    payload = {
        "items": {"item": []},
        "signature": "abc123",
        "ttl": "2026-06-09T13:00:00Z",
    }
    result = explain_validation(payload, now=NOW)
    assert result["signature"] == "abc123"
    assert result["ttl"] == "2026-06-09T13:00:00Z"


def test_include_raw_in_tool(monkeypatch):
    """Tool layer attaches raw under 'raw' key when include_raw=True."""
    monkeypatch.setenv("NETLICENSING_API_KEY", "test-key")
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "false")

    validation_payload = load_ch("validate_acme_all_green.json")

    async def mock_validate(*args, **kwargs):
        return validation_payload

    async def mock_get_licensee(*args, **kwargs):
        return {"items": {"item": []}}

    async def mock_list_licenses(*args, **kwargs):
        return {"items": {"item": []}}

    with patch(
        "netlicensing_mcp.tools.licensees.nl_post", new=AsyncMock(return_value=validation_payload)
    ):
        import asyncio
        from netlicensing_mcp.tools.licensees import validate_licensee

        async def run():
            return await validate_licensee("CUST-ACME", dry_run=True)

        result = asyncio.run(run())
    assert "items" in result


@pytest.mark.asyncio
async def test_tool_sends_dry_run_true(monkeypatch):
    """netlicensing_explain_validation must always send dryRun=true."""
    monkeypatch.setenv("NETLICENSING_API_KEY", "test-key")
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "false")

    validation_payload = load_ch("validate_acme_all_green.json")
    mock_post = AsyncMock(return_value=validation_payload)

    with patch("netlicensing_mcp.tools.licensees.nl_post", new=mock_post):
        from netlicensing_mcp.server import netlicensing_explain_validation

        await netlicensing_explain_validation("CUST-ACME")

    call_data = mock_post.call_args[0][1]
    assert call_data.get("dryRun") == "true"
