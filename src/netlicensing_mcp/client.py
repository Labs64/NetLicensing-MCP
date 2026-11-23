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
import re
from urllib.parse import quote, unquote, urlsplit

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


def base_url_host() -> str | None:
    """Host name of ``BASE_URL`` (no scheme, credentials or path), or ``None``.

    ``None`` when the URL has no host or cannot be parsed (``urlsplit`` raises
    ``ValueError`` for e.g. ``http://[::1/core``), so callers that must never
    raise (``netlicensing_server_info``, error hints, ``/ready``) can use it.
    """
    try:
        return urlsplit(BASE_URL).hostname or None
    except ValueError:
        return None


# ── Demo-mode helpers ─────────────────────────────────────────────────────────

_last_demo_warning_time: float = 0.0

# Logged (throttled) on demo-mode API calls; also a netlicensing_server_info warning.
DEMO_MODE_WARNING = (
    "DEMO MODE ACTIVE — using sandbox demo:demo credentials. "
    "All API calls go to the NetLicensing sandbox. "
    "Set NETLICENSING_API_KEY for production use. "
    "Remove NETLICENSING_ALLOW_DEMO=true to disable this mode."
)


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
    """Raised when the NetLicensing API returns a non-2xx status.

    ``info_ids`` holds the ``id`` of each upstream ``infos.info[]`` entry
    (e.g. ``NotFoundException``); ``retry_after`` the ``Retry-After`` header
    in seconds, when the API sent one. Both feed the error hints
    (``netlicensing_mcp.errors``).
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        info_ids: tuple[str, ...] = (),
        retry_after: int | None = None,
        non_json: bool = False,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.info_ids = info_ids
        self.retry_after = retry_after
        # True when a non-2xx reply was not a NetLicensing JSON body (a gateway or
        # proxy page); ``detail`` is then a fixed text, never the page itself.
        self.non_json = non_json
        super().__init__(f"HTTP {status_code}: {detail}")


def _retry_after_seconds(response: httpx.Response) -> int | None:
    """``Retry-After`` as whole seconds, or ``None`` (absent or an HTTP date)."""
    value = response.headers.get("Retry-After", "").strip()
    return int(value) if value.isascii() and value.isdigit() else None


_MAX_DETAIL_CHARS = 300

#: A fully qualified Java class name (``com.labs64.domain.vo.TransactionStatus``).
_JAVA_CLASS = re.compile(r"\b(?:[a-z][a-z0-9_]*\.){2,}[A-Z][\w$]*(?:\$[\w$]+)*")


def sanitize_detail(text: str) -> str:
    """Return a short, safe version of an upstream error message.

    Cuts a Java stack trace at its first newline or ``\tat `` frame, replaces fully
    qualified class names with ``<internal>`` and caps the length. The full text
    only goes to the log (``_raise_on_error``).
    """
    cut = text
    for marker in ("\n", "\r", "\tat "):
        cut = cut.split(marker, 1)[0]
    cut = _JAVA_CLASS.sub("<internal>", cut).strip()
    if len(cut) > _MAX_DETAIL_CHARS:
        cut = cut[: _MAX_DETAIL_CHARS - 1].rstrip() + "…"
    return cut


def _raise_on_error(response: httpx.Response) -> None:
    """Raise *NetLicensingError* with the API error body if available."""
    if response.is_success:
        return
    info_ids: tuple[str, ...] = ()
    non_json = False
    try:
        body = response.json()
        infos = body.get("infos", {}).get("info", [])
        # Core often repeats the same info several times.
        values = list(dict.fromkeys(i.get("value", "") for i in infos if isinstance(i, dict)))
        detail = "; ".join(v for v in values if v) or response.text
        info_ids = tuple(
            dict.fromkeys(str(i["id"]) for i in infos if isinstance(i, dict) and i.get("id"))
        )
    except Exception:
        non_json = True
        detail = (
            f"The request was answered with HTTP {response.status_code} by a gateway or proxy "
            "(not a NetLicensing JSON response); the page is not shown. If the input contains "
            "special characters, the request may have been blocked."
        )
    if response.status_code >= 500 or non_json:
        logger.warning("NetLicensing error %s: %s", response.status_code, response.text[:2000])
    safe = detail if non_json else sanitize_detail(detail)
    if response.status_code >= 500 and "<internal>" in safe:
        safe = "NetLicensing reported an internal error (details omitted)."
    raise NetLicensingError(
        response.status_code,
        safe,
        info_ids=info_ids,
        retry_after=_retry_after_seconds(response),
        non_json=non_json,
    )


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
    segments = path.split("/")[1:]
    for segment in segments:
        if not segment.strip():
            raise NetLicensingError(400, "Invalid identifier: must not be empty")
        decoded = _fully_unquote(segment)
        if "/" in decoded or "\\" in decoded:
            raise NetLicensingError(400, "Invalid identifier: path separators are not allowed")
        if decoded.split(";", 1)[0] in {".", ".."}:
            raise NetLicensingError(400, "Invalid identifier: path separators are not allowed")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded):
            raise NetLicensingError(400, "Invalid identifier: control characters are not allowed")
        if any(ch in segment for ch in "?#%") or any(ch.isspace() for ch in segment):
            raise NetLicensingError(
                400, "Invalid identifier: '?', '#', '%' and whitespace are not allowed"
            )
    # Every identifier is now a single plain segment; encode it so nothing in it
    # can be read as URL syntax (e.g. '@' → '%40').
    return "/" + "/".join(quote(segment, safe="") for segment in segments)


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
            logger.warning("⚠️  %s", DEMO_MODE_WARNING)
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


# ── Client-side filtering ────────────────────────────────────────────────────

#: Filter fields the tool descriptions advertise. Core honours them on some list
#: endpoints only (checked against the sandbox: ``active`` works on a bare product
#: or module list but is ignored next to ``productNumber`` and on license
#: templates, ``status`` is ignored on transactions), so they are re-applied here.
CLIENT_FILTER_FIELDS = frozenset({"active", "status", "tokenType"})


def _apply_client_filter(body: dict[str, Any], filter_str: str) -> dict[str, Any]:
    """Drop list items that contradict an advertised ``key=value`` filter pair.

    An item without the property is kept (nothing to compare). When items were
    dropped, the upstream totals no longer describe the result, so ``totalitems``
    and ``totalpages`` are removed (``hasnext`` stays, since further pages may hold
    more matches).
    """
    wanted: dict[str, str] = {}
    for part in filter_str.split(";"):
        key, sep, value = part.partition("=")
        if sep and key.strip() in CLIENT_FILTER_FIELDS:
            wanted[key.strip()] = value.strip().lower()
    items_obj = body.get("items")
    if not wanted or not isinstance(items_obj, dict) or not isinstance(items_obj.get("item"), list):
        return body

    def keep(item: Any) -> bool:
        if not isinstance(item, dict):
            return True
        for prop in item.get("property") or []:
            if not isinstance(prop, dict):
                continue
            expected = wanted.get(str(prop.get("name")))
            if expected is not None and str(prop.get("value")).strip().lower() != expected:
                return False
        return True

    kept = [i for i in items_obj["item"] if keep(i)]
    if len(kept) == len(items_obj["item"]):
        return body
    new_items = {k: v for k, v in items_obj.items() if k not in ("totalitems", "totalpages")}
    new_items["item"] = kept
    return {**body, "items": new_items}


# ── Public helpers ───────────────────────────────────────────────────────────


async def nl_get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{_validated_path(path)}"
    logger.debug("GET %s%s params_present=%s", BASE_URL, _log_path(path), bool(params))
    r = await _send("get", url, headers=_headers(), params=params or {})
    logger.debug("Response %s", r.status_code)
    _raise_on_error(r)
    body = _json_body(r)
    if params and params.get("filter"):
        body = _apply_client_filter(body, params["filter"])
    return body


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
