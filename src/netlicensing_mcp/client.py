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
from urllib.parse import unquote

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


# ── Path validation ──────────────────────────────────────────────────────────


def _validated_path(path: str) -> str:
    """Reject path-traversal / separator injection in interpolated identifiers.

    Tool layers build REST paths like ``f"/product/{number}"`` from
    caller-controlled values. httpx applies RFC 3986 / WHATWG dot-segment
    removal, so a value of ``../token`` collapses ``/product/../token`` to
    ``/token`` — silently redirecting the request to an unintended endpoint and
    bypassing endpoint-specific redaction (e.g. token APIKEY masking).

    Validate every segment before the request is built. Each segment is
    percent-decoded *repeatedly until stable* because httpx does not decode
    ``%2f``/``%2e``, so encoded separators reach the upstream untouched — and
    any layer in front of the backend that decodes more than once would turn
    ``%252e%252e`` into ``..`` (GHSA-cwqx-x2qh-6mrx).

    Servlet-style path parameters (``;…``) are stripped before the dot-segment
    check, since Java containers resolve ``..;x`` as ``..``.
    """
    if not path.startswith("/"):
        raise NetLicensingError(400, "Internal error: upstream path must start with '/'")
    for segment in path.split("/"):
        decoded = _fully_unquote(segment)
        if "/" in decoded or "\\" in decoded:
            raise NetLicensingError(400, "Invalid identifier: path separators are not allowed")
        if decoded.split(";", 1)[0] in {".", ".."}:
            raise NetLicensingError(400, "Invalid identifier: path separators are not allowed")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded):
            raise NetLicensingError(400, "Invalid identifier: control characters are not allowed")
    return path


_MAX_DECODE_PASSES = 8


def _fully_unquote(segment: str) -> str:
    """Percent-decode *segment* until it stops changing.

    Raises ``NetLicensingError`` if the encoding is nested deeper than
    ``_MAX_DECODE_PASSES`` — no legitimate identifier needs that.
    """
    current = segment
    for _ in range(_MAX_DECODE_PASSES):
        decoded = unquote(current)
        if decoded == current:
            return decoded
        current = decoded
    raise NetLicensingError(400, "Invalid identifier: excessive percent-encoding")


def _log_path(path: str) -> str:
    """Return *path* with the identifier of ``/token/<number>`` masked.

    For APIKEY tokens the number is the API key itself, so it must not be
    written to logs.
    """
    parts = path.split("/")
    if len(parts) > 2 and parts[1] == "token":
        parts[2:] = ["****"] * (len(parts) - 2)
    return "/".join(parts)


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


async def _send(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """Send a request, converting transport failures to ``NetLicensingError``.

    The error text is fixed so it never carries the request URL.
    """
    try:
        return await getattr(_get_client(), method)(url, **kwargs)
    except httpx.TimeoutException as exc:
        raise NetLicensingError(504, "NetLicensing API request timed out") from exc
    except httpx.HTTPError as exc:
        raise NetLicensingError(502, "Could not reach the NetLicensing API") from exc


def _json_body(response: httpx.Response) -> dict[str, Any]:
    """Parse a 2xx body as a JSON object, or raise ``NetLicensingError(502)``.

    An empty body (``204 No Content``, e.g. ``POST /licensee/{n}/transfer``)
    is a success with nothing to return, so it yields ``{}``.
    """
    if response.status_code == 204 or not response.content.strip():
        return {}
    try:
        body = response.json()
    except ValueError as exc:
        raise NetLicensingError(502, "NetLicensing API returned a non-JSON response") from exc
    if not isinstance(body, dict):
        raise NetLicensingError(502, "NetLicensing API returned an unexpected response")
    return body


# ── Public helpers ───────────────────────────────────────────────────────────


async def nl_get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{_validated_path(path)}"
    logger.debug("GET %s%s params_present=%s", BASE_URL, _log_path(path), bool(params))
    r = await _send("get", url, headers=_headers(), params=params or {})
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return _json_body(r)


async def nl_post(path: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{_validated_path(path)}"
    logger.debug("POST %s%s data_present=%s", BASE_URL, _log_path(path), bool(data))
    r = await _send(
        "post",
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data or {},
    )
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return _json_body(r)


async def nl_put(path: str, data: dict[str, str]) -> dict[str, Any]:
    url = f"{BASE_URL}{_validated_path(path)}"
    logger.debug("PUT %s%s data_present=%s", BASE_URL, _log_path(path), bool(data))
    r = await _send(
        "put",
        url,
        headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
        data=data,
    )
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return _json_body(r)


async def nl_delete(path: str, params: dict[str, str] | None = None) -> int:
    """Delete a resource. Returns HTTP status code (200 or 204)."""
    url = f"{BASE_URL}{_validated_path(path)}"
    logger.debug("DELETE %s%s params_present=%s", BASE_URL, _log_path(path), bool(params))
    r = await _send("delete", url, headers=_headers(), params=params or {})
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    return r.status_code
