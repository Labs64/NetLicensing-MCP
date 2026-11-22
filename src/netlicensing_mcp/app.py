"""
Shared MCP application objects
==============================
The single ``FastMCP`` instance (with its LLM-facing ``instructions``), the
``/health`` route, tool annotation presets, and the response helpers
(``_json`` / ``_wrap_json*`` / ``_error`` and friends) used by every tool
module under ``netlicensing_mcp.mcp_tools``.

Tool modules register their wrappers with ``@tool(...)``, defined at the
bottom of this module, so the registration path can be changed in one place.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict

from starlette.requests import Request
from starlette.responses import JSONResponse

from netlicensing_mcp.client import NetLicensingError, is_demo_mode
from netlicensing_mcp.errors import confirmation_hint, error_hint
from netlicensing_mcp.redaction import redact, redact_token_read
from netlicensing_mcp.responses import DEFAULT_WARN_INFO_TYPES, wrap
from netlicensing_mcp.toolsets import ToolFilter, toolset_of

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

#: Third-party loggers that write credentials: httpx logs every request URL at
#: INFO (``HTTP Request: DELETE https://…/token/<number>``; for APIKEY and SHOP
#: tokens the number in the path is the credential), httpcore request details at
#: DEBUG, and sse_starlette every response chunk at DEBUG (HTTP mode), which
#: includes a new API key or shop URL shown once by the create-token tools.
_LEAKY_LOGGERS = ("httpx", "httpcore", "sse_starlette")


def quiet_http_loggers() -> None:
    """Hold the httpx/httpcore/sse_starlette loggers at WARNING, whatever the root level.

    An explicit level on these loggers is not raised by a DEBUG root logger, so
    verbose mode does not turn their logging back on. The client's own debug
    lines (``client._log_path``) mask token paths and show the requests instead.
    """
    for name in _LEAKY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def enable_verbose_logging() -> None:
    """Verbose mode (``-v`` / ``MCP_VERBOSE``): root logger at DEBUG, leaky loggers kept quiet."""
    logging.getLogger().setLevel(logging.DEBUG)
    quiet_http_loggers()


quiet_http_loggers()

INSTRUCTIONS = """
You are connected to the Labs64 NetLicensing REST API — a cloud-based
online license and entitlements management system for software vendors.

## Entity hierarchy (create in this order, delete in reverse)

  Product  →  ProductModule  →  LicenseTemplate
  Product  →  Licensee       →  License (linked to a LicenseTemplate)
  Bundle (groups LicenseTemplates for one-step obtain)
  Transaction (tracks purchases / shop checkouts)
  Token (shop URLs, API keys)
  PaymentMethod (vendor payment configuration)

- A **Product** is the top-level container (e.g. "My SaaS App v2").
  Supports `licenseeAutoCreate` and `vatMode` (GROSS/NET).
- A **ProductModule** groups features under one licensing model
  (Subscription, TryAndBuy, Floating, PayPerUse, Quota, NodeLocked, etc.).
  Model-specific settings: `maxCheckoutValidity` (Floating),
  `yellowThreshold`/`redThreshold` (Rental), `nodeSecretMode` (NodeLocked).
- A **LicenseTemplate** defines what a purchasable entitlement looks like
  (type, price, currency, auto-assign behaviour).
  License types: FEATURE, TIMEVOLUME, FLOATING, QUANTITY.
- A **Licensee** is a customer / end-user of the product.
  Supports `markedForTransfer` for license migration workflows.
- A **License** is a concrete entitlement assignment for a licensee from a template.
  Type-specific fields: `startDate`/`timeVolume`/`timeVolumePeriod` (TIMEVOLUME),
  `quantity`/`usedQuantity` (PayPerUse), `parentfeature` (Rental).
- A **Bundle** groups one or more license templates for convenient one-step
  provisioning via `obtain`. Price and currency can be set on the bundle.
- A **Transaction** records a purchase event (status: PENDING → CLOSED / CANCELLED).
- A **Token** is a shop checkout URL (SHOP type) or API key (APIKEY type).
- A **PaymentMethod** configures vendor payment processing (e.g. PayPal).

## Common workflows

1. **Set up a new product:**
   create_product → create_product_module → create_license_template.
2. **Onboard a customer:**
   create_licensee → create_license (from a template) → validate_licensee.
3. **Check compliance:**
   validate_licensee returns per-module validity, expiry, and quota (always
   as a list envelope, one item per module).
   Module-scoped parameters require `product_module_number`, and one call
   addresses ONE module:
   - Floating: `product_module_number` + `session_id` + `action` (checkOut/checkIn).
   - NodeLocked: `product_module_number` + `node_secret`.
   Pass `dry_run=true` to validate without side effects — it never checks out,
   checks in, binds a node or consumes anything.
4. **Sell via shop:**
   create_shop_token generates a one-time checkout URL for a licensee.
5. **Provision a bundle:**
   obtain_bundle creates all licenses from a bundle's templates for a licensee.
6. **Review purchases:**
   list_transactions / get_transaction to inspect checkout history.
7. **Discover available models:**
   list_licensing_models and list_license_types for reference data.
8. **Audit:** use the built-in audit prompt templates for full-account,
   single-customer, expiry-sweep, cleanup, or anomaly-detection audits.
9. **Guided setup and troubleshooting:** the prompt templates
   `setup_subscription_product`, `setup_trial`, `onboard_customer`,
   `migrate_customer`, `troubleshoot_validation` and `issue_api_key` walk
   through these tasks step by step, with previews and confirmations.

## High-level workflows (prefer these over chaining low-level CRUD)

- **`netlicensing_get_customer_health(licensee_number, refresh_warning_level=False)`**
  Returns a `CustomerHealth` envelope combining licensee + license list + optional
  dry-run validation. Use when the operator asks "how is customer X doing".
  READ-ONLY — never modifies data.

- **`netlicensing_explain_validation(licensee_number, product_number=None, module_parameters=None)`**
  Returns a `ValidationExplanation` envelope: runs a dry-run validate and translates
  the result into plain-language per-module explanations and `suggested_actions`
  (renewal tokens, top-up flows, force-checkin advice).
  Use when the operator asks "why is this license failing / nearly expired / over quota".
  READ-ONLY — never consumes floating sessions, quota, or node-lock slots.

Both tools support `include_raw=True` to surface the sanitized upstream NetLicensing API response(s).

## Safety rules

- **Never delete without confirmation.** Always show the user what will be
  affected and ask for explicit approval before calling any delete tool.
- Use `force_cascade=True` only when the user explicitly requests recursive
  deletion — it removes all child entities.
- Prefer deactivating (`active=false`) over deleting when the user's intent
  is to disable rather than permanently remove.

## Conventions

- All identifiers (product_number, licensee_number, etc.) are
  case-sensitive strings chosen by the user or auto-generated by the API.
- Boolean fields are sent as lowercase strings ("true" / "false") — the
  tools handle this conversion automatically.
- An API Key with the specified role is required to use REST API.
  API Key role may limit access to the specific API endpoints or operations.
- When a tool fails with an authentication, connection or configuration
  error, or the user asks whether the setup works, run
  `netlicensing_server_info` first: its `status` and `next_steps` say what to fix.

## Output conventions

- Every entity-returning tool (list / get / create / update) emits a
  **normalized envelope** that includes a ``console_url`` field pointing
  at the entity in the NetLicensing Console UI.  When ``console_url`` is
  present, render the entity ``number`` as a Markdown link:
  ``[{number}]({console_url})``.
- List tools and validate_licensee always return
  ``{"type": "list", "kind": "...", "count": N, "items": [...]}``, also
  for zero or one item; get / create / update responses are flat dicts.
- Besides ``count`` (items in that response), list results carry the
  paging data NetLicensing reports (``total``, ``page`` (0-based),
  ``total_pages``, ``page_size``, ``has_more``, ``next_page_hint``); to
  fetch the next page, pass the value quoted in ``next_page_hint`` as
  ``filter`` with the other arguments unchanged.
- Every tool result also carries ``structuredContent``: the same JSON
  object as the text (a non-object result as ``{"result": ...}``); failed
  calls (``{"error": true, ...}``) are flagged with ``isError``.
- Error results keep ``status`` and ``detail`` (NetLicensing's own message)
  and add ``hint`` (the next step), ``suggested_actions`` (tool names to
  call next) and ``retryable`` (whether the same call may succeed later).
  The safety rules above still apply to a suggested delete or cascade.
- Pass ``include_raw=true`` to any tool to receive the sanitized
  NetLicensing API *response* nested under the ``"raw"`` key, alongside
  the normalized envelope built from it.
"""


def new_server(tool_filter: ToolFilter) -> FastMCP:
    """Create an empty FastMCP server with this project's settings.

    The ``instructions`` are :data:`INSTRUCTIONS` plus, when *tool_filter*
    restricts the tool list, a short note about it. Tools are added by the
    ``tool`` decorator (shared :data:`mcp`) or :func:`register_tools`.
    """
    return FastMCP(
        "netlicensing-mcp",
        # Stateless HTTP: every request gets a fresh transport and context, so the
        # per-request API key set by ApiKeyMiddleware is the one the tool uses. In
        # stateful mode the SDK runs a session in the task of the request that
        # created it, which pins that request's key for the whole session.
        stateless_http=True,
        instructions=INSTRUCTIONS + tool_filter.instructions_note(),
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
    )


# MCP_TOOLSETS / MCP_READ_ONLY, read once at import; the tool decorator
# consults this filter when each mcp_tools module registers its tools.
_active_filter = ToolFilter.from_env(os.environ)

mcp = new_server(_active_filter)


# ── Transport (for server_info) ──────────────────────────────────────────────

_TRANSPORTS = ("stdio", "http")

# What main() would resolve without a CLI argument; main() records the final
# choice (CLI arg → MCP_TRANSPORT → stdio) with set_transport().
_transport: str = os.getenv("MCP_TRANSPORT", "stdio").lower()
if _transport not in _TRANSPORTS:
    _transport = "stdio"


def set_transport(name: str) -> None:
    """Record the transport ``server.main()`` runs (``stdio`` or ``http``)."""
    global _transport  # noqa: PLW0603
    if name in _TRANSPORTS:
        _transport = name


def active_transport() -> str:
    """The transport this server runs: ``"stdio"`` or ``"http"``."""
    return _transport


# ── Health check (for load balancers & container orchestrators) ──────────────


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Lightweight liveness probe — returns 200 with server metadata."""
    return JSONResponse(
        {"status": "ok", "server": "netlicensing-mcp"},
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _json(obj: object) -> str:
    if is_demo_mode() and isinstance(obj, dict):
        obj = {**obj, "demo_mode": True}
    if isinstance(obj, (dict, list)):
        obj = redact(obj)
    return json.dumps(obj, indent=2)


def _json_token_read(obj: object) -> str:
    """Serialize a token *read* response (get / list) with extra credential masking.

    APIKEY token ``number`` fields and SHOP token ``shopURL`` fields are masked
    on read paths because they were shown once at creation time.  Standard
    DEFAULT_REDACT fields are also applied.
    """
    if is_demo_mode() and isinstance(obj, dict):
        obj = {**obj, "demo_mode": True}
    if isinstance(obj, (dict, list)):
        obj = redact_token_read(obj)
    return json.dumps(obj, indent=2)


def _wrap_json(
    entity: dict,
    kind: str,
    *,
    include_raw: bool = False,
    as_list: bool = False,
    warn_info_types: tuple[str, ...] = DEFAULT_WARN_INFO_TYPES,
    paging_filter: str | None = None,
) -> str:
    """Normalize *entity* into the response envelope then serialize.

    Calls :func:`wrap` to produce a flat envelope with ``console_url``,
    then passes the result through :func:`_json` for redaction and
    serialization.

    Args:
        entity:      Raw (stripped) NetLicensing API response.
        kind:        Entity type hint (e.g. ``"Licensee"``).
        include_raw: When ``True``, embed the sanitized upstream API
                     response (the input *entity*) under ``"raw"``.
        as_list:     Always return the list envelope (list tools, validate).
        paging_filter: The tool's ``filter`` argument, for list tools that
                     page through ``filter`` (enables ``next_page_hint``).
    """
    wrapped = wrap(
        entity,
        kind,
        raw=entity if include_raw else None,
        as_list=as_list,
        warn_info_types=warn_info_types,
        paging_filter=paging_filter,
    )
    return _json(wrapped)


def _scrub_apikey_console_url(env: dict) -> None:
    """Strip ``console_url`` from APIKEY and SHOP token envelopes (single or list).

    For APIKEY and SHOP tokens the ``number`` property is the credential, so
    embedding it in a URL path (``…/tokens/<apikey>``) leaks the credential
    — both on read paths (where ``number`` is masked, producing a broken URL
    that still hints at the key shape) and on create paths (where ``number``
    is the plaintext key being shown once).
    """

    def _scrub(item: dict) -> None:
        if item.get("tokenType") in ("APIKEY", "SHOP"):
            item.pop("console_url", None)

    if env.get("type") == "list":
        for it in env.get("items", []):
            if isinstance(it, dict):
                _scrub(it)
    else:
        _scrub(env)


def _wrap_json_token_read(
    entity: dict,
    *,
    include_raw: bool = False,
    as_list: bool = False,
    paging_filter: str | None = None,
) -> str:
    """Normalize a token *read* response with extra credential masking.

    Applies :func:`redact_token_read` (masks APIKEY ``number`` and SHOP
    ``shopURL``) on the original property-array structure *before* wrapping,
    then serializes via :func:`_json`. For APIKEY tokens the envelope's
    ``console_url`` is dropped — see :func:`_scrub_apikey_console_url`.
    """
    token_safe = redact_token_read(entity) if isinstance(entity, (dict, list)) else entity
    wrapped = wrap(
        token_safe,
        "Token",
        raw=token_safe if include_raw else None,
        as_list=as_list,
        paging_filter=paging_filter,
    )
    _scrub_apikey_console_url(wrapped)
    return _json(wrapped)


def _registered_tool_names() -> frozenset[str]:
    """Names of the tools the active filter registers on :data:`mcp`."""
    return frozenset(s.name for s in _TOOL_SPECS if _active_filter.allows(s.name, s.annotations))


def _error(exc: NetLicensingError, tool_name: str | None = None) -> str:
    """Return the error blob for a NetLicensing API error raised in *tool_name*.

    ``error`` / ``status`` / ``detail`` come first, then the next-step keys
    from :func:`netlicensing_mcp.errors.error_hint` (``hint``,
    ``suggested_actions``, ``retryable`` and, for 429, ``retry_after_seconds``).
    Suggestions name only tools that are registered on this server.
    """
    blob = {"error": True, "status": exc.status_code, "detail": exc.detail}
    blob.update(error_hint(exc, tool_name, available=_registered_tool_names()))
    return json.dumps(blob, indent=2)


def _confirm_error(exc: ValueError, tool_name: str | None = None) -> str:
    """Return the error blob for a rejected ``confirm_token`` in *tool_name*."""
    blob = {"error": True, "detail": str(exc)}
    blob.update(confirmation_hint(tool_name, available=_registered_tool_names()))
    return _json(blob)


def _count_items(response: dict) -> int:
    """Count items in a NetLicensing API list response (current page only)."""
    items = response.get("items", {}).get("item", [])
    return len(items) if isinstance(items, list) else 0


def _total_items(response: dict) -> int:
    """Return the *total* item count from pagination metadata.

    Reads ``totalitems`` from the ``items`` envelope returned by the
    NetLicensing paged API (e.g. when called with
    ``filter=productNumber=X;page=0;items=1``).  Falls back to counting
    the items present in the response when the metadata field is absent
    (e.g. in unit-test mocks that don't include pagination info).
    """
    items_obj = response.get("items", {})
    try:
        return int(items_obj["totalitems"])
    except (KeyError, ValueError, TypeError):
        items = items_obj.get("item", [])
        return len(items) if isinstance(items, list) else 0


def _sample_numbers(response: dict, limit: int = 3) -> list[str]:
    """Extract up to `limit` entity numbers from a NetLicensing API list response."""
    items = response.get("items", {}).get("item", [])
    if not isinstance(items, list):
        return []
    numbers: list[str] = []
    for item in items[:limit]:
        for prop in item.get("property", []):
            if isinstance(prop, dict) and prop.get("name") == "number":
                numbers.append(prop["value"])
                break
    return numbers


def _extract_props(response: dict) -> dict[str, str]:
    """Extract property name/value pairs from a single-item NetLicensing response."""
    items = response.get("items", {}).get("item", [])
    if not items:
        return {}
    return {
        p["name"]: p["value"]
        for p in items[0].get("property", [])
        if isinstance(p, dict) and "name" in p and "value" in p
    }


def _fmt_price(price: object, currency: str | None = None) -> str | None:
    """Format a price with two decimals and the currency next to it.

    ``60`` / ``"60.0"`` → ``"60.00"``; with currency ``"EUR"`` → ``"60.00 EUR"``.
    Values that are not numbers are returned unchanged; ``None``/``""`` → ``None``.
    """
    if price is None or price == "":
        return None
    try:
        text = f"{float(str(price)):.2f}"
    except ValueError:
        text = str(price)
    return f"{text} {currency}" if currency else text


def _price_active_diff(
    current: dict[str, str], price: float | None, currency: str, active: bool | None
) -> list[dict]:
    """Diff rows for a price / currency / active update preview.

    NetLicensing rejects a price without a currency, so a price-only change
    sends the current currency along; the preview shows that row too, and
    warns when there is no currency to carry over.
    """
    diff: list[dict] = []
    if price is not None:
        cur_currency = current.get("currency")
        diff.append(
            {
                "field": "price",
                "from": _fmt_price(current.get("price"), cur_currency),
                "to": _fmt_price(price, currency or cur_currency),
            }
        )
    if currency:
        diff.append({"field": "currency", "from": current.get("currency"), "to": currency})
    elif price is not None:
        cur = current.get("currency")
        row: dict = {"field": "currency", "from": cur, "to": cur}
        row["note"] = (
            "unchanged; sent with the new price because NetLicensing requires it"
            if cur
            else "no current currency: pass currency explicitly or the update will fail"
        )
        diff.append(row)
    if active is not None:
        diff.append({"field": "active", "from": current.get("active"), "to": str(active).lower()})
    return diff


# Tool behaviour hints surfaced to MCP clients (read-only vs. destructive, etc.).
# All tools call the remote NetLicensing API, hence openWorldHint=True.
_READONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
_UPDATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
_DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)


# ── Structured output ────────────────────────────────────────────────────────


def _compact_output_schema(schema: dict[str, Any]) -> None:
    """Keep the outputSchema small: it is sent with every tool in tools/list.

    Publishes only ``type``, ``additionalProperties``, ``title`` and a short
    description; the common fields are documented in the server
    ``instructions`` ("Output conventions") instead.
    """
    schema.pop("properties", None)
    schema["description"] = (
        'Same JSON as the text content; a result that is not an object is {"result": value}.'
    )


class ToolResult(BaseModel):
    """Structured result of a NetLicensing MCP tool.

    ``structuredContent`` is the parsed JSON of the text content: the same
    redacted object, field for field. Results that are not a JSON object
    (a list, a scalar or plain text) come wrapped as ``{"result": ...}``.
    The shape varies by tool, so the model accepts any object.
    """

    model_config = ConfigDict(
        extra="allow", title="NetLicensingToolResult", json_schema_extra=_compact_output_schema
    )


def to_call_tool_result(text: str) -> CallToolResult:
    """Build the MCP result for a tool's JSON string.

    The text content is *text* unchanged. ``structuredContent`` is
    ``json.loads(text)`` when that is an object, else ``{"result": value}``
    (plain text that is not JSON is wrapped as a string). An error blob
    (``{"error": true, ...}``) sets ``isError``.
    """
    try:
        value: Any = json.loads(text)
    except ValueError:
        value = text
    structured = value if isinstance(value, dict) else {"result": value}
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=structured,
        isError=isinstance(value, dict) and value.get("error") is True,
    )


ToolFn = TypeVar("ToolFn", bound=Callable[..., Awaitable[str]])


def _structured(fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[CallToolResult]]:
    """Wrap *fn* so that FastMCP registers it with structured output.

    The wrapper takes the signature of *fn*, with its annotations evaluated
    here in *fn*'s own module, so the input schema stays exactly the same.
    Only the return annotation changes, to ``Annotated[CallToolResult,
    ToolResult]``: FastMCP then publishes ``ToolResult``'s schema as the
    tool's ``outputSchema`` and passes the returned ``CallToolResult`` on
    to the client as is.
    """
    returns = Annotated[CallToolResult, ToolResult]
    signature = inspect.signature(fn, eval_str=True).replace(return_annotation=returns)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> CallToolResult:
        return to_call_tool_result(await fn(*args, **kwargs))

    wrapper.__signature__ = signature  # type: ignore[attr-defined]
    wrapper.__annotations__ = {
        **{name: p.annotation for name, p in signature.parameters.items()},
        "return": returns,
    }
    return wrapper


@dataclass(frozen=True)
class _ToolSpec:
    """A decorated tool, kept so it can be registered on any server."""

    name: str
    fn: Callable[..., Awaitable[CallToolResult]]
    title: str | None
    annotations: ToolAnnotations | None


# Every decorated tool in registration order, registered or not.
_TOOL_SPECS: list[_ToolSpec] = []


def _add(server: FastMCP, spec: _ToolSpec) -> None:
    server.add_tool(spec.fn, name=spec.name, title=spec.title, annotations=spec.annotations)


def tool(
    *, title: str | None = None, annotations: ToolAnnotations | None = None
) -> Callable[[ToolFn], ToolFn]:
    """Register a tool function with the MCP server.

    Every module in ``netlicensing_mcp.mcp_tools`` registers its tools with
    this decorator, so all registration rules live here. The tool function
    must return a JSON string; over MCP it is sent as text content plus
    ``structuredContent`` (see :func:`to_call_tool_result`). The function
    itself is returned unchanged, so direct calls still return the string.

    The tool must be listed in ``netlicensing_mcp.toolsets.TOOLSETS``. It is
    added to :data:`mcp` only if the active filter (``MCP_TOOLSETS`` /
    ``MCP_READ_ONLY``) allows it; the function is returned either way.
    """

    def decorator(fn: ToolFn) -> ToolFn:
        name = fn.__name__
        if toolset_of(name) is None:
            raise ValueError(f"{name} is not in any toolset; add it to toolsets.TOOLSETS")
        spec = _ToolSpec(name, _structured(fn), title, annotations)
        _TOOL_SPECS.append(spec)
        if _active_filter.allows(name, annotations):
            _add(mcp, spec)
        return fn

    return decorator


def register_tools(server: FastMCP, tool_filter: ToolFilter) -> None:
    """Add every decorated tool that *tool_filter* allows to *server*, in order.

    For building a server under other settings than the import-time ones
    (tests); the shared :data:`mcp` is filled by the decorator.
    """
    for spec in _TOOL_SPECS:
        if tool_filter.allows(spec.name, spec.annotations):
            _add(server, spec)


def tool_settings(tool_filter: ToolFilter) -> dict[str, Any]:
    """Toolsets, read-only flag and tool count that *tool_filter* gives."""
    return {
        "toolsets": tool_filter.toolset_list(),
        "read_only": tool_filter.read_only,
        "tool_count": sum(1 for s in _TOOL_SPECS if tool_filter.allows(s.name, s.annotations)),
    }


def active_tool_settings() -> dict[str, Any]:
    """The settings the shared :data:`mcp` was built with (for server_info).

    ``{"toolsets": [...] or ["all"], "read_only": bool, "tool_count": int}``;
    the count is complete once every ``mcp_tools`` module is imported.
    """
    return tool_settings(_active_filter)
