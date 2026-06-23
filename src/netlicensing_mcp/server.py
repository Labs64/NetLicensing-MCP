"""
NetLicensing MCP Server
=======================
Entry point for both stdio (Claude Desktop / Copilot) and HTTP (remote) modes.

Usage:
  stdio (default):  python -m netlicensing_mcp.server
  HTTP mode:        python -m netlicensing_mcp.server http
  Dev / inspector:  mcp dev src/netlicensing_mcp/server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import argparse

from mcp.server.fastmcp import FastMCP

from starlette.requests import Request
from starlette.responses import JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware

from netlicensing_mcp.client import NetLicensingError, api_key_ctx, is_demo_mode
from netlicensing_mcp import safety
from netlicensing_mcp.redaction import redact, redact_token_read, tag_one_time_display
from netlicensing_mcp.responses import wrap
from netlicensing_mcp.prompts.audit import register_audit_prompts
from netlicensing_mcp.tools import (
    bundles,
    license_templates,
    licensees,
    licenses,
    payment_methods,
    product_modules,
    products,
    tokens,
    transactions,
    utilities,
)

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "netlicensing-mcp",
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
   validate_licensee returns per-module validity, expiry, and quota.
   For Floating models pass `session_id` + `action` (checkOut/checkIn).
   For NodeLocked models pass `product_module_number` + `node_secret`.
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

Both tools support `include_raw=True` to surface the upstream NetLicensing payloads.

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
- List responses have the shape
  ``{"type": "list", "kind": "...", "count": N, "items": [...]}``;
  single-entity responses are flat dicts.
- Pass ``include_raw=true`` to any tool to receive the original
  NetLicensing API payload nested under the ``"raw"`` key alongside the
  normalized envelope.
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


def _wrap_json(entity: dict, kind: str, *, include_raw: bool = False) -> str:
    """Normalize *entity* into the response envelope then serialize.

    Calls :func:`wrap` to produce a flat envelope with ``console_url``,
    then passes the result through :func:`_json` for redaction and
    serialization.

    Args:
        entity:      Raw (stripped) NetLicensing API response.
        kind:        Entity type hint (e.g. ``"Licensee"``).
        include_raw: When ``True``, embed the original payload under ``"raw"``.
    """
    wrapped = wrap(entity, kind, raw=entity if include_raw else None)
    return _json(wrapped)


def _scrub_apikey_console_url(env: dict) -> None:
    """Strip ``console_url`` from APIKEY token envelopes (single or list).

    For APIKEY tokens the ``number`` property *is* the API key value, so
    embedding it in a URL path (``…/tokens/<apikey>``) leaks the credential
    — both on read paths (where ``number`` is masked, producing a broken URL
    that still hints at the key shape) and on create paths (where ``number``
    is the plaintext key being shown once).
    """

    def _scrub(item: dict) -> None:
        if item.get("tokenType") == "APIKEY":
            item.pop("console_url", None)

    if env.get("type") == "list":
        for it in env.get("items", []):
            if isinstance(it, dict):
                _scrub(it)
    else:
        _scrub(env)


def _wrap_json_token_read(entity: dict, *, include_raw: bool = False) -> str:
    """Normalize a token *read* response with extra credential masking.

    Applies :func:`redact_token_read` (masks APIKEY ``number`` and SHOP
    ``shopURL``) on the original property-array structure *before* wrapping,
    then serializes via :func:`_json`. For APIKEY tokens the envelope's
    ``console_url`` is dropped — see :func:`_scrub_apikey_console_url`.
    """
    token_safe = redact_token_read(entity) if isinstance(entity, (dict, list)) else entity
    wrapped = wrap(token_safe, "Token", raw=token_safe if include_raw else None)
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


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_products(filter: str = "", include_raw: bool = False) -> str:
    """List all products in the NetLicensing account.

    Args:
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await products.list_products(filter_str=filter or None),
            "Product",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_product(product_number: str, include_raw: bool = False) -> str:
    """Get details of a specific product.

    Args:
        product_number: Product identifier (e.g. 'P001')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await products.get_product(product_number), "Product", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_product(
    number: str,
    name: str,
    version: str = "1.0",
    active: bool = True,
    description: str = "",
    licensing_info: str = "",
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
    licensee_secret_mode: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new product.

    Args:
        number: Unique product number (e.g. 'P001')
        name: Human-readable product name
        version: Product version string
        active: Whether the product is active
        description: Optional product description
        licensing_info: Optional licensing information displayed in the shop
        licensee_auto_create: Auto-create licensees on first validation attempt
        vat_mode: GROSS or NET (leave empty to use account default)
        licensee_secret_mode: DISABLED, PREDEFINED, or CLIENT (leave empty for default)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await products.create_product(
                number,
                name,
                active,
                version,
                description,
                licensing_info=licensing_info,
                licensee_auto_create=licensee_auto_create,
                vat_mode=vat_mode or None,
                licensee_secret_mode=licensee_secret_mode or None,
            ),
            "Product",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_update_product(
    product_number: str,
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
) -> str:
    """Preview a sensitive product update (licenseeAutoCreate or vatMode change).

    Returns a diff of proposed changes and a confirmation token. Pass the
    token to netlicensing_update_product within 5 minutes to apply.

    Args:
        product_number: Product to preview changes for
        licensee_auto_create: Proposed new auto-create setting (omit to skip)
        vat_mode: Proposed new VAT mode — GROSS or NET (leave empty to skip)
    """
    try:
        current_resp = await products.get_product(product_number)
        current = _extract_props(current_resp)
        diff: list[dict] = []
        if licensee_auto_create is not None:
            diff.append(
                {
                    "field": "licenseeAutoCreate",
                    "from": current.get("licenseeAutoCreate"),
                    "to": str(licensee_auto_create).lower(),
                }
            )
        if vat_mode:
            diff.append({"field": "vatMode", "from": current.get("vatMode"), "to": vat_mode})
        return _json(safety.make_update_preview("update_product", product_number, diff))
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_product(
    product_number: str,
    name: str = "",
    active: bool | None = None,
    version: str = "",
    description: str = "",
    licensing_info: str = "",
    licensee_auto_create: bool | None = None,
    vat_mode: str = "",
    licensee_secret_mode: str = "",
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update an existing product's fields.

    Changing licenseeAutoCreate or vatMode requires a confirmation token
    (downstream business effect). Call netlicensing_preview_update_product first.

    Args:
        product_number: Product to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        version: New version string (leave empty to keep current)
        description: New description (leave empty to keep current)
        licensing_info: Licensing information for the shop (leave empty to keep current)
        licensee_auto_create: Auto-create licensees on first validation
        vat_mode: GROSS or NET (leave empty to keep current)
        licensee_secret_mode: DISABLED, PREDEFINED, or CLIENT (leave empty to keep current)
        confirm_token: Confirmation token (required when licenseeAutoCreate or vatMode change)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        sensitive = licensee_auto_create is not None or bool(vat_mode)

        if sensitive:
            if confirm_token:
                safety.validate_and_consume(confirm_token, "update_product", product_number)
            else:
                current_resp = await products.get_product(product_number)
                current = _extract_props(current_resp)
                diff: list[dict] = []
                if licensee_auto_create is not None:
                    diff.append(
                        {
                            "field": "licenseeAutoCreate",
                            "from": current.get("licenseeAutoCreate"),
                            "to": str(licensee_auto_create).lower(),
                        }
                    )
                if vat_mode:
                    diff.append(
                        {
                            "field": "vatMode",
                            "from": current.get("vatMode"),
                            "to": vat_mode,
                        }
                    )
                return _json(safety.make_update_preview("update_product", product_number, diff))

        return _wrap_json(
            await products.update_product(
                product_number,
                name or None,
                active,
                version or None,
                description or None,
                licensing_info=licensing_info or None,
                licensee_auto_create=licensee_auto_create,
                vat_mode=vat_mode or None,
                licensee_secret_mode=licensee_secret_mode or None,
            ),
            "Product",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_product(product_number: str) -> str:
    """Preview what would be deleted when deleting a product.

    Returns affected counts, sample entity identifiers, and a short-lived
    confirmation token. Pass the token to netlicensing_delete_product within
    5 minutes to confirm the deletion.

    Args:
        product_number: Product to preview deletion for
    """
    try:
        # Use filter-embedded pagination to get accurate total counts from
        # the API metadata (``totalitems``), not just the current page.
        # items=1 for modules — only total count is needed, no samples.
        # items=100 for licensees — fetch enough to also extract samples.
        modules_resp = await product_modules.list_product_modules(
            product_number, page=0, items_per_page=1
        )
        licensees_resp = await licensees.list_licensees(product_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_product",
                product_number,
                affected={
                    "product_modules": _total_items(modules_resp),
                    "licensees": _total_items(licensees_resp),
                },
                samples={"licensees": _sample_numbers(licensees_resp)},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_product(
    product_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a product permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_product)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        product_number: Product to delete
        force_cascade: Also delete all dependent modules, templates, licensees, and licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_product", product_number)
            return await products.delete_product(product_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        modules_resp = await product_modules.list_product_modules(
            product_number, page=0, items_per_page=1
        )
        licensees_resp = await licensees.list_licensees(product_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_product",
                product_number,
                affected={
                    "product_modules": _total_items(modules_resp),
                    "licensees": _total_items(licensees_resp),
                },
                samples={"licensees": _sample_numbers(licensees_resp)},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# BUNDLES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_bundles(include_raw: bool = False) -> str:
    """List all bundles in the NetLicensing account.

    Args:
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(await bundles.list_bundles(), "Bundle", include_raw=include_raw)
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_bundle(bundle_number: str, include_raw: bool = False) -> str:
    """Get details of a specific bundle.

    Args:
        bundle_number: Bundle identifier (e.g. 'B001')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await bundles.get_bundle(bundle_number), "Bundle", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_bundle(
    number: str,
    name: str,
    license_template_numbers: list[str],
    active: bool = True,
    price: float | None = None,
    currency: str = "",
    description: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new bundle grouping one or more license templates.

    Args:
        number: Unique bundle number (e.g. 'B001')
        name: Human-readable bundle name
        license_template_numbers: List of license template numbers included in the bundle
        active: Whether the bundle is active
        price: Optional bundle price
        currency: ISO 4217 currency code (e.g. EUR, USD — leave empty for account default)
        description: Optional bundle description
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await bundles.create_bundle(
                number,
                name,
                license_template_numbers,
                active,
                price=price,
                currency=currency or None,
                description=description,
            ),
            "Bundle",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_bundle(
    bundle_number: str,
    name: str = "",
    active: bool | None = None,
    license_template_numbers: list[str] | None = None,
    price: float | None = None,
    currency: str = "",
    description: str = "",
    include_raw: bool = False,
) -> str:
    """Update an existing bundle's fields.

    Args:
        bundle_number: Bundle to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        license_template_numbers: New list of license template numbers (omit to keep current)
        price: New price (omit to keep current)
        currency: New currency code (leave empty to keep current)
        description: New description (leave empty to keep current)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await bundles.update_bundle(
                bundle_number,
                name or None,
                active,
                license_template_numbers,
                price,
                currency or None,
                description or None,
            ),
            "Bundle",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_bundle(bundle_number: str) -> str:
    """Preview what would be deleted when deleting a bundle.

    Bundles reference license templates but do not own them; only the bundle
    record itself is removed. Returns a confirmation token.

    Args:
        bundle_number: Bundle to preview deletion for
    """
    try:
        bundle_resp = await bundles.get_bundle(bundle_number)
        props = _extract_props(bundle_resp)
        return _json(
            safety.make_delete_preview(
                "delete_bundle",
                bundle_number,
                affected={
                    "license_templates": "referenced only — will NOT be deleted",
                },
                samples={"bundle_name": props.get("name", "")},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_bundle(
    bundle_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a bundle permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_bundle)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        bundle_number: Bundle to delete
        force_cascade: Force deletion even if dependencies exist
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_bundle", bundle_number)
            return await bundles.delete_bundle(bundle_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        bundle_resp = await bundles.get_bundle(bundle_number)
        props = _extract_props(bundle_resp)
        return _json(
            safety.make_delete_preview(
                "delete_bundle",
                bundle_number,
                affected={"license_templates": "referenced only — will NOT be deleted"},
                samples={"bundle_name": props.get("name", "")},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_obtain_bundle(
    bundle_number: str,
    licensee_number: str,
    include_raw: bool = False,
) -> str:
    """Obtain a bundle for a customer — creates licenses from all license
    templates included in the bundle for the specified licensee.

    Args:
        bundle_number: Bundle to obtain
        licensee_number: Customer (licensee) who receives the licenses
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await bundles.obtain_bundle(bundle_number, licensee_number),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT MODULES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_product_modules(
    product_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all modules (feature groups) for a product.

    Args:
        product_number: Product whose modules to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await product_modules.list_product_modules(
                product_number,
                filter_str=filter or None,
            ),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_product_module(module_number: str, include_raw: bool = False) -> str:
    """Get a specific product module.

    Args:
        module_number: Module identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await product_modules.get_product_module(module_number),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_product_module(
    product_number: str,
    number: str,
    name: str,
    licensing_model: str,
    active: bool = True,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str = "",
    custom_properties: dict[str, str] | None = None,
    include_raw: bool = False,
) -> str:
    """Create a product module with a licensing model.

    Args:
        product_number: Parent product
        number: Unique module number (e.g. 'M01')
        name: Module name
        licensing_model: One of: TryAndBuy, Subscription, Rental, Floating,
                         MultiFeature, PayPerUse, PricingTable, Quota, NodeLocked
        active: Whether the module is active
        max_checkout_validity: Maximum checkout validity in days (Floating model)
        yellow_threshold: Remaining time volume for yellow warning (Rental model)
        red_threshold: Remaining time volume for red warning (Rental model)
        node_secret_mode: PREDEFINED or CLIENT (NodeLocked model)
        custom_properties: Additional properties as key-value pairs (e.g. skudef for PricingTable)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await product_modules.create_product_module(
                product_number,
                number,
                name,
                licensing_model,
                active,
                max_checkout_validity=max_checkout_validity,
                yellow_threshold=yellow_threshold,
                red_threshold=red_threshold,
                node_secret_mode=node_secret_mode or None,
                custom_properties=custom_properties,
            ),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_product_module(
    module_number: str,
    name: str = "",
    active: bool | None = None,
    max_checkout_validity: int | None = None,
    yellow_threshold: int | None = None,
    red_threshold: int | None = None,
    node_secret_mode: str = "",
    custom_properties: dict[str, str] | None = None,
    include_raw: bool = False,
) -> str:
    """Update a product module's properties.

    Args:
        module_number: Module to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        max_checkout_validity: Maximum checkout validity in days (Floating model, omit to keep current)
        yellow_threshold: Remaining time volume for yellow warning (Rental model, omit to keep current)
        red_threshold: Remaining time volume for red warning (Rental model, omit to keep current)
        node_secret_mode: PREDEFINED or CLIENT (NodeLocked model, leave empty to keep current)
        custom_properties: Additional properties to set or update as key-value pairs
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await product_modules.update_product_module(
                module_number,
                name or None,
                active,
                max_checkout_validity=max_checkout_validity,
                yellow_threshold=yellow_threshold,
                red_threshold=red_threshold,
                node_secret_mode=node_secret_mode or None,
                custom_properties=custom_properties,
            ),
            "ProductModule",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_product_module(module_number: str) -> str:
    """Preview what would be deleted when deleting a product module.

    Returns affected license template counts and a confirmation token.

    Args:
        module_number: Module to preview deletion for
    """
    try:
        templates_resp = await license_templates.list_license_templates(
            module_number, page=0, items_per_page=100
        )
        return _json(
            safety.make_delete_preview(
                "delete_product_module",
                module_number,
                affected={"license_templates": _total_items(templates_resp)},
                samples={"license_templates": _sample_numbers(templates_resp)},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_product_module(
    module_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a product module.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_product_module)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        module_number: Module to delete
        force_cascade: Also delete all dependent license templates and licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_product_module", module_number)
            return await product_modules.delete_product_module(module_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        templates_resp = await license_templates.list_license_templates(
            module_number, page=0, items_per_page=100
        )
        return _json(
            safety.make_delete_preview(
                "delete_product_module",
                module_number,
                affected={"license_templates": _total_items(templates_resp)},
                samples={"license_templates": _sample_numbers(templates_resp)},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_license_templates(
    module_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all license templates for a product module.

    Args:
        module_number: Module whose templates to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await license_templates.list_license_templates(
                module_number,
                filter_str=filter or None,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_license_template(template_number: str, include_raw: bool = False) -> str:
    """Get a specific license template.

    Args:
        template_number: Template identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await license_templates.get_license_template(template_number),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_license_template(
    module_number: str,
    number: str,
    name: str,
    license_type: str,
    price: float = 0.0,
    currency: str = "EUR",
    automatic: bool = False,
    hidden: bool = False,
    hide_licenses: bool = False,
    active: bool = True,
    time_volume: int | None = None,
    time_volume_period: str = "",
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
    custom_properties: dict[str, str] | None = None,
    include_raw: bool = False,
) -> str:
    """Create a license template.

    Args:
        module_number: Parent product module
        number: Unique template number (e.g. 'LT01')
        name: Template display name
        license_type: FEATURE | TIMEVOLUME | FLOATING | QUANTITY
        price: Template price (0 for free)
        currency: ISO 4217 currency code (default EUR)
        automatic: Auto-assign this license to new licensees
        hidden: Hide template in NetLicensing Shop
        hide_licenses: Hide licenses derived from this template in the Shop
        active: Whether the template is active
        time_volume: Number of time units (TIMEVOLUME type)
        time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME type)
        max_sessions: Concurrent sessions allowed (FLOATING type)
        quantity: Usage quota (QUANTITY / PayPerUse type)
        grace_period: Allow grace period after expiry (Subscription model)
        custom_properties: Additional properties as key-value pairs (e.g. skus for PricingTable, description)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await license_templates.create_license_template(
                module_number,
                number,
                name,
                license_type,
                active,
                price,
                currency,
                automatic,
                hidden=hidden,
                hide_licenses=hide_licenses,
                time_volume=time_volume,
                time_volume_period=time_volume_period or None,
                max_sessions=max_sessions,
                quantity=quantity,
                grace_period=grace_period,
                custom_properties=custom_properties,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_update_license_template(
    template_number: str,
    active: bool | None = None,
    price: float | None = None,
    currency: str = "",
) -> str:
    """Preview a sensitive license template update (price, currency, or active state).

    Returns a diff table of the proposed changes and a confirmation token. Pass
    the token to netlicensing_update_license_template within 5 minutes to apply.

    Args:
        template_number: Template to preview changes for
        active: Proposed new active state (omit to skip)
        price: Proposed new price (omit to skip)
        currency: Proposed new currency code (leave empty to skip)
    """
    try:
        current_resp = await license_templates.get_license_template(template_number)
        current = _extract_props(current_resp)
        diff: list[dict] = []
        if price is not None:
            diff.append({"field": "price", "from": current.get("price"), "to": str(price)})
        if currency:
            diff.append({"field": "currency", "from": current.get("currency"), "to": currency})
        if active is not None:
            diff.append(
                {
                    "field": "active",
                    "from": current.get("active"),
                    "to": str(active).lower(),
                }
            )
        return _json(safety.make_update_preview("update_license_template", template_number, diff))
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_license_template(
    template_number: str,
    name: str = "",
    active: bool | None = None,
    price: float | None = None,
    currency: str = "",
    automatic: bool | None = None,
    hidden: bool | None = None,
    hide_licenses: bool | None = None,
    time_volume: int | None = None,
    time_volume_period: str = "",
    max_sessions: int | None = None,
    quantity: int | None = None,
    grace_period: bool | None = None,
    custom_properties: dict[str, str] | None = None,
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update a license template's properties.

    Changing price, currency, or active requires a confirmation token (revenue /
    availability impact). Call netlicensing_preview_update_license_template first.

    Args:
        template_number: Template to update
        name: New name (leave empty to keep current)
        active: Set active state (omit to keep current)
        price: New price (omit to keep current)
        currency: New ISO 4217 currency code (leave empty to keep current)
        automatic: Auto-assign to new licensees (omit to keep current)
        hidden: Hide template in NetLicensing Shop (omit to keep current)
        hide_licenses: Hide derived licenses in the Shop (omit to keep current)
        time_volume: Number of time units — TIMEVOLUME type (omit to keep current)
        time_volume_period: DAY | WEEK | MONTH | YEAR — TIMEVOLUME type (leave empty to keep current)
        max_sessions: Concurrent sessions — FLOATING type (omit to keep current)
        quantity: Usage quota — QUANTITY / PayPerUse type (omit to keep current)
        grace_period: Grace period after expiry — Subscription model (omit to keep current)
        custom_properties: Additional properties to set or update as key-value pairs
        confirm_token: Confirmation token (required when price, currency, or active change)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        sensitive = price is not None or bool(currency) or active is not None

        if sensitive:
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_license_template", template_number
                )
            else:
                current_resp = await license_templates.get_license_template(template_number)
                current = _extract_props(current_resp)
                diff: list[dict] = []
                if price is not None:
                    diff.append({"field": "price", "from": current.get("price"), "to": str(price)})
                if currency:
                    diff.append(
                        {
                            "field": "currency",
                            "from": current.get("currency"),
                            "to": currency,
                        }
                    )
                if active is not None:
                    diff.append(
                        {
                            "field": "active",
                            "from": current.get("active"),
                            "to": str(active).lower(),
                        }
                    )
                return _json(
                    safety.make_update_preview("update_license_template", template_number, diff)
                )

        return _wrap_json(
            await license_templates.update_license_template(
                template_number,
                name or None,
                active,
                price,
                currency=currency or None,
                automatic=automatic,
                hidden=hidden,
                hide_licenses=hide_licenses,
                time_volume=time_volume,
                time_volume_period=time_volume_period or None,
                max_sessions=max_sessions,
                quantity=quantity,
                grace_period=grace_period,
                custom_properties=custom_properties,
            ),
            "LicenseTemplate",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_license_template(template_number: str) -> str:
    """Preview what would be deleted when deleting a license template.

    Dependent licenses cannot be efficiently counted without enumerating all
    licensees, so the preview always warns that licenses may be affected.
    Returns a confirmation token.

    Args:
        template_number: Template to preview deletion for
    """
    try:
        template_resp = await license_templates.get_license_template(template_number)
        props = _extract_props(template_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license_template",
                template_number,
                affected={
                    "licenses": "unknown — may have licenses derived from this template",
                },
                samples={
                    "template_name": props.get("name", ""),
                    "price": props.get("price", ""),
                },
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_license_template(
    template_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a license template.

    Because dependent licenses cannot be cheaply enumerated, a confirmation
    token is always required. Call netlicensing_preview_delete_license_template
    first to obtain one.

    Args:
        template_number: Template to delete
        force_cascade: Also delete all dependent licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_license_template", template_number)
            return await license_templates.delete_license_template(template_number, force_cascade)

        template_resp = await license_templates.get_license_template(template_number)
        props = _extract_props(template_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license_template",
                template_number,
                affected={
                    "licenses": "unknown — may have licenses derived from this template",
                },
                samples={
                    "template_name": props.get("name", ""),
                    "price": props.get("price", ""),
                },
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSEES  (customers)
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_licensees(
    product_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all customers (licensees) for a product.

    Args:
        product_number: Product to list customers for
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.list_licensees(
                product_number,
                filter_str=filter or None,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_licensee(licensee_number: str, include_raw: bool = False) -> str:
    """Get a specific licensee (customer).

    Args:
        licensee_number: Licensee identifier (e.g. 'I001')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.get_licensee(licensee_number),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_licensee(
    product_number: str,
    number: str = "",
    name: str = "",
    active: bool = True,
    marked_for_transfer: bool | None = None,
    licensee_secret: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new customer (licensee) under a product.

    Args:
        product_number: Product to associate the customer with
        number: Optional custom licensee number (auto-generated if empty)
        name: Optional display name for the customer
        active: Whether the licensee is active
        marked_for_transfer: Mark licensee for license transfer
        licensee_secret: Secret for licensee identification (when product licenseeSecretMode is PREDEFINED)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.create_licensee(
                product_number,
                number or None,
                name or None,
                active,
                marked_for_transfer=marked_for_transfer,
                licensee_secret=licensee_secret or None,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_licensee(
    licensee_number: str,
    name: str = "",
    active: bool | None = None,
    marked_for_transfer: bool | None = None,
    licensee_secret: str = "",
    include_raw: bool = False,
) -> str:
    """Update a licensee's properties.

    Args:
        licensee_number: Licensee to update
        name: New name (empty to keep current)
        active: New active state (omit to keep current)
        marked_for_transfer: Mark for license transfer (omit to keep current)
        licensee_secret: Secret for licensee identification (leave empty to keep current)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.update_licensee(
                licensee_number,
                name or None,
                active,
                marked_for_transfer=marked_for_transfer,
                licensee_secret=licensee_secret or None,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_licensee(licensee_number: str) -> str:
    """Preview what would be deleted when deleting a licensee.

    Returns the count of licenses that would be removed and a confirmation token.

    Args:
        licensee_number: Licensee to preview deletion for
    """
    try:
        licenses_resp = await licenses.list_licenses(licensee_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_licensee",
                licensee_number,
                affected={"licenses": _total_items(licenses_resp)},
                samples={"licenses": _sample_numbers(licenses_resp)},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_licensee(
    licensee_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a licensee and all their licenses permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_licensee)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        licensee_number: Licensee to delete
        force_cascade: Also delete all dependent licenses
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_licensee", licensee_number)
            return await licensees.delete_licensee(licensee_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        licenses_resp = await licenses.list_licenses(licensee_number, page=0, items_per_page=100)
        return _json(
            safety.make_delete_preview(
                "delete_licensee",
                licensee_number,
                affected={"licenses": _total_items(licenses_resp)},
                samples={"licenses": _sample_numbers(licenses_resp)},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_validate_licensee(
    licensee_number: str,
    product_number: str = "",
    licensee_name: str = "",
    session_id: str = "",
    action: str = "",
    product_module_number: str = "",
    node_secret: str = "",
    include_raw: bool = False,
) -> str:
    """Validate a customer's licenses across all product modules.

    Returns per-module validity, type, expiry dates, and usage counts.

    Args:
        licensee_number: Customer to validate
        product_number: Optional — scope validation to a specific product
        licensee_name: Human-readable name for auto-created licensees (when licenseeAutoCreate is enabled)
        session_id: Floating model — unique session identifier
        action: Floating model — 'checkOut' or 'checkIn'
        product_module_number: NodeLocked model — target product module
        node_secret: NodeLocked model — unique device/node secret
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.validate_licensee(
                licensee_number,
                product_number=product_number or None,
                licensee_name=licensee_name or None,
                session_id=session_id or None,
                action=action or None,
                product_module_number=product_module_number or None,
                node_secret=node_secret or None,
            ),
            "ProductModuleValidation",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_transfer_licenses(
    from_licensee_number: str,
    to_licensee_number: str,
    include_raw: bool = False,
) -> str:
    """Transfer all licenses from one licensee to another.

    Args:
        from_licensee_number: Source licensee
        to_licensee_number: Destination licensee
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licensees.transfer_licenses(
                from_licensee_number,
                to_licensee_number,
            ),
            "Licensee",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# LICENSES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_licenses(
    licensee_number: str, filter: str = "", include_raw: bool = False
) -> str:
    """List all licenses for a specific customer.

    Args:
        licensee_number: Customer whose licenses to list
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licenses.list_licenses(
                licensee_number,
                filter_str=filter or None,
            ),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_license(license_number: str, include_raw: bool = False) -> str:
    """Get details of a specific license.

    Args:
        license_number: License identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licenses.get_license(license_number),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_license(
    licensee_number: str,
    license_template_number: str,
    number: str = "",
    active: bool = True,
    name: str = "",
    start_date: str = "",
    price: float | None = None,
    currency: str = "",
    time_volume: str = "",
    time_volume_period: str = "",
    quantity: str = "",
    parent_feature: str = "",
    hidden: bool | None = None,
    include_raw: bool = False,
) -> str:
    """Assign a new license to a customer from a license template.

    Args:
        licensee_number: Customer to assign the license to
        license_template_number: Template defining type and rules
        number: Optional custom license number (auto-generated if empty)
        active: Whether the license is active immediately
        name: Display name (defaults from template if empty)
        start_date: ISO 8601 datetime — mandatory for TIMEVOLUME type
        price: License price (overrides template default, omit to inherit)
        currency: ISO 4217 currency code (overrides template default)
        time_volume: Duration value — mandatory for TIMEVOLUME type
        time_volume_period: DAY | WEEK | MONTH | YEAR (TIMEVOLUME type)
        quantity: Usage quota — mandatory for PayPerUse / NodeLocked models
        parent_feature: Parent feature — mandatory for TIMEVOLUME + Rental model
        hidden: Hide license from end customer in Shop (omit to inherit)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licenses.create_license(
                licensee_number,
                license_template_number,
                number or None,
                active,
                name=name or None,
                start_date=start_date or None,
                price=price,
                currency=currency or None,
                time_volume=time_volume or None,
                time_volume_period=time_volume_period or None,
                quantity=quantity or None,
                parent_feature=parent_feature or None,
                hidden=hidden,
            ),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_license(
    license_number: str,
    active: bool | None = None,
    name: str = "",
    start_date: str = "",
    price: float | None = None,
    currency: str = "",
    time_volume: str = "",
    time_volume_period: str = "",
    quantity: str = "",
    used_quantity: str = "",
    parent_feature: str = "",
    hidden: bool | None = None,
    include_raw: bool = False,
) -> str:
    """Update a license's properties.

    Args:
        license_number: License to update
        active: True to activate, False to deactivate (omit to keep current)
        name: New display name (leave empty to keep current)
        start_date: ISO 8601 datetime — TIMEVOLUME type (leave empty to keep current)
        price: License price (omit to keep current)
        currency: ISO 4217 currency code (leave empty to keep current)
        time_volume: Duration value — TIMEVOLUME type (leave empty to keep current)
        time_volume_period: DAY | WEEK | MONTH | YEAR (leave empty to keep current)
        quantity: Usage quota — PayPerUse model (leave empty to keep current)
        used_quantity: Used count — PayPerUse model (leave empty to keep current)
        parent_feature: Parent feature — Rental model (leave empty to keep current)
        hidden: Visibility in Shop (omit to keep current)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await licenses.update_license(
                license_number,
                active,
                name=name or None,
                start_date=start_date or None,
                price=price,
                currency=currency or None,
                time_volume=time_volume or None,
                time_volume_period=time_volume_period or None,
                quantity=quantity or None,
                used_quantity=used_quantity or None,
                parent_feature=parent_feature or None,
                hidden=hidden,
            ),
            "License",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_license(license_number: str) -> str:
    """Preview what would be deleted when deleting a license.

    Licenses have no owned dependents. Returns context about the license
    (licensee, template) and a confirmation token.

    Args:
        license_number: License to preview deletion for
    """
    try:
        license_resp = await licenses.get_license(license_number)
        props = _extract_props(license_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license",
                license_number,
                affected={},
                samples={
                    "licensee": props.get("licenseeNumber", ""),
                    "template": props.get("licenseTemplateNumber", ""),
                },
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_license(
    license_number: str,
    force_cascade: bool = False,
    confirm_token: str = "",
) -> str:
    """Delete a license permanently.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_license)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        license_number: License to delete
        force_cascade: Force deletion even if dependencies exist
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_license", license_number)
            return await licenses.delete_license(license_number, force_cascade)

        # No token — always show preview; deletion is never allowed without confirmation.
        license_resp = await licenses.get_license(license_number)
        props = _extract_props(license_resp)
        return _json(
            safety.make_delete_preview(
                "delete_license",
                license_number,
                affected={},
                samples={
                    "licensee": props.get("licenseeNumber", ""),
                    "template": props.get("licenseTemplateNumber", ""),
                },
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# TOKENS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_tokens(filter: str = "", include_raw: bool = False) -> str:
    """List all active tokens in the account.

    Args:
        filter: Optional server-side filter expression (e.g. 'tokenType=SHOP')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json_token_read(
            await tokens.list_tokens(filter_str=filter or None),
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_token(token_number: str, include_raw: bool = False) -> str:
    """Get details of a specific token.

    Args:
        token_number: Token identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json_token_read(
            await tokens.get_token(token_number),
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_shop_token(
    licensee_number: str,
    product_number: str = "",
    license_template_number: str = "",
    success_url: str = "",
    cancel_url: str = "",
    success_url_title: str = "",
    cancel_url_title: str = "",
    include_raw: bool = False,
) -> str:
    """Generate a NetLicensing Shop one-time checkout URL for a customer.

    Args:
        licensee_number: Customer to generate the shop URL for
        product_number: Optional — scope shop to a specific product
        license_template_number: Optional — pre-select a specific license template
        success_url: Optional URL to redirect to after successful purchase
        cancel_url: Optional URL to redirect to if customer cancels
        success_url_title: Optional button/link label for success redirect
        cancel_url_title: Optional button/link label for cancel redirect
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        raw = await tokens.create_shop_token(
            licensee_number,
            product_number=product_number or None,
            license_template_number=license_template_number or None,
            success_url=success_url or None,
            cancel_url=cancel_url or None,
            success_url_title=success_url_title or None,
            cancel_url_title=cancel_url_title or None,
        )
        wrapped = wrap(raw, "Token", raw=raw if include_raw else None)
        return _json(tag_one_time_display(wrapped))
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_api_token(
    api_key_role: str = "ROLE_APIKEY_LICENSEE",
    licensee_number: str = "",
    include_raw: bool = False,
) -> str:
    """Create a scoped API token.

    Args:
        api_key_role: ROLE_APIKEY_LICENSEE | ROLE_APIKEY_ANALYTICS |
              ROLE_APIKEY_OPERATION | ROLE_APIKEY_MAINTENANCE | ROLE_APIKEY_ADMIN
        licensee_number: Optional — scope token to a specific licensee
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        raw = await tokens.create_api_token(api_key_role, licensee_number or None)
        wrapped = wrap(raw, "Token", raw=raw if include_raw else None)
        _scrub_apikey_console_url(wrapped)
        return _json(tag_one_time_display(wrapped))
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_delete_token(token_number: str) -> str:
    """Preview what would be revoked when deleting a token.

    For APIKEY tokens this is always required before deletion.
    Returns token kind, role, and a confirmation token.

    Args:
        token_number: Token to preview deletion for
    """
    try:
        token_resp = await tokens.get_token(token_number)
        props = _extract_props(token_resp)
        return _json(
            safety.make_delete_preview(
                "delete_token",
                token_number,
                affected={
                    "token_type": props.get("tokenType", "UNKNOWN"),
                    "role": props.get("role", ""),
                },
                samples={},
            )
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_delete_token(
    token_number: str,
    confirm_token: str = "",
) -> str:
    """Revoke an API or shop token.

    Always requires a two-step confirmation:
    1. Call without confirm_token (or call netlicensing_preview_delete_token)
       to receive a preview and a short-lived confirmation token.
    2. Call again with the confirm_token within 5 minutes to execute.

    Args:
        token_number: Token to revoke
        confirm_token: Confirmation token from a previous preview call
    """
    try:
        if confirm_token:
            safety.validate_and_consume(confirm_token, "delete_token", token_number)
            return await tokens.delete_token(token_number)

        # No token — always show preview; deletion is never allowed without confirmation.
        token_resp = await tokens.get_token(token_number)
        props = _extract_props(token_resp)
        return _json(
            safety.make_delete_preview(
                "delete_token",
                token_number,
                affected={
                    "token_type": props.get("tokenType", "UNKNOWN"),
                    "role": props.get("role", ""),
                },
                samples={},
            )
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_transactions(filter: str = "", include_raw: bool = False) -> str:
    """List all transactions in the account.

    Args:
        filter: Optional server-side filter expression (e.g. 'status=CLOSED')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await transactions.list_transactions(
                filter_str=filter or None,
            ),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_transaction(transaction_number: str, include_raw: bool = False) -> str:
    """Get details of a specific transaction.

    Args:
        transaction_number: Transaction identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await transactions.get_transaction(transaction_number),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_create_transaction(
    status: str,
    source: str = "SHOP",
    licensee_number: str = "",
    number: str = "",
    name: str = "",
    active: bool = True,
    date_created: str = "",
    date_closed: str = "",
    payment_method: str = "",
    include_raw: bool = False,
) -> str:
    """Create a new transaction.

    Args:
        status: CANCELLED | CLOSED | PENDING
        source: Transaction source — SHOP or AUTO (default SHOP)
        licensee_number: Optional — associated licensee
        number: Optional custom transaction number (auto-generated if empty)
        name: Optional human-readable transaction name
        active: Whether the transaction is active
        date_created: Optional ISO 8601 creation timestamp
        date_closed: Optional ISO 8601 close timestamp
        payment_method: Optional payment method number
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await transactions.create_transaction(
                status,
                source,
                licensee_number=licensee_number or None,
                number=number or None,
                name=name or None,
                active=active,
                date_created=date_created or None,
                date_closed=date_closed or None,
                payment_method=payment_method or None,
            ),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_transaction(
    transaction_number: str,
    status: str = "",
    active: bool | None = None,
    name: str = "",
    date_closed: str = "",
    payment_method: str = "",
    include_raw: bool = False,
) -> str:
    """Update a transaction's status or properties.

    Args:
        transaction_number: Transaction to update
        status: CANCELLED | CLOSED | PENDING (leave empty to keep current)
        active: Set active state (omit to keep current)
        name: Human-readable name (leave empty to keep current)
        date_closed: ISO 8601 close timestamp (leave empty to keep current)
        payment_method: Payment method number (leave empty to keep current)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await transactions.update_transaction(
                transaction_number,
                status=status or None,
                active=active,
                name=name or None,
                date_closed=date_closed or None,
                payment_method=payment_method or None,
            ),
            "Transaction",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENT METHODS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_payment_methods(filter: str = "", include_raw: bool = False) -> str:
    """List all payment methods configured for the account.

    Args:
        filter: Optional server-side filter expression (e.g. 'active=true')
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await payment_methods.list_payment_methods(
                filter_str=filter or None,
            ),
            "PaymentMethod",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_get_payment_method(
    payment_method_number: str, include_raw: bool = False
) -> str:
    """Get details of a specific payment method.

    Args:
        payment_method_number: Payment method identifier
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await payment_methods.get_payment_method(payment_method_number),
            "PaymentMethod",
            include_raw=include_raw,
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_preview_update_payment_method(
    payment_method_number: str,
    active: bool | None = None,
) -> str:
    """Preview a sensitive payment method update (active state change).

    Returns a diff and a confirmation token. Pass the token to
    netlicensing_update_payment_method within 5 minutes to apply.

    Args:
        payment_method_number: Payment method to preview changes for
        active: Proposed new active state (omit to skip)
    """
    try:
        current_resp = await payment_methods.get_payment_method(payment_method_number)
        current = _extract_props(current_resp)
        diff: list[dict] = []
        if active is not None:
            diff.append(
                {
                    "field": "active",
                    "from": current.get("active"),
                    "to": str(active).lower(),
                }
            )
        return _json(
            safety.make_update_preview("update_payment_method", payment_method_number, diff)
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_update_payment_method(
    payment_method_number: str,
    active: bool | None = None,
    paypal_subject: str = "",
    confirm_token: str = "",
    include_raw: bool = False,
) -> str:
    """Update a payment method's configuration.

    Changing the active state requires a confirmation token. Call
    netlicensing_preview_update_payment_method first.

    Args:
        payment_method_number: Payment method to update
        active: Enable or disable the payment method
        paypal_subject: PayPal account e-mail address
        confirm_token: Confirmation token (required when active changes)
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        if active is not None:
            if confirm_token:
                safety.validate_and_consume(
                    confirm_token, "update_payment_method", payment_method_number
                )
            else:
                current_resp = await payment_methods.get_payment_method(payment_method_number)
                current = _extract_props(current_resp)
                diff: list[dict] = [
                    {
                        "field": "active",
                        "from": current.get("active"),
                        "to": str(active).lower(),
                    }
                ]
                return _json(
                    safety.make_update_preview("update_payment_method", payment_method_number, diff)
                )

        return _wrap_json(
            await payment_methods.update_payment_method(
                payment_method_number,
                active=active,
                paypal_subject=paypal_subject or None,
            ),
            "PaymentMethod",
            include_raw=include_raw,
        )
    except ValueError as exc:
        return _json({"error": True, "detail": str(exc)})
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def netlicensing_list_licensing_models(include_raw: bool = False) -> str:
    """List all licensing models supported by the NetLicensing service.

    Args:
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await utilities.list_licensing_models(), "LicensingModel", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_list_license_types(include_raw: bool = False) -> str:
    """List all license types supported by the NetLicensing service.

    Args:
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(
            await utilities.list_license_types(), "LicenseType", include_raw=include_raw
        )
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_list_countries(include_raw: bool = False) -> str:
    """List all countries available for VAT and localization settings.

    Args:
        include_raw: When true, include the original NetLicensing API payload under 'raw'
    """
    try:
        return _wrap_json(await utilities.list_countries(), "Country", include_raw=include_raw)
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════════════

from netlicensing_mcp.workflows import customer_health as _customer_health  # noqa: E402


@mcp.tool()
async def netlicensing_get_customer_health(
    licensee_number: str,
    refresh_warning_level: bool = False,
    include_raw: bool = False,
) -> str:
    """Return a normalized health summary for one licensee.

    Combines licensee details, license list, and (optionally) a dry-run
    validation into a single CustomerHealth envelope with per-module rows,
    warnings, and suggested actions. This tool is READ-ONLY — it never
    modifies data or consumes quota.

    Args:
        licensee_number:       Licensee identifier (e.g. 'CUST-ACME').
        refresh_warning_level: When True, runs a dry-run validate_licensee to
                               get live warning levels and quota/session info.
                               Slightly slower but more accurate.
        include_raw:           When True, include the original NetLicensing
                               API payloads under 'raw'.
    """
    try:
        licensee = await licensees.get_licensee(licensee_number)
        licenses_payload = await licenses.list_licenses(licensee_number)
        validation = None
        if refresh_warning_level:
            validation = await licensees.validate_licensee(licensee_number, dry_run=True)
        envelope = _customer_health.build_health(licensee, licenses_payload, validation)
        if include_raw:
            envelope["raw"] = {
                "licensee": licensee,
                "licenses": licenses_payload,
                "validation": validation,
            }
        return _json(envelope)
    except NetLicensingError as exc:
        return _error(exc)


@mcp.tool()
async def netlicensing_explain_validation(
    licensee_number: str,
    product_number: str = "",
    module_parameters: list[dict] | None = None,
    include_raw: bool = False,
) -> str:
    """Run a dry-run validation and return a plain-language explanation.

    Wraps validate_licensee with dryRun=true and translates the result into
    per-module status, explanations, and suggested_actions (renewal tokens,
    top-up flows, force-checkin advice). This tool is READ-ONLY — it never
    consumes floating sessions, quota, or node-lock slots.

    Note: module_parameters currently passes the first entry's fields only
    (single-module shorthand). Full multi-module indexed support is planned
    for a future release (P0.5).

    Args:
        licensee_number:   Licensee identifier (e.g. 'CUST-ACME').
        product_number:    Optional — scope validation to a single product.
        module_parameters: Optional per-module overrides. Each dict may
                           contain: product_module_number, node_secret,
                           session_id, action.
        include_raw:       When True, include the original validation payload
                           under 'raw'.
    """
    from netlicensing_mcp.workflows import validation_explain as _val_explain

    try:
        first = (module_parameters or [{}])[0]
        payload = await licensees.validate_licensee(
            licensee_number,
            product_number=product_number or None,
            product_module_number=first.get("product_module_number"),
            node_secret=first.get("node_secret"),
            session_id=first.get("session_id"),
            action=first.get("action"),
            dry_run=True,
        )
        envelope = _val_explain.explain_validation(payload)
        envelope["licensee_number"] = licensee_number
        if include_raw:
            envelope["raw"] = payload
        return _json(envelope)
    except NetLicensingError as exc:
        return _error(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

register_audit_prompts(mcp)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Health check endpoint must remain unauthenticated for load-balancer probes
        if request.url.path == "/health":
            return await call_next(request)

        # Extract key: prefer dedicated header, fall back to Bearer token
        key = request.headers.get("x-netlicensing-api-key", "").strip()
        if not key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()

        if key:
            token = api_key_ctx.set(key)
            try:
                return await call_next(request)
            finally:
                api_key_ctx.reset(token)

        # Reject unauthenticated requests with a standard 401 + WWW-Authenticate header
        return JSONResponse(
            {
                "error": "NetLicensing API key is required for HTTP transport. "
                "Supply it via the x-netlicensing-api-key header or "
                "Authorization: Bearer <key>."
            },
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="netlicensing-mcp"'},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="NetLicensing MCP Server")
    parser.add_argument(
        "transport",
        nargs="?",
        choices=["http", "stdio"],
        default=None,
        help="Transport mode: 'stdio' (default) or 'http'. "
        "Can also be set via MCP_TRANSPORT env var.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="Enable verbose debug logging (request/response details). "
        "Can also be set via MCP_VERBOSE=true env var.",
    )
    args = parser.parse_args()

    # Resolve transport: CLI arg → env var → default
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio").lower()

    # Resolve verbose: CLI flag → env var → default
    verbose = args.verbose or os.getenv("MCP_VERBOSE", "").lower() in ("1", "true", "yes")

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled — API requests/responses will be logged")

    logger.info("Starting NetLicensing MCP server (transport=%s, verbose=%s)", transport, verbose)

    if transport == "stdio":
        _startup_api_key = os.getenv("NETLICENSING_API_KEY", "")
        _startup_allow_demo = os.getenv("NETLICENSING_ALLOW_DEMO", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if not _startup_api_key and not _startup_allow_demo:
            logger.error(
                "FATAL: No NetLicensing API key configured. "
                "Set NETLICENSING_API_KEY or NETLICENSING_ALLOW_DEMO=true for sandbox access."
            )
            sys.exit(1)
        if _startup_allow_demo and not _startup_api_key:
            logger.warning(
                "⚠️  DEMO MODE ACTIVE — using sandbox demo:demo credentials. "
                "Not suitable for production. "
                "Set NETLICENSING_API_KEY to use real credentials."
            )
        mcp.run(transport="stdio")
    elif transport == "http":
        print(f"Starting MCP server on http://{mcp.settings.host}:{mcp.settings.port}")

        import anyio
        import uvicorn

        async def run_server() -> None:
            app = mcp.streamable_http_app()
            app.add_middleware(ApiKeyMiddleware)
            config = uvicorn.Config(
                app,
                host=mcp.settings.host,
                port=mcp.settings.port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()

        anyio.run(run_server)
    else:
        print(f"Unknown transport: {transport}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
