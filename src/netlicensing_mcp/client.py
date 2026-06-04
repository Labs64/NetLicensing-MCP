"""
NetLicensing REST API async client.

Uses a shared ``httpx.AsyncClient`` for connection reuse.
All public helpers raise ``NetLicensingError`` on non-2xx responses,
wrapping the upstream JSON error body when available.
"""

from __future__ import annotations

import base64
import contextvars
import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL: str = os.getenv(
    "NETLICENSING_BASE_URL",
    "https://go.netlicensing.io/core/v2/rest",
)
api_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "api_key", default=os.getenv("NETLICENSING_API_KEY", "")
)

# ── Demo-mode helpers ─────────────────────────────────────────────────────────

_last_demo_warning_time: float = 0.0


def _allow_demo() -> bool:
    """Return True when ``NETLICENSING_ALLOW_DEMO`` is explicitly opted-in."""
    return os.getenv("NETLICENSING_ALLOW_DEMO", "").lower() in ("true", "1", "yes")


def is_demo_mode() -> bool:
    """Return True when the current request will use demo sandbox credentials.

    Demo mode is active only when no API key is present in the context AND
    ``NETLICENSING_ALLOW_DEMO=true`` has been explicitly set.
    """
    return not api_key_ctx.get() and _allow_demo()

# ── Error wrapper ────────────────────────────────────────────────────────────


class NetLicensingError(Exception):
    """Raised when the NetLicensing API returns a non-2xx status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def _raise_on_error(response: httpx.Response) -> None:
    """Raise *NetLicensingError* with the API error body if available."""
    if response.is_success:
        return
    try:
        body = response.json()
        infos = body.get("infos", {}).get("info", [])
        detail = "; ".join(i.get("value", "") for i in infos) or response.text
    except Exception:
        detail = response.text
    raise NetLicensingError(response.status_code, detail)


# ── Auth header ──────────────────────────────────────────────────────────────


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    global _last_demo_warning_time  # noqa: PLW0603
    api_key = api_key_ctx.get()
    if api_key:
        auth_str = f"apiKey:{api_key}"
    elif _allow_demo():
        # Demo mode is explicitly opted-in — emit a loud, throttled warning.
        now = time.monotonic()
        if now - _last_demo_warning_time >= 60:
            logger.warning(
                "⚠️  DEMO MODE ACTIVE — using sandbox demo:demo credentials. "
                "All API calls go to the NetLicensing sandbox. "
                "Set NETLICENSING_API_KEY for production use. "
                "Remove NETLICENSING_ALLOW_DEMO=true to disable this mode."
            )
            _last_demo_warning_time = now
        auth_str = "demo:demo"
    else:
        raise NetLicensingError(
            503,
            "No NetLicensing API key configured. "
            "Set NETLICENSING_API_KEY or supply X-NetLicensing-API-Key. "
            "For sandbox/demo access, set NETLICENSING_ALLOW_DEMO=true.",
        )
    token = base64.b64encode(auth_str.encode()).decode()
    h: dict[str, str] = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


# ── Shared HTTP client ──────────────────────────────────────────────────────

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return (and lazily create) the module-level ``AsyncClient``."""
    global _client  # noqa: PLW0603
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_client() -> None:
    """Shut down the shared HTTP client (call on server shutdown)."""
    global _client  # noqa: PLW0603
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── Public helpers ───────────────────────────────────────────────────────────


async def nl_get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug("GET %s params=%s", url, params)
    r = await client.get(url, headers=_headers(), params=params or {})
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return r.json()


async def nl_post(path: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug("POST %s", url)
    r = await client.post(
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data or {},
    )
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return r.json()


async def nl_put(path: str, data: dict[str, str]) -> dict[str, Any]:
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug("PUT %s", url)
    r = await client.put(
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data,
    )
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return r.json()


async def nl_delete(path: str, params: dict[str, str] | None = None) -> int:
    """Delete a resource. Returns HTTP status code (200 or 204)."""
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug("DELETE %s params=%s", url, params)
    r = await client.delete(url, headers=_headers(), params=params or {})
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return r.status_code
