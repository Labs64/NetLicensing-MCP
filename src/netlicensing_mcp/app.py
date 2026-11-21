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

import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from netlicensing_mcp.client import NetLicensingError, is_demo_mode
from netlicensing_mcp.redaction import redact, redact_token_read
from netlicensing_mcp.responses import DEFAULT_WARN_INFO_TYPES, wrap

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

mcp = FastMCP(
    "netlicensing-mcp",
    # Stateless HTTP: every request gets a fresh transport and context, so the
    # per-request API key set by ApiKeyMiddleware is the one the tool uses. In
    # stateful mode the SDK runs a session in the task of the request that
    # created it, which pins that request's key for the whole session.
    stateless_http=True,
    instructions="""
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

## Output conventions

- Every entity-returning tool (list / get / create / update) emits a
  **normalized envelope** that includes a ``console_url`` field pointing
  at the entity in the NetLicensing Console UI.  When ``console_url`` is
  present, render the entity ``number`` as a Markdown link:
  ``[{number}]({console_url})``.
- List tools and validate_licensee always return
  ``{"type": "list", "kind": "...", "count": N, "items": [...]}``, also
  for zero or one item; get / create / update responses are flat dicts.
- Pass ``include_raw=true`` to any tool to receive the sanitized
  NetLicensing API *response* nested under the ``"raw"`` key, alongside
  the normalized envelope built from it.
""",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8000")),
)


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
    """
    wrapped = wrap(
        entity,
        kind,
        raw=entity if include_raw else None,
        as_list=as_list,
        warn_info_types=warn_info_types,
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


def _wrap_json_token_read(entity: dict, *, include_raw: bool = False, as_list: bool = False) -> str:
    """Normalize a token *read* response with extra credential masking.

    Applies :func:`redact_token_read` (masks APIKEY ``number`` and SHOP
    ``shopURL``) on the original property-array structure *before* wrapping,
    then serializes via :func:`_json`. For APIKEY tokens the envelope's
    ``console_url`` is dropped — see :func:`_scrub_apikey_console_url`.
    """
    token_safe = redact_token_read(entity) if isinstance(entity, (dict, list)) else entity
    wrapped = wrap(token_safe, "Token", raw=token_safe if include_raw else None, as_list=as_list)
    _scrub_apikey_console_url(wrapped)
    return _json(wrapped)


def _error(exc: NetLicensingError) -> str:
    """Return a user-friendly error string from a NetLicensing API error."""
    return json.dumps({"error": True, "status": exc.status_code, "detail": exc.detail}, indent=2)


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


# Decorator used by every module in netlicensing_mcp.mcp_tools to register a tool.
tool = mcp.tool
