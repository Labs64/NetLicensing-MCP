"""No log record carries a token number in full (Task 8b, fix round 1).

httpx logs every request URL at INFO (``HTTP Request: DELETE https://…/token/<number>``)
and httpcore logs request details at DEBUG. For APIKEY and SHOP tokens the number
in the path is the credential, so both loggers are held at WARNING in every mode,
including verbose. The project's own debug lines (``client._log_path``) mask
the token path and stay the way to see requests in verbose mode.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from netlicensing_mcp import app, client, safety
from netlicensing_mcp.server import (
    netlicensing_delete_token,
    netlicensing_get_token,
    netlicensing_preview_delete_token,
)

KEY = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

TOKEN = {
    "items": {
        "item": [
            {
                "type": "Token",
                "property": [
                    {"name": "number", "value": KEY},
                    {"name": "tokenType", "value": "APIKEY"},
                    {"name": "role", "value": "ROLE_APIKEY_ADMIN"},
                ],
            }
        ]
    }
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
    safety._store.clear()
    yield
    safety._store.clear()


@pytest.fixture
def wire():
    """Real httpx requests against a MockTransport (so httpx/httpcore would log)."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=TOKEN)

    old = client._client
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    key = client.api_key_ctx.set("test-key")
    yield requests
    client.api_key_ctx.reset(key)
    client._client = old


@pytest.fixture
def root_level():
    """Restore the root logger level after a test that turns on verbose mode."""
    root = logging.getLogger()
    old = root.level
    yield
    root.setLevel(old)


async def _exercise(requests: list[httpx.Request]) -> None:
    await netlicensing_get_token(KEY)
    await netlicensing_preview_delete_token(KEY)
    preview = await netlicensing_delete_token(KEY)  # no token: a preview
    assert KEY not in preview
    token, _ = safety.issue_token("delete_token", KEY)
    message = await netlicensing_delete_token(KEY, confirm_token=token)
    assert "deleted" in message
    # The calls really went over httpx, with the real number in the path.
    assert [r.method for r in requests] == ["GET", "GET", "GET", "DELETE"]
    assert all(r.url.path.endswith(f"/token/{KEY}") for r in requests)


def _leaks(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        f"{r.name}: {r.getMessage()}"
        for r in caplog.records
        if KEY in r.getMessage() or KEY in str(r.args)
    ]


async def test_default_mode_logs_no_token_number(wire, caplog, root_level):
    logging.getLogger().setLevel(logging.INFO)  # the app's default (basicConfig)
    caplog.set_level(logging.DEBUG, logger="netlicensing_mcp")
    await _exercise(wire)
    assert _leaks(caplog) == []
    assert not [r for r in caplog.records if r.name.startswith(("httpx", "httpcore"))]


async def test_verbose_mode_logs_no_token_number_but_keeps_masked_debug_lines(
    wire, caplog, root_level
):
    app.enable_verbose_logging()  # what server.main() does for -v / MCP_VERBOSE
    assert logging.getLogger().level == logging.DEBUG
    await _exercise(wire)

    assert _leaks(caplog) == []
    assert not [r for r in caplog.records if r.name.startswith(("httpx", "httpcore"))]
    own = [r.getMessage() for r in caplog.records if r.name == "netlicensing_mcp.client"]
    assert any(m.startswith("GET ") and m.endswith("/token/**** params_present=False") for m in own)
    assert any(
        m.startswith("DELETE ") and m.endswith("/token/**** params_present=False") for m in own
    )


def test_leaky_loggers_are_held_at_warning_even_in_verbose_mode(root_level):
    # sse_starlette logs every SSE response chunk at DEBUG ("chunk: %s"), which
    # includes the key a create-token tool shows once.
    names = ("httpx", "httpcore", "sse_starlette")
    for name in names:
        assert logging.getLogger(name).level == logging.WARNING
    app.enable_verbose_logging()
    for name in names:
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING
        assert not logging.getLogger(name).isEnabledFor(logging.INFO)
