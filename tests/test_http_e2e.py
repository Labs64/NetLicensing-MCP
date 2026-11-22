"""End to end over the real HTTP app, the way a remote MCP client sees it.

The app is :func:`netlicensing_mcp.server.build_http_app` (what ``main()``
serves in HTTP mode: FastMCP's streamable-HTTP app + ``ApiKeyMiddleware``).
Requests go through the full ASGI stack: middleware, the SDK's session
manager, JSON-RPC, the tool wrapper, the tools layer and ``client.py``. Only
the upstream NetLicensing API is fake: an ``httpx.MockTransport`` swapped in
as the shared client, which records every request it gets. No real network.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Iterator
from importlib.metadata import version as pkg_version
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

import netlicensing_mcp.server as server
from netlicensing_mcp import client, readiness

# The SDK turns on DNS-rebinding protection for a 127.0.0.1 bind (the
# default MCP_HOST) and then accepts only 127.0.0.1 / localhost Host headers.
BASE = "http://127.0.0.1:8000"
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
DEFAULT_TOOL_COUNT = 61


def _product(number: str) -> dict[str, Any]:
    return {
        "items": {
            "item": [
                {
                    "type": "Product",
                    "property": [
                        {"name": "number", "value": number},
                        {"name": "active", "value": "true"},
                        {"name": "name", "value": f"Product {number}"},
                    ],
                }
            ]
        }
    }


class Upstream:
    """Fake NetLicensing API: answers ``GET /product/{n}``; records requests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.unreachable = False

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.unreachable:
            raise httpx.ConnectError("down", request=request)
        prefix = "/core/v2/rest/product/"
        if request.url.path.startswith(prefix):
            return httpx.Response(200, json=_product(request.url.path[len(prefix) :]))
        return httpx.Response(404, json={})

    def keys(self) -> list[str]:
        """The API key each tool request sent upstream (Basic ``apiKey:<key>``)."""
        out = []
        for r in self.requests:
            scheme, _, token = r.headers["authorization"].partition(" ")
            assert scheme == "Basic"
            user, _, key = base64.b64decode(token).decode().partition(":")
            assert user == "apiKey"
            out.append(key)
        return out


@pytest.fixture()
def upstream(monkeypatch: pytest.MonkeyPatch) -> Upstream:
    up = Upstream()
    monkeypatch.setattr(client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(up)))
    monkeypatch.setattr(client, "BASE_URL", "https://upstream.test/core/v2/rest")
    # A fresh probe: no /ready result cached by another test.
    monkeypatch.setattr(readiness, "upstream_probe", readiness.UpstreamProbe())
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
    return up


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    # The SDK's session manager can run only once; give each test a fresh one.
    monkeypatch.setattr(server.mcp, "_session_manager", None)
    return server.build_http_app()


@pytest.fixture()
def http(app, upstream: Upstream) -> Iterator[TestClient]:
    """TestClient with the app's lifespan (the MCP session manager) running."""
    with TestClient(app, base_url=BASE) as c:
        yield c


def _rpc(method: str, params: dict[str, Any] | None = None, id_: int = 1) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def _initialize() -> dict[str, Any]:
    return _rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test", "version": "0"},
        },
    )


def _get_product(number: str, id_: int = 3) -> dict[str, Any]:
    return _rpc(
        "tools/call",
        {"name": "netlicensing_get_product", "arguments": {"product_number": number}},
        id_,
    )


def _result(resp: httpx.Response) -> dict[str, Any]:
    """The JSON-RPC ``result`` from an SSE (or plain JSON) MCP response."""
    assert resp.status_code == 200, resp.text
    body = None
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            body = json.loads(line[5:])
    if body is None:
        body = resp.json()
    assert "error" not in body, body
    return body["result"]


def _key(key: str) -> dict[str, str]:
    return {**HEADERS, "x-netlicensing-api-key": key}


# ── Probes ───────────────────────────────────────────────────────────────────


def test_health(http: TestClient, upstream: Upstream):
    r = http.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "server": "netlicensing-mcp"}
    assert upstream.requests == []


def test_ready_when_upstream_reachable(http: TestClient, upstream: Upstream):
    r = http.get("/ready")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"
    assert r.json()["checks"]["upstream"] == {"ok": True, "host": "upstream.test", "cached": False}
    assert [req.url.path for req in upstream.requests] == ["/core/v2/rest"]


def test_not_ready_when_upstream_unreachable(http: TestClient, upstream: Upstream):
    upstream.unreachable = True
    r = http.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"
    assert r.json()["checks"]["upstream"]["error"] == "connect_error"


# ── MCP over HTTP ────────────────────────────────────────────────────────────


def test_mcp_without_key_is_401(http: TestClient, upstream: Upstream):
    r = http.post("/mcp", headers=HEADERS, json=_initialize())
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == 'Bearer realm="netlicensing-mcp"'
    assert "x-netlicensing-api-key" in r.json()["error"]
    assert upstream.requests == []


def test_initialize_with_header_key(http: TestClient):
    result = _result(http.post("/mcp", headers=_key("KEY-A"), json=_initialize()))
    assert result["serverInfo"]["name"] == "netlicensing-mcp"
    assert "tools" in result["capabilities"]
    assert "NetLicensing" in result["instructions"]
    # The netlicensing-mcp version, not the MCP SDK's (the SDK's fallback).
    assert result["serverInfo"]["version"] == server._server_version()
    assert result["serverInfo"]["version"] == pkg_version("netlicensing-mcp")
    assert result["serverInfo"]["version"] != pkg_version("mcp")


def test_initialize_with_bearer_key(http: TestClient):
    headers = {**HEADERS, "authorization": "Bearer KEY-A"}
    result = _result(http.post("/mcp", headers=headers, json=_initialize()))
    assert result["serverInfo"]["name"] == "netlicensing-mcp"


def test_tools_list_has_the_default_tool_count(http: TestClient, upstream: Upstream):
    result = _result(http.post("/mcp", headers=_key("KEY-A"), json=_rpc("tools/list", id_=2)))
    names = [t["name"] for t in result["tools"]]
    assert len(names) == DEFAULT_TOOL_COUNT
    assert len(set(names)) == DEFAULT_TOOL_COUNT
    assert "netlicensing_get_product" in names
    assert all(n.startswith("netlicensing_") for n in names)
    assert upstream.requests == []  # listing tools never calls NetLicensing


def test_tool_call_returns_the_envelope(http: TestClient, upstream: Upstream):
    result = _result(http.post("/mcp", headers=_key("KEY-A"), json=_get_product("P1")))
    expected = {
        "number": "P1",
        "active": True,
        "name": "Product P1",
        "type": "Product",
        "console_url": "https://ui.netlicensing.io/#/products/P1/edit",
        "warnings": [],
        "suggested_actions": [],
    }
    assert result["isError"] is False
    assert result["structuredContent"] == expected
    assert [c["type"] for c in result["content"]] == ["text"]
    assert json.loads(result["content"][0]["text"]) == expected

    assert len(upstream.requests) == 1
    req = upstream.requests[0]
    assert (req.method, req.url.host, req.url.path) == (
        "GET",
        "upstream.test",
        "/core/v2/rest/product/P1",
    )
    assert upstream.keys() == ["KEY-A"]


def test_sequential_requests_use_their_own_key(http: TestClient, upstream: Upstream):
    for i, key in enumerate(("KEY-A", "KEY-B", "KEY-A")):
        result = _result(http.post("/mcp", headers=_key(key), json=_get_product(f"P{i}")))
        assert result["isError"] is False
    assert upstream.keys() == ["KEY-A", "KEY-B", "KEY-A"]


async def test_concurrent_requests_do_not_leak_keys(
    app, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
):
    """Two requests in flight at once, different keys: each reaches upstream with its own."""
    arrived: list[str] = []
    both_in_flight = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        arrived.append(request.url.path)
        if len(arrived) == 2:
            both_in_flight.set()
        # Hold each upstream call until the other one has started too.
        await asyncio.wait_for(both_in_flight.wait(), timeout=5)
        return await upstream(request)

    monkeypatch.setattr(
        client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as c:
            ra, rb = await asyncio.gather(
                c.post("/mcp", headers=_key("KEY-A"), json=_get_product("PA")),
                c.post("/mcp", headers=_key("KEY-B"), json=_get_product("PB")),
            )

    assert _result(ra)["structuredContent"]["number"] == "PA"
    assert _result(rb)["structuredContent"]["number"] == "PB"
    seen = {r.url.path.rsplit("/", 1)[1]: key for r, key in zip(upstream.requests, upstream.keys())}
    assert seen == {"PA": "KEY-A", "PB": "KEY-B"}
