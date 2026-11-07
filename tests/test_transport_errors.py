"""Transport failures and non-JSON replies must surface as NetLicensingError."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import netlicensing_mcp.client as client
from netlicensing_mcp.client import NetLicensingError


@pytest.fixture
def fake_http():
    fake = AsyncMock()
    with patch("netlicensing_mcp.client._get_client", return_value=fake):
        tok = client.api_key_ctx.set("k")
        try:
            yield fake
        finally:
            client.api_key_ctx.reset(tok)


async def _call(helper: str):
    fn = getattr(client, helper)
    if helper in ("nl_post", "nl_put"):
        return await fn("/product/P1", {"a": "b"})
    return await fn("/product/P1")


@pytest.mark.parametrize("helper", ["nl_get", "nl_post", "nl_put", "nl_delete"])
@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (httpx.ReadTimeout("slow"), 504),
        (httpx.ConnectError("refused https://go.netlicensing.io/secret-path"), 502),
    ],
)
async def test_transport_errors_become_netlicensing_error(helper, exc, status, fake_http):
    method = helper.removeprefix("nl_")
    getattr(fake_http, method).side_effect = exc
    with pytest.raises(NetLicensingError) as e:
        await _call(helper)
    assert e.value.status_code == status
    assert "secret-path" not in e.value.detail


@pytest.mark.parametrize("helper", ["nl_get", "nl_post", "nl_put"])
@pytest.mark.parametrize("body", [b"<html>proxy</html>", b"[]", b'"x"'])
async def test_bad_2xx_body_becomes_502(helper, body, fake_http):
    method = helper.removeprefix("nl_")
    getattr(fake_http, method).return_value = httpx.Response(200, content=body)
    with pytest.raises(NetLicensingError) as e:
        await _call(helper)
    assert e.value.status_code == 502


async def test_valid_json_object_still_returned(fake_http):
    fake_http.get.return_value = httpx.Response(200, json={"items": {"item": []}})
    assert await client.nl_get("/product") == {"items": {"item": []}}


async def test_tool_returns_error_blob_on_timeout(fake_http):
    import netlicensing_mcp.server as server

    fake_http.get.side_effect = httpx.ReadTimeout("slow")
    out = json.loads(await server.netlicensing_get_product("P1"))
    assert out["error"] is True
    assert out["status"] == 504
