"""Structured tool output (``structuredContent`` + ``outputSchema``).

Every tool still returns a JSON *string* when called directly. The MCP
registration layer (``netlicensing_mcp.app.tool``) adds, over the protocol:

- ``content``: one text block with the identical string;
- ``structuredContent``: ``json.loads(text)`` when it is a JSON object,
  otherwise ``{"result": <value>}`` (lists, scalars, plain text);
- ``isError=True`` for error blobs (``{"error": true, ...}``);
- one shared, permissive ``outputSchema`` on every tool.

The protocol tests go through a real in-memory client/server session.
"""

from __future__ import annotations

import inspect
import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from netlicensing_mcp import server
from netlicensing_mcp.app import to_call_tool_result
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.server import mcp


@pytest.fixture(autouse=True)
def _no_demo_mode(monkeypatch):
    """Keep the demo_mode tag out so outputs are deterministic either way."""
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)


def _item(entity_type: str, **props: str) -> dict:
    return {
        "type": entity_type,
        "property": [{"name": k, "value": v} for k, v in props.items()],
    }


def _resp(*items: dict) -> dict:
    return {"items": {"item": list(items)}}


PRODUCT = _resp(_item("Product", number="P001", name="Test Product", active="true"))
PRODUCTS = _resp(
    _item("Product", number="P001", name="One", active="true"),
    _item("Product", number="P002", name="Two", active="false"),
)
APIKEY_TOKEN = _resp(
    _item(
        "Token",
        number="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        tokenType="APIKEY",
        active="true",
        apiKey="super-secret-api-key",
    )
)


async def _call(name: str, arguments: dict) -> CallToolResult:
    async with create_connected_server_and_client_session(mcp) as session:
        return await session.call_tool(name, arguments)


def _text(result: CallToolResult) -> str:
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


# ── Over the MCP protocol ────────────────────────────────────────────────────


async def test_get_tool_structured_equals_text():
    with patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value=PRODUCT)):
        direct = await server.netlicensing_get_product("P001")
        result = await _call("netlicensing_get_product", {"product_number": "P001"})

    assert _text(result) == direct
    assert result.structuredContent == json.loads(direct)
    assert result.structuredContent["number"] == "P001"
    assert result.isError is False


async def test_list_tool_structured_equals_text():
    with patch("netlicensing_mcp.tools.products.list_products", AsyncMock(return_value=PRODUCTS)):
        direct = await server.netlicensing_list_products()
        result = await _call("netlicensing_list_products", {})

    assert _text(result) == direct
    assert result.structuredContent == json.loads(direct)
    assert result.structuredContent["type"] == "list"
    assert result.structuredContent["count"] == 2
    assert result.isError is False


async def test_error_blob_sets_is_error_and_keeps_text():
    err = NetLicensingError(404, "Product not found")
    with patch("netlicensing_mcp.tools.products.get_product", AsyncMock(side_effect=err)):
        direct = await server.netlicensing_get_product("NOPE")
        result = await _call("netlicensing_get_product", {"product_number": "NOPE"})

    assert _text(result) == direct
    assert result.structuredContent == json.loads(direct)
    assert result.structuredContent == {"error": True, "status": 404, "detail": "Product not found"}
    assert result.isError is True


async def test_token_read_structured_is_redacted_like_text():
    with patch("netlicensing_mcp.tools.tokens.get_token", AsyncMock(return_value=APIKEY_TOKEN)):
        direct = await server.netlicensing_get_token("ignored")
        result = await _call("netlicensing_get_token", {"token_number": "ignored"})

    assert _text(result) == direct
    assert result.structuredContent == json.loads(direct)
    serialized = json.dumps(result.structuredContent)
    assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in serialized
    assert "super-secret-api-key" not in serialized
    assert "console_url" not in result.structuredContent
    assert result.isError is False


async def test_preview_tool_structured_equals_text():
    one = _resp(_item("Product", number="P001"))
    empty = _resp()
    with (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value=one)),
        patch(
            "netlicensing_mcp.tools.product_modules.list_product_modules",
            AsyncMock(return_value=empty),
        ),
        patch("netlicensing_mcp.tools.licensees.list_licensees", AsyncMock(return_value=empty)),
    ):
        result = await _call("netlicensing_delete_product", {"product_number": "P001"})

    text = _text(result)
    assert result.structuredContent == json.loads(text)
    # Same serialization the tool itself uses (_json → json.dumps(indent=2)).
    assert text == json.dumps(result.structuredContent, indent=2)
    assert result.structuredContent["operation"] == "delete_product"
    assert result.structuredContent["target"] == "P001"
    assert "confirmation_token" in result.structuredContent
    assert result.isError is False


async def test_plain_text_result_is_wrapped():
    """Confirmed deletes return plain text (not JSON); it is wrapped as ``result``."""
    preview_one = _resp(_item("Product", number="P001"))
    empty = _resp()
    with (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value=preview_one)),
        patch(
            "netlicensing_mcp.tools.product_modules.list_product_modules",
            AsyncMock(return_value=empty),
        ),
        patch("netlicensing_mcp.tools.licensees.list_licensees", AsyncMock(return_value=empty)),
        patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)),
    ):
        preview = await _call("netlicensing_delete_product", {"product_number": "P001"})
        token = preview.structuredContent["confirmation_token"]
        result = await _call(
            "netlicensing_delete_product", {"product_number": "P001", "confirm_token": token}
        )

    assert _text(result) == "Product P001 deleted (HTTP 204)."
    assert result.structuredContent == {"result": "Product P001 deleted (HTTP 204)."}
    assert result.isError is False


async def test_every_tool_declares_the_shared_output_schema():
    async with create_connected_server_and_client_session(mcp) as session:
        tools = (await session.list_tools()).tools

    assert len(tools) == 61
    schemas = {json.dumps(t.outputSchema, sort_keys=True) for t in tools}
    assert len(schemas) == 1
    schema = tools[0].outputSchema
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    assert "required" not in schema
    # Sent with every tool in tools/list, so it stays minimal: no properties.
    assert set(schema) == {"type", "additionalProperties", "title", "description"}
    assert schema["title"] == "NetLicensingToolResult"
    assert '{"result": value}' in schema["description"]
    assert len(json.dumps(schema)) <= 250


# ── Conversion helper ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "structured", "is_error"),
    [
        ('{"type": "Product", "number": "P1"}', {"type": "Product", "number": "P1"}, False),
        ('{"error": true, "detail": "boom"}', {"error": True, "detail": "boom"}, True),
        ('{"error": false}', {"error": False}, False),
        ('{"error": "true"}', {"error": "true"}, False),
        ("[1, 2]", {"result": [1, 2]}, False),
        ('"just a string"', {"result": "just a string"}, False),
        ("42", {"result": 42}, False),
        ("null", {"result": None}, False),
        ("Product P1 deleted (HTTP 204).", {"result": "Product P1 deleted (HTTP 204)."}, False),
        ("", {"result": ""}, False),
    ],
)
def test_to_call_tool_result(text, structured, is_error):
    result = to_call_tool_result(text)
    assert isinstance(result, CallToolResult)
    assert [b.model_dump() for b in result.content] == [
        TextContent(type="text", text=text).model_dump()
    ]
    assert result.structuredContent == structured
    assert result.isError is is_error


# ── Direct-call contract ─────────────────────────────────────────────────────


async def test_decorator_returns_original_function():
    fn = server.netlicensing_get_product
    assert inspect.signature(fn).return_annotation == "str"
    assert not hasattr(fn, "__wrapped__")
    with patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value=PRODUCT)):
        out = await fn("P001")
    assert isinstance(out, str)
    assert json.loads(out)["number"] == "P001"
