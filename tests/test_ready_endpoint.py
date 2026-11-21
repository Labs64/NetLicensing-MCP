"""``/health`` (liveness) and ``/ready`` (readiness) over the real HTTP app.

The app is built with :func:`netlicensing_mcp.server.build_http_app` (the same
app ``main()`` serves: FastMCP streamable-HTTP app + ``ApiKeyMiddleware``) and
driven with Starlette's ``TestClient``. The upstream NetLicensing API is a
``httpx.MockTransport`` swapped in as the shared client.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator

import httpx
import pytest
from starlette.testclient import TestClient

import netlicensing_mcp.server as server
from netlicensing_mcp import client, readiness

# A key-like string the upstream mock puts in its body; it must never reach
# the /ready output.
_UPSTREAM_SECRET = "apiKey=UPSTREAM-SECRET-0123456789"
_SERVER_SECRET = "SERVER-SIDE-SECRET-KEY"

Handler = Callable[[httpx.Request], httpx.Response]


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Upstream:
    """Records the requests the readiness probe sends upstream."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.handler: Handler = self.respond(200)

    @staticmethod
    def respond(status: int) -> Handler:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, text=f'{{"error": "{_UPSTREAM_SECRET}"}}')

        return handler

    @staticmethod
    def fail(exc: type[httpx.HTTPError]) -> Handler:
        def handler(request: httpx.Request) -> httpx.Response:
            raise exc("boom " + _UPSTREAM_SECRET, request=request)

        return handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def upstream(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> Iterator[Upstream]:
    up = Upstream()
    monkeypatch.setattr(client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(up)))
    # Credentials in the base URL must not leak into /ready either.
    monkeypatch.setattr(client, "BASE_URL", "https://user:URLPASSWORD@upstream.test/core/v2/rest")
    monkeypatch.setattr(readiness, "upstream_probe", readiness.UpstreamProbe(clock=clock))
    monkeypatch.setenv("NETLICENSING_API_KEY", _SERVER_SECRET)
    yield up


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    # The SDK's session manager can run only once; give each test a fresh one.
    monkeypatch.setattr(server.mcp, "_session_manager", None)
    return server.build_http_app()


@pytest.fixture()
def http(app, upstream: Upstream) -> Iterator[TestClient]:
    """TestClient with the app's lifespan running (session manager started)."""
    with TestClient(app) as c:
        yield c


def _assert_no_secrets(text: str) -> None:
    for secret in (_UPSTREAM_SECRET, "UPSTREAM-SECRET", _SERVER_SECRET, "URLPASSWORD", "user:"):
        assert secret not in text


# ── /health (liveness) ───────────────────────────────────────────────────────


def test_health_is_unauthenticated_and_unchanged(http: TestClient, upstream: Upstream):
    r = http.get("/health")
    assert r.status_code == 200
    assert r.content == b'{"status":"ok","server":"netlicensing-mcp"}'
    assert upstream.requests == []  # liveness never calls NetLicensing


# ── /ready (readiness) ───────────────────────────────────────────────────────


@pytest.mark.parametrize("status", [200, 401, 404, 500])
def test_ready_when_upstream_answers_with_any_status(
    http: TestClient, upstream: Upstream, status: int
):
    upstream.handler = Upstream.respond(status)
    r = http.get("/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "status": "ready",
        "server": "netlicensing-mcp",
        "version": server._server_version(),
        "checks": {
            "app": {"ok": True},
            "upstream": {"ok": True, "host": "upstream.test", "cached": False},
        },
    }
    assert r.headers["cache-control"] == "no-store"
    _assert_no_secrets(r.text)


def test_ready_probe_is_one_unauthenticated_get_to_base_url(http: TestClient, upstream: Upstream):
    http.get("/ready", headers={"Authorization": "Bearer CLIENT-KEY"})
    assert len(upstream.requests) == 1
    req = upstream.requests[0]
    assert req.method == "GET"
    assert req.url.host == "upstream.test"
    assert req.url.path == "/core/v2/rest"
    assert "authorization" not in req.headers
    assert "CLIENT-KEY" not in str(req.headers)
    assert _SERVER_SECRET not in str(req.headers)


def test_ready_needs_no_api_key(http: TestClient):
    r = http.get("/ready", headers={})
    assert r.status_code == 200
    assert "www-authenticate" not in r.headers


def test_mcp_still_requires_a_key(http: TestClient):
    r = http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (httpx.ConnectError, "connect_error"),
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.RemoteProtocolError, "transport_error"),
    ],
)
def test_not_ready_when_upstream_unreachable(
    http: TestClient, upstream: Upstream, exc: type[httpx.HTTPError], error: str
):
    upstream.handler = Upstream.fail(exc)
    r = http.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["server"] == "netlicensing-mcp"
    assert body["version"] == server._server_version()
    assert body["reason"] == f"NetLicensing API at upstream.test is unreachable ({error})"
    assert body["checks"] == {
        "app": {"ok": True},
        "upstream": {"ok": False, "host": "upstream.test", "cached": False, "error": error},
    }
    _assert_no_secrets(r.text)
    assert "boom" not in r.text


def test_not_ready_when_base_url_is_malformed(
    http: TestClient, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(client, "BASE_URL", "https://[::1/core")
    r = http.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["upstream"] == {
        "ok": False,
        "host": "unknown",
        "cached": False,
        "error": "invalid_url",
    }
    assert upstream.requests == []


def test_not_ready_when_upstream_is_slower_than_the_timeout(
    app, upstream: Upstream, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
):
    async def slow(request: httpx.Request) -> httpx.Response:
        upstream.requests.append(request)
        await asyncio.sleep(1)
        return httpx.Response(200)

    monkeypatch.setattr(client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(slow)))
    monkeypatch.setattr(
        readiness, "upstream_probe", readiness.UpstreamProbe(clock=clock, timeout=0.05)
    )
    with TestClient(app) as http:
        r = http.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["upstream"]["error"] == "timeout"


def test_not_ready_before_the_app_has_started(app, upstream: Upstream):
    # No ``with``: the lifespan (MCP session manager) never starts.
    r = TestClient(app).get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "MCP session manager is not running"
    assert body["checks"]["app"] == {"ok": False}
    assert body["checks"]["upstream"]["ok"] is True


# ── caching ──────────────────────────────────────────────────────────────────


def test_success_is_cached_for_the_ttl(http: TestClient, upstream: Upstream, clock: FakeClock):
    assert http.get("/ready").json()["checks"]["upstream"]["cached"] is False
    clock.now += readiness.SUCCESS_TTL_SECONDS - 0.1
    r = http.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["upstream"]["cached"] is True
    assert len(upstream.requests) == 1

    clock.now += 0.2  # past the TTL: probe again
    assert http.get("/ready").json()["checks"]["upstream"]["cached"] is False
    assert len(upstream.requests) == 2


def test_failure_is_cached_for_the_shorter_failure_ttl(
    http: TestClient, upstream: Upstream, clock: FakeClock
):
    assert readiness.FAILURE_TTL_SECONDS < readiness.SUCCESS_TTL_SECONDS
    upstream.handler = Upstream.fail(httpx.ConnectError)
    assert http.get("/ready").status_code == 503
    clock.now += readiness.FAILURE_TTL_SECONDS - 0.1
    r = http.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["upstream"]["cached"] is True
    assert len(upstream.requests) == 1

    # Upstream recovers; once the failure TTL is over /ready turns 200.
    upstream.handler = Upstream.respond(401)
    clock.now += 0.2
    assert http.get("/ready").status_code == 200
    assert len(upstream.requests) == 2


async def test_concurrent_checks_share_one_probe(
    upstream: Upstream, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
):
    async def slow(request: httpx.Request) -> httpx.Response:
        upstream.requests.append(request)
        await asyncio.sleep(0.05)
        return httpx.Response(200)

    monkeypatch.setattr(client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(slow)))
    probe = readiness.UpstreamProbe(clock=clock)
    results = await asyncio.gather(*(probe.check() for _ in range(5)))
    assert len(upstream.requests) == 1
    assert all(r.ok for r, _ in results)
    assert sorted(cached for _, cached in results) == [False, True, True, True, True]


# ── robustness (review fix round 1) ──────────────────────────────────────────


def test_app_check_fails_open_when_sdk_internals_are_unknown(
    http: TestClient, monkeypatch: pytest.MonkeyPatch
):
    # A future SDK without ``_task_group``: do not report "not ready" forever.
    monkeypatch.setattr(server.mcp, "_session_manager", object())
    r = http.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["app"] == {"ok": True}


def test_session_manager_running_states():
    class Manager:
        def __init__(self, task_group: object) -> None:
            self._task_group = task_group

    class Server:
        def __init__(self, manager: object) -> None:
            self._session_manager = manager

    check = readiness.session_manager_running
    assert check(Server(None)) is False  # type: ignore[arg-type]  # app not built
    assert check(Server(Manager(None))) is False  # type: ignore[arg-type]  # not started
    assert check(Server(Manager(object()))) is True  # type: ignore[arg-type]  # running
    assert check(Server(object())) is True  # type: ignore[arg-type]  # unknown internals
    assert check(object()) is True  # type: ignore[arg-type]  # unknown internals


def test_probe_lock_works_across_event_loops(upstream: Upstream, monkeypatch, clock: FakeClock):
    async def slow(request: httpx.Request) -> httpx.Response:
        upstream.requests.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200)

    monkeypatch.setattr(client, "_client", httpx.AsyncClient(transport=httpx.MockTransport(slow)))
    probe = readiness.UpstreamProbe(clock=clock)

    async def contended() -> None:
        await asyncio.gather(*(probe.check() for _ in range(3)))

    asyncio.run(contended())
    clock.now += readiness.SUCCESS_TTL_SECONDS + 1
    asyncio.run(contended())  # used to raise "bound to a different event loop"
    assert len(upstream.requests) == 2


def test_unexpected_probe_error_is_a_503_not_a_500(
    http: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def broken() -> str | None:
        raise RuntimeError("unexpected " + _UPSTREAM_SECRET)

    monkeypatch.setattr(readiness.upstream_probe, "_probe", broken)
    with caplog.at_level("WARNING", logger="netlicensing_mcp.readiness"):
        r = http.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["reason"] == "NetLicensing API at upstream.test is unreachable (probe_error)"
    assert body["checks"]["upstream"]["error"] == "probe_error"
    assert r.headers["cache-control"] == "no-store"
    _assert_no_secrets(r.text)
    assert "RuntimeError" in caplog.text
    _assert_no_secrets(caplog.text)


def test_unreachable_warning_log_has_no_url_credentials(
    http: TestClient, upstream: Upstream, caplog: pytest.LogCaptureFixture
):
    upstream.handler = Upstream.fail(httpx.ConnectError)
    with caplog.at_level("WARNING", logger="netlicensing_mcp.readiness"):
        assert http.get("/ready").status_code == 503
    assert "NetLicensing API at upstream.test is unreachable (connect_error)" in caplog.text
    _assert_no_secrets(caplog.text)


def test_both_reasons_are_joined_and_503_is_not_cacheable(app, upstream: Upstream):
    upstream.handler = Upstream.fail(httpx.ConnectError)
    r = TestClient(app).get("/ready")  # no lifespan: app check fails too
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"
    assert r.json()["reason"] == (
        "MCP session manager is not running; "
        "NetLicensing API at upstream.test is unreachable (connect_error)"
    )


def test_version_is_read_once_at_registration(monkeypatch: pytest.MonkeyPatch):
    from mcp.server.fastmcp import FastMCP

    calls: list[int] = []

    def version() -> str:
        calls.append(1)
        return "9.9.9"

    srv = FastMCP("t")
    readiness.register_ready_route(srv, version=version)
    assert calls == [1]
    monkeypatch.setattr(readiness, "upstream_probe", readiness.UpstreamProbe())
    monkeypatch.setattr(readiness.upstream_probe, "_probe", _ok_probe)
    with TestClient(srv.streamable_http_app()) as c:
        assert c.get("/ready").json()["version"] == "9.9.9"
        assert c.get("/ready").json()["version"] == "9.9.9"
    assert calls == [1]


async def _ok_probe() -> str | None:
    return None
