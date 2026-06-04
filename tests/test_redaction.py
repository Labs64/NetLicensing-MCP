"""Tests for P0.3: Redaction layer.

Covers:
- redact() with plain dict keys
- redact() with NetLicensing property arrays
- MCP_REDACT_FIELDS extension
- tag_one_time_display()
- redact_token_read() for APIKEY and SHOP tokens
- Integration: create_licensee(licensee_secret=...) never echoes plaintext
- Integration: create_api_token response tagged as shown_once
- Integration: get_token after create_api_token returns masked number
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp.redaction import (
    DEFAULT_REDACT,
    _mask,
    redact,
    redact_token_read,
    tag_one_time_display,
)


# ── Unit: _mask ───────────────────────────────────────────────────────────────


def test_mask_short_value():
    assert _mask("abc") == "****"


def test_mask_exactly_8_chars():
    assert _mask("12345678") == "****"


def test_mask_long_value():
    result = _mask("apikey-abc12345")
    assert result == "api****2345"
    assert "apikey" not in result


def test_mask_preserves_prefix_and_suffix():
    val = "s3creT-value-xyz1"
    result = _mask(val)
    assert result.startswith(val[:3])
    assert result.endswith(val[-4:])
    assert "****" in result


# ── Unit: redact() — plain dict keys ────────────────────────────────────────


def test_redact_plain_dict_masks_sensitive_key():
    payload = {"licenseeSecret": "s3cret", "name": "Acme"}
    result = redact(payload)
    assert result["name"] == "Acme"
    assert result["licenseeSecret"] != "s3cret"
    assert "****" in result["licenseeSecret"]


def test_redact_plain_dict_mode_remove():
    payload = {"apiKey": "abc123", "active": "true"}
    result = redact(payload, mode="remove")
    assert "apiKey" not in result
    assert result["active"] == "true"


def test_redact_does_not_touch_non_sensitive_keys():
    payload = {"number": "P001", "name": "Test Product", "active": "true"}
    result = redact(payload)
    assert result == payload


def test_redact_nested_dict():
    payload = {"outer": {"nodeSecret": "secret123", "keep": "yes"}}
    result = redact(payload)
    assert "****" in result["outer"]["nodeSecret"]
    assert result["outer"]["keep"] == "yes"


def test_redact_list_of_dicts():
    payload = [
        {"apiKey": "key1", "role": "ADMIN"},
        {"apiKey": "key2", "role": "USER"},
    ]
    result = redact(payload)
    assert isinstance(result, list)
    for item in result:
        assert "****" in item["apiKey"]
        assert item["role"] in ("ADMIN", "USER")


# ── Unit: redact() — NetLicensing property arrays ────────────────────────────


def test_redact_property_array_masks_sensitive_name():
    payload = {
        "items": {
            "item": [
                {
                    "type": "Licensee",
                    "property": [
                        {"name": "number", "value": "I001"},
                        {"name": "licenseeSecret", "value": "s3cret"},
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }
    result = redact(payload)
    props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
    assert props["number"] == "I001"
    assert props["active"] == "true"
    assert "s3cret" not in props["licenseeSecret"]
    assert "****" in props["licenseeSecret"]


def test_redact_property_array_mode_remove():
    payload = {
        "property": [
            {"name": "nodeSecret", "value": "n0de-secret"},
            {"name": "name", "value": "keep-me"},
        ]
    }
    result = redact(payload, mode="remove")
    names = [p.get("name") for p in result["property"]]
    assert "nodeSecret" in names  # key kept, value dropped
    # value should be gone
    ns_entry = next(p for p in result["property"] if p["name"] == "nodeSecret")
    assert "value" not in ns_entry
    assert any(p["name"] == "name" for p in result["property"])


def test_redact_multiple_sensitive_fields():
    payload = {
        "property": [
            {"name": "apiKey", "value": "longapikey1234"},
            {"name": "password", "value": "hunter2"},
            {"name": "active", "value": "true"},
        ]
    }
    result = redact(payload)
    for p in result["property"]:
        if p["name"] in DEFAULT_REDACT:
            assert "****" in p["value"]
        else:
            assert p["value"] == "true"


# ── Unit: MCP_REDACT_FIELDS extension ────────────────────────────────────────


def test_mcp_redact_fields_extends_set(monkeypatch):
    monkeypatch.setenv("MCP_REDACT_FIELDS", "ssn,phone")
    payload = {"ssn": "123-45-6789", "phone": "555-1234", "name": "Alice"}
    result = redact(payload)
    assert "****" in result["ssn"]
    assert "****" in result["phone"]
    assert result["name"] == "Alice"


def test_mcp_redact_fields_with_spaces(monkeypatch):
    monkeypatch.setenv("MCP_REDACT_FIELDS", " customSecret , token ")
    payload = {"customSecret": "abc123456789", "token": "tok-xyz9876"}
    result = redact(payload)
    assert "****" in result["customSecret"]
    assert "****" in result["token"]


def test_mcp_redact_fields_empty_does_not_affect(monkeypatch):
    monkeypatch.setenv("MCP_REDACT_FIELDS", "")
    payload = {"name": "safe", "active": "true"}
    result = redact(payload)
    assert result == payload


# ── Unit: tag_one_time_display() ─────────────────────────────────────────────


def test_tag_one_time_display_adds_fields():
    response = {"items": {"item": [{"property": [{"name": "number", "value": "TK001"}]}]}}
    result = tag_one_time_display(response)
    assert result["shown_once"] is True
    assert "_warning" in result
    assert "once" in result["_warning"].lower()


def test_tag_one_time_display_preserves_original_data():
    response = {"items": {"item": [{"property": [{"name": "tokenType", "value": "APIKEY"}]}]}}
    result = tag_one_time_display(response)
    assert result["items"] == response["items"]


def test_tag_one_time_display_non_dict_passthrough():
    assert tag_one_time_display("plain string") == "plain string"
    assert tag_one_time_display(None) is None
    assert tag_one_time_display([1, 2, 3]) == [1, 2, 3]


# ── Unit: redact_token_read() ─────────────────────────────────────────────────


@pytest.fixture
def apikey_token_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "actual-api-key-value-1234"},
                        {"name": "tokenType", "value": "APIKEY"},
                        {"name": "role", "value": "ROLE_APIKEY_ANALYTICS"},
                        {"name": "active", "value": "true"},
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
                        {"name": "number", "value": "TK-shop-001"},
                        {"name": "tokenType", "value": "SHOP"},
                        {
                            "name": "shopURL",
                            "value": "https://netlicensing.io/shop?token=onetimetoken123",
                        },
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }


@pytest.fixture
def mixed_token_list_response(apikey_token_response, shop_token_response):
    return {
        "items": {
            "item": [
                apikey_token_response["items"]["item"][0],
                shop_token_response["items"]["item"][0],
            ]
        }
    }


def test_redact_token_read_masks_apikey_number(apikey_token_response):
    result = redact_token_read(apikey_token_response)
    props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
    assert "actual-api-key-value-1234" not in props["number"]
    assert "****" in props["number"]
    # role and active preserved
    assert props["role"] == "ROLE_APIKEY_ANALYTICS"
    assert props["active"] == "true"


def test_redact_token_read_masks_shop_url(shop_token_response):
    result = redact_token_read(shop_token_response)
    props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
    assert "onetimetoken123" not in props["shopURL"]
    assert "****" in props["shopURL"]
    # shop token's number is an opaque ID, not the secret — still preserved
    assert props["number"] == "TK-shop-001"


def test_redact_token_read_mixed_list(mixed_token_list_response):
    result = redact_token_read(mixed_token_list_response)
    items = result["items"]["item"]
    assert len(items) == 2

    # First item: APIKEY — number masked
    apikey_props = {p["name"]: p["value"] for p in items[0]["property"]}
    assert "****" in apikey_props["number"]

    # Second item: SHOP — shopURL masked
    shop_props = {p["name"]: p["value"] for p in items[1]["property"]}
    assert "****" in shop_props["shopURL"]
    assert shop_props["number"] == "TK-shop-001"


def test_redact_token_read_passthrough_for_unknown_type():
    response = {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "TK999"},
                        {"name": "tokenType", "value": "CUSTOM"},
                        {"name": "active", "value": "true"},
                    ],
                }
            ]
        }
    }
    result = redact_token_read(response)
    props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
    assert props["number"] == "TK999"


def test_redact_token_read_also_applies_default_redact():
    response = {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "tokenType", "value": "APIKEY"},
                        {"name": "number", "value": "real-api-key-9876"},
                        {"name": "secret", "value": "top-secret-value"},
                    ],
                }
            ]
        }
    }
    result = redact_token_read(response)
    props = {p["name"]: p["value"] for p in result["items"]["item"][0]["property"]}
    assert "****" in props["number"]  # APIKEY token-specific mask
    assert "****" in props["secret"]  # DEFAULT_REDACT mask


# ── Integration: create_licensee with licensee_secret ────────────────────────


@pytest.fixture
def licensee_with_secret_response():
    """Simulates an API response that echoes back the licenseeSecret."""
    return {
        "items": {
            "item": [
                {
                    "type": "Licensee",
                    "property": [
                        {"name": "number", "value": "I001"},
                        {"name": "active", "value": "true"},
                        {"name": "licenseeSecret", "value": "s3cret-value"},
                        {"name": "productNumber", "value": "P001"},
                    ],
                }
            ]
        }
    }


async def test_create_licensee_never_echoes_plaintext_secret(licensee_with_secret_response):
    """create_licensee round-trip must never expose the plaintext licenseeSecret."""
    with patch(
        "netlicensing_mcp.tools.licensees.nl_post",
        new=AsyncMock(return_value=licensee_with_secret_response),
    ):
        from netlicensing_mcp.server import netlicensing_create_licensee

        result = await netlicensing_create_licensee(
            product_number="P001",
            licensee_secret="s3cret-value",
        )

    assert "s3cret-value" not in result
    assert "****" in result


# ── Integration: create_api_token tagged as shown_once ───────────────────────


@pytest.fixture
def api_token_create_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "actual-api-key-value-5678"},
                        {"name": "tokenType", "value": "APIKEY"},
                        {"name": "role", "value": "ROLE_APIKEY_ANALYTICS"},
                    ],
                }
            ]
        }
    }


async def test_create_api_token_tagged_shown_once(api_token_create_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_post",
        new=AsyncMock(return_value=api_token_create_response),
    ):
        from netlicensing_mcp.server import netlicensing_create_api_token

        result_str = await netlicensing_create_api_token()

    result = json.loads(result_str)
    assert result.get("shown_once") is True
    assert "_warning" in result


async def test_create_api_token_shows_full_key_once(api_token_create_response):
    """The API key number is visible in the one-time create response."""
    with patch(
        "netlicensing_mcp.tools.tokens.nl_post",
        new=AsyncMock(return_value=api_token_create_response),
    ):
        from netlicensing_mcp.server import netlicensing_create_api_token

        result_str = await netlicensing_create_api_token()

    # The full value should appear at creation time (one-time display).
    assert "actual-api-key-value-5678" in result_str


# ── Integration: get_token returns masked number ─────────────────────────────


async def test_get_token_masks_apikey_number(api_token_create_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_get",
        new=AsyncMock(return_value=api_token_create_response),
    ):
        from netlicensing_mcp.server import netlicensing_get_token

        result_str = await netlicensing_get_token("actual-api-key-value-5678")

    assert "actual-api-key-value-5678" not in result_str
    assert "****" in result_str


async def test_list_tokens_masks_apikey_number(api_token_create_response):
    list_response = {"items": {"item": api_token_create_response["items"]["item"]}}
    with patch(
        "netlicensing_mcp.tools.tokens.nl_get",
        new=AsyncMock(return_value=list_response),
    ):
        from netlicensing_mcp.server import netlicensing_list_tokens

        result_str = await netlicensing_list_tokens()

    assert "actual-api-key-value-5678" not in result_str
    assert "****" in result_str


# ── Integration: create_shop_token tagged as shown_once ──────────────────────


@pytest.fixture
def shop_token_create_response():
    return {
        "items": {
            "item": [
                {
                    "type": "Token",
                    "property": [
                        {"name": "number", "value": "TK-shop-xyz"},
                        {"name": "tokenType", "value": "SHOP"},
                        {
                            "name": "shopURL",
                            "value": "https://netlicensing.io/shop?token=onetimeshoptoken",
                        },
                    ],
                }
            ]
        }
    }


async def test_create_shop_token_tagged_shown_once(shop_token_create_response):
    with patch(
        "netlicensing_mcp.tools.tokens.nl_post",
        new=AsyncMock(return_value=shop_token_create_response),
    ):
        from netlicensing_mcp.server import netlicensing_create_shop_token

        result_str = await netlicensing_create_shop_token(licensee_number="I001")

    result = json.loads(result_str)
    assert result.get("shown_once") is True
    assert "_warning" in result
    # The full shopURL should be visible on create
    assert "onetimeshoptoken" in result_str
