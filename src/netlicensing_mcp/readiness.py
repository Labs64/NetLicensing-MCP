"""
Readiness probe (``GET /ready``)
================================
``/health`` is the liveness probe: the process answers HTTP. ``/ready`` says
whether this instance can serve MCP traffic now:

1. **app** — the MCP session manager is running (the ASGI lifespan started);
   before that, ``/mcp`` requests fail.
2. **upstream** — the NetLicensing API (``NETLICENSING_BASE_URL``) answers.
   One unauthenticated ``GET`` of the base URL through the shared HTTP client,
   3 s timeout. *Any* HTTP response (also 401 / 404 / 5xx) counts as
   reachable; timeouts, connection / transport errors and a malformed URL do not. The
   result is cached (success 15 s, failure 5 s) so probes cannot hammer the
   upstream, and concurrent checks share one probe.

An API key is *not* a readiness criterion: in HTTP mode every request brings
its own key. The probe sends no credentials, never reads the upstream body and
reports only the base URL's host name.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from netlicensing_mcp import client as _client

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 3.0
SUCCESS_TTL_SECONDS = 15.0
# Shorter, so a recovered upstream is noticed quickly; still at most one
# upstream request per 5 s per instance while it is down.
FAILURE_TTL_SECONDS = 5.0

SERVER_NAME = "netlicensing-mcp"


@dataclass(frozen=True)
class UpstreamStatus:
    """Outcome of one upstream probe. ``error`` is a fixed code, never upstream text."""

    ok: bool
    # "timeout" | "connect_error" | "transport_error" | "invalid_url" | "probe_error"
    error: str | None
    checked_at: float


def upstream_host() -> str:
    """Host name of ``NETLICENSING_BASE_URL`` (no scheme, credentials or path)."""
    try:
        return urlsplit(_client.BASE_URL).hostname or "unknown"
    except ValueError:
        return "unknown"


class UpstreamProbe:
    """Cached, single-flight reachability check of the NetLicensing API."""

    def __init__(
        self,
        *,
        timeout: float = PROBE_TIMEOUT_SECONDS,
        success_ttl: float = SUCCESS_TTL_SECONDS,
        failure_ttl: float = FAILURE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.timeout = timeout
        self.success_ttl = success_ttl
        self.failure_ttl = failure_ttl
        self.clock = clock
        self._last: UpstreamStatus | None = None
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        """The lock for the running event loop (an ``asyncio.Lock`` binds to one loop)."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def _fresh(self) -> UpstreamStatus | None:
        last = self._last
        if last is None:
            return None
        ttl = self.success_ttl if last.ok else self.failure_ttl
        return last if self.clock() - last.checked_at < ttl else None

    async def check(self) -> tuple[UpstreamStatus, bool]:
        """Return ``(status, cached)``; probes the upstream only when the cache expired."""
        cached = self._fresh()
        if cached is not None:
            return cached, True
        async with self._get_lock():
            # Another task may have probed while this one waited for the lock.
            cached = self._fresh()
            if cached is not None:
                return cached, True
            error = await self._probe()
            self._last = UpstreamStatus(ok=error is None, error=error, checked_at=self.clock())
            if error is not None:
                logger.warning(
                    "Readiness: NetLicensing API at %s is unreachable (%s)", upstream_host(), error
                )
            return self._last, False

    async def _probe(self) -> str | None:
        """GET the base URL without credentials; return an error code or ``None``."""
        try:
            # httpx turns URL userinfo into Basic auth; the probe sends no credentials.
            url = httpx.URL(_client.BASE_URL).copy_with(userinfo=b"")
            async with asyncio.timeout(self.timeout):
                # Streamed, so the body is never read; only the status line matters.
                async with _client._get_client().stream("GET", url, timeout=self.timeout):
                    return None
        except (TimeoutError, httpx.TimeoutException):
            return "timeout"
        except httpx.ConnectError:
            return "connect_error"
        except httpx.HTTPError:
            return "transport_error"
        except httpx.InvalidURL:  # malformed NETLICENSING_BASE_URL
            return "invalid_url"


# Replaced in tests; looked up on every request.
upstream_probe = UpstreamProbe()


_MISSING = object()


def session_manager_running(server: FastMCP) -> bool:
    """True while the server's streamable-HTTP session manager runs (lifespan started).

    Reads private SDK attributes. If a future SDK no longer has them, assume it
    runs (fail open) rather than report "not ready" forever.
    """
    manager = getattr(server, "_session_manager", _MISSING)
    if manager is None:  # streamable_http_app() not built yet
        return False
    task_group = _MISSING if manager is _MISSING else getattr(manager, "_task_group", _MISSING)
    if task_group is _MISSING:
        logger.debug("Readiness: cannot inspect the MCP session manager; assuming it runs")
        return True
    return task_group is not None


def register_ready_route(server: FastMCP, version: Callable[[], str]) -> None:
    """Add ``GET /ready`` to *server*; *version* returns the package version (read once)."""
    version_str = version()

    @server.custom_route("/ready", methods=["GET"])
    async def ready_check(request: Request) -> JSONResponse:
        """Readiness probe — 200 when this instance can serve traffic, else 503."""
        app_ok = session_manager_running(server)
        try:
            upstream, cached = await upstream_probe.check()
        except Exception as exc:  # a bug must give 503, not 500; CancelledError passes
            logger.warning("Readiness: upstream check failed (%s)", type(exc).__name__)
            upstream, cached = UpstreamStatus(ok=False, error="probe_error", checked_at=0.0), False
        host = upstream_host()

        upstream_check: dict[str, object] = {"ok": upstream.ok, "host": host, "cached": cached}
        if upstream.error is not None:
            upstream_check["error"] = upstream.error

        reasons = []
        if not app_ok:
            reasons.append("MCP session manager is not running")
        if not upstream.ok:
            reasons.append(f"NetLicensing API at {host} is unreachable ({upstream.error})")

        body: dict[str, object] = {
            "status": "not_ready" if reasons else "ready",
            "server": SERVER_NAME,
            "version": version_str,
        }
        if reasons:
            body["reason"] = "; ".join(reasons)
        body["checks"] = {"app": {"ok": app_ok}, "upstream": upstream_check}
        return JSONResponse(
            body,
            status_code=503 if reasons else 200,
            headers={"Cache-Control": "no-store"},
        )
