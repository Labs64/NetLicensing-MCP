"""
Regression test for GHSA-x9vc-9ffq-p3gj.

Verifies that the HTTP transport rejects requests that carry no API key,
and accepts requests that carry a valid one, without ever falling back to
the server-side NETLICENSING_API_KEY environment variable.
"""

import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse

from netlicensing_mcp.server import ApiKeyMiddleware, api_key_ctx


def _make_app() -> Starlette:
    """Minimal Starlette app wrapped with ApiKeyMiddleware."""

    async def echo_key(request):
        return PlainTextResponse(api_key_ctx.get() or "<none>")

    async def health(request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/mcp", echo_key),
            Route("/health", health),
        ]
    )
    app.add_middleware(ApiKeyMiddleware)
    return app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("NETLICENSING_API_KEY", "SERVER_SECRET")
    return TestClient(_make_app(), raise_server_exceptions=True)


class TestUnauthenticated:
    """Requests with no key must be rejected — never use the server-side key."""

    def test_no_key_returns_401(self, client):
        r = client.get("/mcp", headers={})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_401_includes_www_authenticate_header(self, client):
        r = client.get("/mcp", headers={})
        assert "WWW-Authenticate" in r.headers

    def test_server_key_not_leaked(self, client):
        r = client.get("/mcp", headers={})
        assert "SERVER_SECRET" not in r.text

    def test_empty_header_returns_401(self, client):
        r = client.get("/mcp", headers={"x-netlicensing-api-key": ""})
        assert r.status_code == 401

    def test_whitespace_only_header_returns_401(self, client):
        r = client.get("/mcp", headers={"x-netlicensing-api-key": "   "})
        assert r.status_code == 401


class TestAuthenticated:
    """Requests with a valid key must pass through using that key."""

    def test_header_key_accepted(self, client):
        r = client.get("/mcp", headers={"x-netlicensing-api-key": "CLIENT_KEY"})
        assert r.status_code == 200
        assert r.text == "CLIENT_KEY"

    def test_bearer_token_accepted(self, client):
        r = client.get("/mcp", headers={"Authorization": "Bearer CLIENT_KEY"})
        assert r.status_code == 200
        assert r.text == "CLIENT_KEY"

    def test_bearer_token_whitespace_stripped(self, client):
        r = client.get("/mcp", headers={"Authorization": "Bearer  CLIENT_KEY  "})
        assert r.status_code == 200
        assert r.text == "CLIENT_KEY"

    def test_client_key_not_replaced_by_server_key(self, client):
        r = client.get("/mcp", headers={"x-netlicensing-api-key": "CLIENT_KEY"})
        assert r.text != "SERVER_SECRET"


class TestHealthEndpoint:
    """Health check must work without any API key."""

    def test_health_unauthenticated(self, client):
        r = client.get("/health")
        assert r.status_code == 200
