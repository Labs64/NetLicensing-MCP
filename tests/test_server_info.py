"""``netlicensing_server_info`` as a first-run check (Task 6).

Every branch of the report: no key, demo, valid key, rejected key (401 /
403), API unreachable (transport error, timeout), other upstream errors and
unexpected exceptions, plus ``check_connection=False``. The HTTP layer is
mocked at ``client._get_client`` as in ``test_transport_errors.py``. No output
or log line may carry the API key or any part of it.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# server first: importing it registers the tools in their canonical order
# (tests/test_tool_registry_snapshot.py checks that order).
import netlicensing_mcp.server as server
import netlicensing_mcp.app as app
import netlicensing_mcp.client as client
import netlicensing_mcp.mcp_tools.utilities as utilities
from netlicensing_mcp.errors import error_hint
from netlicensing_mcp.toolsets import ToolFilter

ENV_KEY = "ENV-KEY-6f1d2c9a8b7e"
HEADER_KEY = "HDR-KEY-3a9b4c5d6e7f"

_PRODUCT_PAGE = {
    "infos": {"info": []},
    "items": {
        "item": [
            {
                "property": [
                    {"name": "number", "value": "P1"},
                    {"name": "active", "value": "true"},
                ],
                "type": "Product",
            }
        ],
        "pagenumber": "0",
        "itemsnumber": "1",
        "totalpages": "18",
        "totalitems": "18",
        "hasnext": "true",
    },
}


def _api_error(status: int, value: str) -> httpx.Response:
    return httpx.Response(
        status, json={"infos": {"info": [{"id": str(status), "type": "ERROR", "value": value}]}}
    )


def _fragments(key: str, size: int = 6) -> set[str]:
    return {key[i : i + size] for i in range(len(key) - size + 1)}


def _assert_no_key(text: str, *keys: str) -> None:
    for key in keys:
        for part in _fragments(key):
            assert part not in text, f"key fragment {part!r} leaked"


@pytest.fixture
def fake_http():
    fake = AsyncMock()
    with patch("netlicensing_mcp.client._get_client", return_value=fake):
        yield fake


@pytest.fixture
def key_default(monkeypatch):
    """Replace the API-key ContextVar with one whose default (the env value) is given."""

    def _set(default: str) -> contextvars.ContextVar[str]:
        var: contextvars.ContextVar[str] = contextvars.ContextVar("api_key", default=default)
        monkeypatch.setattr(client, "api_key_ctx", var)
        return var

    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
    monkeypatch.setattr(app, "_transport", "stdio")
    return _set


async def _info(**kwargs) -> tuple[dict, str]:
    text = await server.netlicensing_server_info(**kwargs)
    return json.loads(text), text


def _check(out: dict, name: str) -> dict:
    matches = [c for c in out["checks"] if c["name"] == name]
    assert len(matches) == 1, out["checks"]
    assert set(matches[0]) == {"name", "ok", "detail"}
    return matches[0]


# ── Shape ────────────────────────────────────────────────────────────────────


async def test_keeps_existing_fields_and_adds_the_new_ones(key_default, fake_http):
    from importlib.metadata import version

    key_default(ENV_KEY)
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    out, _ = await _info()
    assert list(out) == [
        "version",
        "base_url",
        "demo_mode",
        "status",
        "transport",
        "auth",
        "checks",
        "warnings",
        "next_steps",
        "toolsets",
        "read_only",
        "tool_count",
    ]
    assert out["version"] == version("netlicensing-mcp")
    assert out["base_url"] == "go.netlicensing.io"
    assert out["demo_mode"] is False
    settings = app.active_tool_settings()
    assert out["toolsets"] == settings["toolsets"]
    assert out["read_only"] is settings["read_only"]
    assert out["tool_count"] == settings["tool_count"] == 61


async def test_reports_a_restricted_tool_list(key_default, fake_http, monkeypatch):
    key_default(ENV_KEY)
    restricted = ToolFilter.from_env({"MCP_TOOLSETS": "licenses", "MCP_READ_ONLY": "true"})
    monkeypatch.setattr(app, "_active_filter", restricted)
    out, _ = await _info(check_connection=False)
    assert out["read_only"] is True
    assert out["toolsets"] == ["licenses"]
    assert out["tool_count"] == app.tool_settings(restricted)["tool_count"] == 4


def test_instructions_point_at_server_info():
    flat = " ".join(app.INSTRUCTIONS.split())  # line breaks and indentation do not matter
    assert "run `netlicensing_server_info` first" in flat
    assert "on every new connection" not in flat


# ── Valid key ────────────────────────────────────────────────────────────────


async def test_valid_env_key(key_default, fake_http):
    key_default(ENV_KEY)
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    out, text = await _info()
    assert out["status"] == "ok"
    assert out["auth"] == {"configured": True, "source": "env", "valid": True}
    assert _check(out, "credentials")["ok"] is True
    assert _check(out, "reachable")["ok"] is True
    assert _check(out, "authentication")["ok"] is True
    assert out["warnings"] == []
    assert out["next_steps"] == []
    # exactly one cheap read: list products, one item
    fake_http.get.assert_awaited_once()
    args, kwargs = fake_http.get.call_args
    assert args[0] == f"{client.BASE_URL}/product"
    assert kwargs["params"] == {"filter": "page=0;items=1"}
    _assert_no_key(text, ENV_KEY)


async def test_header_key_is_reported_as_header(key_default, fake_http):
    var = key_default(ENV_KEY)
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    token = var.set(HEADER_KEY)
    try:
        out, text = await _info()
    finally:
        var.reset(token)
    assert out["auth"] == {"configured": True, "source": "header", "valid": True}
    assert out["status"] == "ok"
    _assert_no_key(text, ENV_KEY, HEADER_KEY)


async def test_header_key_without_env_key(key_default, fake_http):
    var = key_default("")
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    token = var.set(HEADER_KEY)
    try:
        out, text = await _info()
    finally:
        var.reset(token)
    assert out["auth"]["source"] == "header"
    _assert_no_key(text, HEADER_KEY)


# ── No key ───────────────────────────────────────────────────────────────────


async def test_no_key_stdio(key_default, fake_http):
    key_default("")
    out, _ = await _info()
    assert out["status"] == "error"
    assert out["auth"] == {"configured": False, "source": "none", "valid": None}
    assert _check(out, "credentials")["ok"] is False
    steps = " ".join(out["next_steps"])
    assert "NETLICENSING_API_KEY" in steps
    assert "NETLICENSING_ALLOW_DEMO=true" in steps
    assert [c["name"] for c in out["checks"]] == ["credentials"]
    fake_http.get.assert_not_called()


async def test_no_key_http_points_at_the_header(key_default, fake_http):
    key_default("")
    app.set_transport("http")
    out, _ = await _info()
    assert out["transport"] == "http"
    assert out["status"] == "error"
    steps = " ".join(out["next_steps"])
    assert "X-NetLicensing-API-Key" in steps
    assert "Authorization: Bearer" in steps
    fake_http.get.assert_not_called()


# ── Demo ─────────────────────────────────────────────────────────────────────


async def test_demo_mode(key_default, fake_http, monkeypatch):
    key_default("")
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    out, _ = await _info()
    assert out["status"] == "warning"
    assert out["demo_mode"] is True
    assert out["auth"] == {"configured": True, "source": "demo", "valid": True}
    assert client.DEMO_MODE_WARNING in out["warnings"]
    assert any("NETLICENSING_API_KEY" in s for s in out["next_steps"])
    fake_http.get.assert_awaited_once()


async def test_env_key_wins_over_demo_flag(key_default, fake_http, monkeypatch):
    key_default(ENV_KEY)
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    out, _ = await _info()
    assert out["auth"]["source"] == "env"
    assert out["demo_mode"] is False
    assert out["status"] == "ok"


# ── Rejected key ─────────────────────────────────────────────────────────────


async def test_rejected_key_401(key_default, fake_http):
    key_default(ENV_KEY)
    # An upstream message that (hypothetically) echoes the key must not leak.
    fake_http.get.return_value = _api_error(401, f"Unauthorized {ENV_KEY}")
    out, text = await _info()
    assert out["status"] == "error"
    assert out["auth"] == {"configured": True, "source": "env", "valid": False}
    assert _check(out, "reachable")["ok"] is True
    assert _check(out, "authentication")["ok"] is False
    hint = error_hint(client.NetLicensingError(401, ""), "netlicensing_server_info")["hint"]
    assert out["next_steps"][0] == hint
    assert "restart" in out["next_steps"][1]
    _assert_no_key(text, ENV_KEY)


async def test_forbidden_403_means_valid_key_with_a_low_role(key_default, fake_http):
    # API Conventions: 403 = authenticated, but the role may not call the operation.
    key_default(ENV_KEY)
    fake_http.get.return_value = _api_error(403, f"Forbidden {ENV_KEY}")
    out, text = await _info()
    assert out["status"] == "warning"
    assert out["auth"] == {"configured": True, "source": "env", "valid": True}
    assert _check(out, "reachable")["ok"] is True
    assert _check(out, "authentication")["ok"] is True
    assert _check(out, "permission")["ok"] is False
    assert out["warnings"]
    hint = error_hint(client.NetLicensingError(403, ""), "netlicensing_server_info")["hint"]
    assert out["next_steps"][0] == hint
    assert "restart" in out["next_steps"][1]
    _assert_no_key(text, ENV_KEY)


async def test_demo_rejected_has_no_key_restart_step(key_default, fake_http, monkeypatch):
    key_default("")
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
    fake_http.get.return_value = _api_error(401, "Unauthorized")
    out, _ = await _info()
    assert out["auth"] == {"configured": True, "source": "demo", "valid": False}
    hint = error_hint(client.NetLicensingError(401, ""), "netlicensing_server_info")["hint"]
    assert hint in out["next_steps"]
    assert not any("After changing NETLICENSING_API_KEY" in s for s in out["next_steps"])


async def test_rejected_header_key_points_at_the_header(key_default, fake_http):
    var = key_default("")
    fake_http.get.return_value = _api_error(401, f"Unauthorized {HEADER_KEY}")
    token = var.set(HEADER_KEY)
    try:
        out, text = await _info()
    finally:
        var.reset(token)
    assert out["auth"] == {"configured": True, "source": "header", "valid": False}
    assert "header" in out["next_steps"][1]
    _assert_no_key(text, HEADER_KEY)


# ── API not reachable ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError(f"refused https://go.netlicensing.io/?k={ENV_KEY}"),
        httpx.ReadTimeout(f"slow {ENV_KEY}"),
    ],
)
async def test_transport_error_means_unreachable(key_default, fake_http, exc):
    key_default(ENV_KEY)
    fake_http.get.side_effect = exc
    out, text = await _info()
    assert out["status"] == "error"
    assert out["auth"] == {"configured": True, "source": "env", "valid": None}
    assert _check(out, "reachable")["ok"] is False
    assert [c["name"] for c in out["checks"]] == ["credentials", "reachable"]
    assert out["next_steps"]
    _assert_no_key(text, ENV_KEY)


async def test_slow_api_hits_the_short_timeout(key_default, fake_http, monkeypatch):
    key_default(ENV_KEY)
    monkeypatch.setattr(utilities, "_CHECK_TIMEOUT_SECONDS", 0.05)

    async def never_answers(*args, **kwargs):
        await asyncio.sleep(5)

    fake_http.get.side_effect = never_answers
    out, _ = await asyncio.wait_for(_info(), timeout=2)
    assert out["auth"]["valid"] is None
    reachable = _check(out, "reachable")
    assert reachable["ok"] is False
    assert "0.05" in reachable["detail"]
    assert out["status"] == "error"


def test_check_timeout_is_shorter_than_the_client_timeout():
    assert utilities._CHECK_TIMEOUT_SECONDS < 30.0


# ── Other failures ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", [429, 500])
async def test_other_upstream_error_leaves_valid_unknown(key_default, fake_http, status):
    key_default(ENV_KEY)
    fake_http.get.return_value = _api_error(status, f"busy {ENV_KEY}")
    out, text = await _info()
    assert out["status"] == "warning"
    assert out["auth"]["valid"] is None
    assert _check(out, "reachable")["ok"] is True
    assert _check(out, "api_read")["ok"] is False
    assert out["warnings"]
    _assert_no_key(text, ENV_KEY)


async def test_non_json_reply_is_reachable_but_unverified(key_default, fake_http):
    key_default(ENV_KEY)
    fake_http.get.return_value = httpx.Response(200, content=b"<html>proxy</html>")
    out, _ = await _info()
    assert out["auth"]["valid"] is None
    assert _check(out, "reachable")["ok"] is True
    assert _check(out, "api_read")["ok"] is False
    assert out["status"] == "warning"


async def test_unexpected_exception_never_raises(key_default, fake_http, caplog):
    key_default(ENV_KEY)
    fake_http.get.side_effect = RuntimeError(f"boom {ENV_KEY}")
    with caplog.at_level(logging.DEBUG):
        out, text = await _info()
    assert out["auth"]["valid"] is None
    assert out["status"] == "warning"
    assert _check(out, "api_read")["ok"] is False
    assert "boom" not in text
    _assert_no_key(text, ENV_KEY)
    _assert_no_key(caplog.text, ENV_KEY)


# ── check_connection=False ───────────────────────────────────────────────────


async def test_check_connection_false_makes_no_http_call(key_default, fake_http):
    key_default(ENV_KEY)
    with patch.object(utilities.products, "list_products") as list_products:
        out, text = await _info(check_connection=False)
    fake_http.get.assert_not_called()
    list_products.assert_not_called()
    assert out["status"] == "ok"
    assert out["auth"] == {"configured": True, "source": "env", "valid": None}
    assert [c["name"] for c in out["checks"]] == ["credentials"]
    assert any("check_connection=true" in s for s in out["next_steps"])
    _assert_no_key(text, ENV_KEY)


async def test_check_connection_false_in_demo_mode(key_default, fake_http, monkeypatch):
    key_default("")
    monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
    out, _ = await _info(check_connection=False)
    fake_http.get.assert_not_called()
    assert out["status"] == "warning"
    assert out["auth"] == {"configured": True, "source": "demo", "valid": None}


# ── Logs ─────────────────────────────────────────────────────────────────────


async def test_no_key_in_debug_logs(key_default, fake_http, caplog):
    key_default(ENV_KEY)
    fake_http.get.return_value = _api_error(401, "Unauthorized")
    with caplog.at_level(logging.DEBUG):
        await _info()
    _assert_no_key(caplog.text, ENV_KEY)


# ── Transport ────────────────────────────────────────────────────────────────


def test_set_transport(monkeypatch):
    monkeypatch.setattr(app, "_transport", "stdio")
    app.set_transport("http")
    assert app.active_transport() == "http"
    app.set_transport("stdio")
    assert app.active_transport() == "stdio"


@pytest.mark.parametrize("arg", ["stdio", "http"])
def test_main_records_the_transport(monkeypatch, arg):
    monkeypatch.setattr(app, "_transport", "stdio" if arg == "http" else "http")
    monkeypatch.setenv("NETLICENSING_API_KEY", ENV_KEY)
    monkeypatch.setattr(sys, "argv", ["netlicensing-mcp", arg])
    with (
        patch.object(server.mcp, "run", MagicMock()) as run,
        patch("anyio.run", MagicMock()) as anyio_run,
    ):
        server.main()
    assert app.active_transport() == arg
    assert (run.called, anyio_run.called) == ((True, False) if arg == "stdio" else (False, True))


# ── End to end over HTTP: the header key ─────────────────────────────────────

_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def _payload(resp: httpx.Response) -> dict:
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    return resp.json()


async def test_http_request_reports_header_source(fake_http, monkeypatch):
    monkeypatch.setattr(app, "_transport", "http")
    fake_http.get.return_value = httpx.Response(200, json=_PRODUCT_PAGE)
    # A fresh server: a FastMCP session manager can run only once per instance.
    tool_filter = ToolFilter.from_env({})
    srv = app.new_server(tool_filter)
    app.register_tools(srv, tool_filter)
    asgi = srv.streamable_http_app()
    asgi.add_middleware(server.ApiKeyMiddleware)
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "netlicensing_server_info", "arguments": {}},
    }
    async with asgi.router.lifespan_context(asgi):
        transport = httpx.ASGITransport(app=asgi)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
            r = await c.post(
                "/mcp", headers={**_HEADERS, "x-netlicensing-api-key": HEADER_KEY}, json=call
            )
    assert r.status_code == 200, r.text
    result = _payload(r)["result"]
    assert result["isError"] is False
    info = result["structuredContent"]
    assert info["transport"] == "http"
    assert info["auth"] == {"configured": True, "source": "header", "valid": True}
    _assert_no_key(r.text, HEADER_KEY)
    sent = fake_http.get.call_args.kwargs["headers"]["Authorization"]
    assert sent.startswith("Basic ")
