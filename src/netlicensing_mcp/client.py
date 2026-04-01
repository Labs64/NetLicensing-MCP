"""
NetLicensing REST API async client.

Uses a shared ``httpx.AsyncClient`` for connection reuse.
All public helpers raise ``NetLicensingError`` on non-2xx responses,
wrapping the upstream JSON error body when available.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

import contextvars

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL: str = os.getenv(
    "NETLICENSING_BASE_URL",
    "https://go.netlicensing.io/core/v2/rest",
)
api_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "api_key", default=os.getenv("NETLICENSING_API_KEY", "")
)

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
    api_key = api_key_ctx.get()
    if api_key:
        auth_str = f"apiKey:{api_key}"
    else:
        logger.warning("NETLICENSING_API_KEY not set — falling back to demo credentials")
        auth_str = "demo:demo"
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
        _client = httpx.AsyncClient(timeout=30)
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
    logger.debug(f"GET {url} params={params}")
    r = await client.get(url, headers=_headers(), params=params or {})
    logger.debug(f"Response {r.status_code}: {r.text}")
    _raise_on_error(r)
    return r.json()


async def nl_post(path: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug(f"POST {url} data={data}")
    r = await client.post(
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data or {},
    )
    logger.debug(f"Response {r.status_code}: {r.text}")
    _raise_on_error(r)
    return r.json()


async def nl_put(path: str, data: dict[str, str]) -> dict[str, Any]:
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug(f"PUT {url} data={data}")
    r = await client.put(
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data,
    )
    logger.debug(f"Response {r.status_code}: {r.text}")
    _raise_on_error(r)
    return r.json()


async def nl_delete(path: str, params: dict[str, str] | None = None) -> int:
    """Delete a resource. Returns HTTP status code (200 or 204)."""
    client = _get_client()
    url = f"{BASE_URL}{path}"
    logger.debug(f"DELETE {url} params={params}")
    r = await client.delete(url, headers=_headers(), params=params or {})
    logger.debug(f"Response {r.status_code}: {r.text}")
    _raise_on_error(r)
    return r.status_code
