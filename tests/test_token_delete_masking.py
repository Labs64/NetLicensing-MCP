"""Delete-token outputs never echo the token number in full (Task 8b).

For APIKEY tokens the token ``number`` is the API key, for SHOP tokens it is
the credential in the checkout URL. The read paths already mask it
(``redact_token_read``); these tests pin the same for the three delete-token
outputs: the preview's ``target``, the delete success message and the
confirm-token mismatch error. Masking is display-only: the confirmation token
stays bound to the real token number.

Rule: the token type is not known on the confirmed-delete and mismatch paths
without another API call, so every token number is masked in these outputs,
whatever its type, with the read-path mask (first 3 + last 4 characters for
16+ characters, ``****`` below that).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent

from netlicensing_mcp import safety
from netlicensing_mcp.redaction import mask_token_number
from netlicensing_mcp.server import mcp

KEY = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
KEY_MASKED = "a1b****7890"
OTHER = "f0e1d2c3-b4a5-9687-fedc-ba0987654321"
OTHER_MASKED = "f0e****4321"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
    safety._store.clear()
    yield
    safety._store.clear()


def _token_resp(number: str, token_type: str, **extra: str) -> dict:
    props = {"number": number, "tokenType": token_type, **extra}
    return {
        "items": {
            "item": [
                {"type": "Token", "property": [{"name": k, "value": v} for k, v in props.items()]}
            ]
        }
    }


async def _call(name: str, arguments: dict) -> CallToolResult:
    async with create_connected_server_and_client_session(mcp) as session:
        return await session.call_tool(name, arguments)


def _text(result: CallToolResult) -> str:
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _everything(result: CallToolResult) -> str:
    return _text(result) + json.dumps(result.structuredContent)


# ── The mask helper ──────────────────────────────────────────────────────────


def test_mask_token_number_uses_the_read_path_mask():
    assert mask_token_number(KEY) == KEY_MASKED
    assert mask_token_number("TK001") == "****"


# ── 1. Preview target ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("netlicensing_preview_delete_token", {"token_number": KEY}),
        ("netlicensing_delete_token", {"token_number": KEY}),
    ],
)
@pytest.mark.parametrize(
    ("token_type", "extra"),
    [
        ("APIKEY", {"role": "ROLE_APIKEY_ADMIN"}),
        ("SHOP", {"shopURL": f"https://go.netlicensing.io/shop/v2/?shoptoken={KEY}"}),
    ],
)
async def test_preview_masks_secret_token_number(tool, args, token_type, extra):
    resp = _token_resp(KEY, token_type, **extra)
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=resp)):
        result = await _call(tool, args)

    assert result.isError is False
    assert KEY not in _everything(result)
    assert result.structuredContent is not None
    assert result.structuredContent == json.loads(_text(result))
    assert result.structuredContent["target"] == KEY_MASKED
    assert KEY_MASKED in _text(result)
    assert result.structuredContent["operation"] == "delete_token"
    assert result.structuredContent["affected"]["token_type"] == token_type
    assert result.structuredContent["confirmation_token"].startswith("CONF-")


async def test_preview_of_non_secret_token_type_is_still_recognisable():
    resp = _token_resp(OTHER, "DEFAULT")
    with patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=resp)):
        result = await _call("netlicensing_preview_delete_token", {"token_number": OTHER})

    sc = result.structuredContent
    assert sc is not None
    # Same mask, so the user can still tell which token it is; the type is shown.
    assert sc["target"] == OTHER_MASKED
    assert sc["affected"]["token_type"] == "DEFAULT"
    assert OTHER not in _everything(result)


def test_preview_builder_masks_only_the_display_not_the_binding():
    preview = safety.make_delete_preview("delete_token", KEY, affected={})
    assert preview["target"] == KEY_MASKED
    assert KEY not in json.dumps(preview)
    # The masked value is not accepted as the target: the binding is the real one.
    with pytest.raises(ValueError):
        safety.validate_and_consume(preview["confirmation_token"], "delete_token", KEY_MASKED)
    safety.validate_and_consume(preview["confirmation_token"], "delete_token", KEY)


def test_preview_builder_leaves_other_targets_alone():
    preview = safety.make_delete_preview("delete_product", "P001", affected={})
    assert preview["target"] == "P001"


# ── 2. Delete success message + round trip ──────────────────────────────────


@pytest.mark.parametrize("token_type", ["APIKEY", "SHOP"])
async def test_round_trip_preview_then_delete_masks_the_message(token_type):
    resp = _token_resp(KEY, token_type)
    deleted = AsyncMock(return_value=204)
    with (
        patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=resp)),
        patch("netlicensing_mcp.tools.tokens.nl_delete", deleted),
    ):
        preview = await _call("netlicensing_preview_delete_token", {"token_number": KEY})
        assert preview.structuredContent is not None
        token = preview.structuredContent["confirmation_token"]
        result = await _call(
            "netlicensing_delete_token", {"token_number": KEY, "confirm_token": token}
        )
        # Single use: the same token is rejected the second time.
        again = await _call(
            "netlicensing_delete_token", {"token_number": KEY, "confirm_token": token}
        )

    # The real number reached the API.
    deleted.assert_awaited_once_with(f"/token/{KEY}")
    assert result.isError is False
    assert json.loads(_text(result))["message"] == f"Token {KEY_MASKED} deleted (HTTP 204)."
    assert result.structuredContent is not None
    assert result.structuredContent["target"] == KEY_MASKED
    assert KEY not in _everything(result)
    assert again.isError is True
    assert KEY not in _everything(again)


async def test_tools_layer_delete_message_is_masked():
    with patch("netlicensing_mcp.tools.tokens.nl_delete", AsyncMock(return_value=204)):
        from netlicensing_mcp.tools.tokens import delete_token

        message = await delete_token(KEY)
    assert json.loads(message)["message"] == f"Token {KEY_MASKED} deleted (HTTP 204)."
    assert json.loads(message)["target"] == KEY_MASKED


# ── 3. Confirm-token mismatch error ──────────────────────────────────────────


async def test_mismatch_error_names_neither_number_in_full():
    resp_key = _token_resp(KEY, "APIKEY")
    deleted = AsyncMock(return_value=204)
    with (
        patch("netlicensing_mcp.tools.tokens.nl_get", AsyncMock(return_value=resp_key)),
        patch("netlicensing_mcp.tools.tokens.nl_delete", deleted),
    ):
        preview = await _call("netlicensing_preview_delete_token", {"token_number": KEY})
        assert preview.structuredContent is not None
        token = preview.structuredContent["confirmation_token"]
        wrong = await _call(
            "netlicensing_delete_token", {"token_number": OTHER, "confirm_token": token}
        )
        deleted.assert_not_awaited()
        # The mismatch does not consume the token; the real target still works.
        right = await _call(
            "netlicensing_delete_token", {"token_number": KEY, "confirm_token": token}
        )

    assert wrong.isError is True
    sc = wrong.structuredContent
    assert sc is not None
    assert sc == json.loads(_text(wrong))
    assert sc["error"] is True
    detail = sc["detail"]
    assert detail == (f"Confirmation token {token!r} does not match this operation or target")
    everything = _everything(wrong)
    assert KEY not in everything
    assert OTHER not in everything
    assert sc["status"] == 400
    assert right.isError is False
    deleted.assert_awaited_once_with(f"/token/{KEY}")


def test_mismatch_from_another_tool_masks_the_stored_token_number():
    """A delete_token confirmation used on another delete tool: the stored target is masked."""
    token, _ = safety.issue_token("delete_token", KEY)
    with pytest.raises(ValueError) as info:
        safety.validate_and_consume(token, "delete_product", "P001")
    message = str(info.value)
    assert KEY not in message
    assert "delete_token" not in message  # the bound operation is not revealed
    assert "P001" not in message


async def test_product_confirmation_on_delete_token_masks_the_key():
    """A preview_delete_product token presented to delete_token: key masked, nothing deleted."""
    one = {"items": {"item": [{"type": "Product", "property": []}]}}
    empty: dict = {"items": {"item": []}}
    deleted = AsyncMock(return_value=204)
    with (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value=one)),
        patch(
            "netlicensing_mcp.tools.product_modules.list_product_modules",
            AsyncMock(return_value=empty),
        ),
        patch("netlicensing_mcp.tools.licensees.list_licensees", AsyncMock(return_value=empty)),
        patch("netlicensing_mcp.tools.tokens.nl_delete", deleted),
    ):
        preview = await _call("netlicensing_preview_delete_product", {"product_number": "P001"})
        assert preview.structuredContent is not None
        token = preview.structuredContent["confirmation_token"]
        result = await _call(
            "netlicensing_delete_token", {"token_number": KEY, "confirm_token": token}
        )

    deleted.assert_not_awaited()
    assert result.isError is True
    sc = result.structuredContent
    assert sc is not None
    assert sc == json.loads(_text(result))
    assert sc["detail"] == f"Confirmation token {token!r} does not match this operation or target"
    assert KEY not in _everything(result)


def test_mismatch_between_non_secret_operations_is_unchanged():
    token, _ = safety.issue_token("delete_product", "P001")
    with pytest.raises(ValueError) as info:
        safety.validate_and_consume(token, "delete_product", "P002")
    message = str(info.value)
    assert message == f"Confirmation token {token!r} does not match this operation or target"
    assert "P001" not in message and "P002" not in message
