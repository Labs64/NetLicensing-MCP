"""Tests for P0.6: Normalized response envelope + Console deep links.

Covers:
- console_url() generation for each entity kind and unknown kinds
- MCP_CONSOLE_BASE_URL override and trailing-slash handling
- wrap() single-entity shape (flat dict with promoted properties, console_url,
  active bool, warnings, suggested_actions)
- wrap() list shape and empty-list shape
- include_raw=True attaches the original payload under "raw"
- Server-layer _wrap_json plumbs include_raw through to every tool
- _wrap_json_token_read drops console_url for APIKEY tokens (since the
  number IS the secret) but keeps it for SHOP tokens
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp import server
from netlicensing_mcp.responses import console_url, wrap


# ── console_url ───────────────────────────────────────────────────────────────


def test_console_url_known_kinds():
    assert (
        console_url("Licensee", "CUST-ACME") == "https://ui.netlicensing.io/#/licensees/CUST-ACME"
    )
    assert console_url("Product", "P001") == "https://ui.netlicensing.io/#/products/P001"
    assert console_url("License", "L001") == "https://ui.netlicensing.io/#/licenses/L001"


def test_console_url_unknown_kind_returns_none():
    assert console_url("Banana", "X") is None


def test_console_url_empty_number_returns_none():
    assert console_url("Licensee", "") is None


def test_console_url_respects_env_override(monkeypatch):
    monkeypatch.setenv("MCP_CONSOLE_BASE_URL", "https://staging.example.com/ui/")
    assert console_url("Licensee", "I1") == "https://staging.example.com/ui/licensees/I1"


# ── wrap(): single entity ─────────────────────────────────────────────────────


def _single(kind: str, props: dict[str, str]) -> dict:
    return {
        "items": {
            "item": [
                {
                    "type": kind,
                    "property": [{"name": k, "value": v} for k, v in props.items()],
                }
            ]
        }
    }


def test_wrap_single_entity_flat_envelope():
    raw = _single("Licensee", {"number": "I1", "name": "Acme", "active": "true"})
    env = wrap(raw, "Licensee")

    assert env["type"] == "Licensee"
    assert env["number"] == "I1"
    assert env["name"] == "Acme"
    assert env["active"] is True
    assert env["console_url"] == "https://ui.netlicensing.io/#/licensees/I1"
    assert env["warnings"] == []
    assert env["suggested_actions"] == []
    assert "items" not in env


def test_wrap_active_false_coerced():
    raw = _single("Product", {"number": "P1", "active": "false"})
    env = wrap(raw, "Product")
    assert env["active"] is False


def test_wrap_include_raw_attaches_original_payload():
    raw = _single("Product", {"number": "P1", "active": "true"})
    env = wrap(raw, "Product", raw=raw)
    assert env["raw"] is raw
    assert env["number"] == "P1"


def test_wrap_summary_and_actions():
    raw = _single("Licensee", {"number": "I1", "active": "true"})
    env = wrap(raw, "Licensee", summary="all good", suggested_actions=["do X"])
    assert env["summary"] == "all good"
    assert env["suggested_actions"] == ["do X"]


# ── wrap(): list ──────────────────────────────────────────────────────────────


def _list(kind: str, items: list[dict[str, str]]) -> dict:
    return {
        "items": {
            "item": [
                {
                    "type": kind,
                    "property": [{"name": k, "value": v} for k, v in props.items()],
                }
                for props in items
            ]
        }
    }


def test_wrap_list_envelope():
    raw = _list(
        "Product", [{"number": "P1", "active": "true"}, {"number": "P2", "active": "false"}]
    )
    env = wrap(raw, "Product")

    assert env["type"] == "list"
    assert env["kind"] == "Product"
    assert env["count"] == 2
    assert len(env["items"]) == 2
    assert env["items"][0]["console_url"] == "https://ui.netlicensing.io/#/products/P1"
    assert env["items"][1]["active"] is False


def test_wrap_empty_list():
    raw = {"items": {"item": []}}
    env = wrap(raw, "Product")
    assert env["type"] == "list"
    assert env["count"] == 0
    assert env["items"] == []


# ── Server-layer plumbing: include_raw threads through ───────────────────────


@pytest.mark.asyncio
async def test_tool_default_response_contains_console_url():
    raw = _single("Product", {"number": "P1", "name": "Demo", "active": "true"})
    with patch("netlicensing_mcp.server.products.get_product", AsyncMock(return_value=raw)):
        result = json.loads(await server.netlicensing_get_product("P1"))

    assert result["console_url"] == "https://ui.netlicensing.io/#/products/P1"
    assert "raw" not in result


@pytest.mark.asyncio
async def test_tool_include_raw_true_attaches_raw():
    raw = _single("Product", {"number": "P1", "name": "Demo", "active": "true"})
    with patch("netlicensing_mcp.server.products.get_product", AsyncMock(return_value=raw)):
        result = json.loads(await server.netlicensing_get_product("P1", include_raw=True))

    assert result["console_url"] == "https://ui.netlicensing.io/#/products/P1"
    assert "raw" in result
    assert result["raw"] == raw


# ── Token-read console_url scrubbing ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_token_apikey_drops_console_url():
    raw = _single(
        "Token",
        {"number": "supersecret-apikey-value", "tokenType": "APIKEY"},
    )
    with patch("netlicensing_mcp.server.tokens.get_token", AsyncMock(return_value=raw)):
        result = json.loads(await server.netlicensing_get_token("ignored"))

    assert result["tokenType"] == "APIKEY"
    # console_url would have leaked the api key as a URL path segment.
    assert "console_url" not in result
    # The number itself must be masked by redact_token_read on this read path.
    assert "supersecret-apikey-value" not in json.dumps(result)


@pytest.mark.asyncio
async def test_get_token_shop_keeps_console_url():
    raw = _single(
        "Token",
        {
            "number": "TKN-SHOP-1",
            "tokenType": "SHOP",
            "shopURL": "https://shop.example/checkout/abc",
        },
    )
    with patch("netlicensing_mcp.server.tokens.get_token", AsyncMock(return_value=raw)):
        result = json.loads(await server.netlicensing_get_token("TKN-SHOP-1"))

    assert result["tokenType"] == "SHOP"
    assert result["console_url"] == "https://ui.netlicensing.io/#/tokens/TKN-SHOP-1"
    # shopURL must be masked on read paths.
    assert "shop.example/checkout/abc" not in json.dumps(result)
