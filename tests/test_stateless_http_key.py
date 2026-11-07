"""Regression test: the API key of *each* HTTP request must reach the tool.

In stateful streamable-HTTP mode the MCP SDK runs a session in the task of the
request that created it, so later requests on the same session silently used the
first request's key. ``stateless_http=True`` gives each request its own context.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx

import netlicensing_mcp.server as server
from netlicensing_mcp.client import _log_path, api_key_ctx

_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def _payload(resp: httpx.Response) -> dict:
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    return resp.json()


async def test_each_request_uses_its_own_api_key():
    seen: list[str] = []

    async def fake_nl_get(path, params=None):
        seen.append(api_key_ctx.get())
        return {"items": {"item": []}}

    app = server.mcp.streamable_http_app()
    app.add_middleware(server.ApiKeyMiddleware)
    call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "netlicensing_get_product", "arguments": {"product_number": "P1"}},
    }
    with patch("netlicensing_mcp.tools.products.nl_get", fake_nl_get):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1:8000"
            ) as c:
                for key in ("KEY-A", "KEY-B", "KEY-A"):
                    r = await c.post(
                        "/mcp", headers={**_HEADERS, "x-netlicensing-api-key": key}, json=call
                    )
                    assert r.status_code == 200, r.text
                    assert "error" not in _payload(r), r.text

    assert seen == ["KEY-A", "KEY-B", "KEY-A"]


def test_server_is_stateless():
    assert server.mcp.settings.stateless_http is True


def test_log_path_masks_token_identifier():
    assert _log_path("/token/APIKEY-SECRET") == "/token/****"
    assert _log_path("/token") == "/token"
    assert _log_path("/product/P1") == "/product/P1"


async def test_debug_log_does_not_contain_token_number(caplog):
    import logging
    from unittest.mock import AsyncMock

    import netlicensing_mcp.client as client

    fake = AsyncMock()
    fake.get.return_value = httpx.Response(200, json={})
    tok = client.api_key_ctx.set("k")
    try:
        with (
            patch("netlicensing_mcp.client._get_client", return_value=fake),
            caplog.at_level(logging.DEBUG, logger="netlicensing_mcp.client"),
        ):
            await client.nl_get("/token/SUPER-SECRET-KEY")
    finally:
        client.api_key_ctx.reset(tok)
    assert "SUPER-SECRET-KEY" not in caplog.text
    assert "/token/****" in caplog.text
