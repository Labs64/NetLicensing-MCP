"""Normalized response envelope for NetLicensing MCP tools (P0.6).

Every entity-returning tool wraps its raw NetLicensing API response through
:func:`wrap` before serialising it.  The result is a flat, human-readable
envelope that:

* Promotes entity properties to the top level of the returned dict.
* Converts the ``active`` property string ("true"/"false") to a JSON bool.
* Injects a ``console_url`` pointing at the entity in the NetLicensing
  Console UI, derived from ``MCP_CONSOLE_BASE_URL`` (default
  ``https://ui.netlicensing.io/#``).
* Adds ``warnings`` and ``suggested_actions`` fields for downstream callers.
* Optionally includes the original raw NetLicensing payload under ``"raw"``
  when ``include_raw=True`` is requested at the tool level.

Single-item responses (get / create / update) return a flat dict; list
responses return ``{"type": "list", "kind": "...", "count": N, "items": [...]}``.

Usage::

    from netlicensing_mcp.responses import wrap

    raw = await licensees.get_licensee("I001")
    envelope = wrap(raw, "Licensee")
    # → {"type": "Licensee", "number": "I001", "active": True,
    #    "console_url": "https://ui.netlicensing.io/#/licensees/I001", ...}
"""

from __future__ import annotations

import os
from typing import Any

# ── Console URL mapping ───────────────────────────────────────────────────────

_DEFAULT_CONSOLE_BASE = "https://ui.netlicensing.io/#"

#: Maps NetLicensing entity ``type`` strings to Console URL path segments.
ENTITY_PATH: dict[str, str] = {
    "Product": "products",
    "ProductModule": "modules",
    "LicenseTemplate": "license-templates",
    "Licensee": "licensees",
    "License": "licenses",
    "Bundle": "bundles",
    "Transaction": "transactions",
    "Token": "tokens",
    "PaymentMethod": "payment-methods",
}


def _console_base() -> str:
    """Return the Console base URL, stripped of trailing slashes."""
    return os.getenv("MCP_CONSOLE_BASE_URL", _DEFAULT_CONSOLE_BASE).rstrip("/")


def console_url(kind: str, number: str) -> str | None:
    """Build a Console deep link for *kind* / *number*.

    Returns ``None`` when the entity kind has no known URL path or *number* is
    empty.

    Args:
        kind:   Entity type string, e.g. ``"Licensee"``.
        number: Entity identifier, e.g. ``"CUST-ACME"``.
    """
    path = ENTITY_PATH.get(kind)
    if not path or not number:
        return None
    return f"{_console_base()}/{path}/{number}"


# ── Internal helpers ──────────────────────────────────────────────────────────


def _props_to_dict(item: dict) -> dict[str, str]:
    """Flatten a NetLicensing ``property`` list into a plain ``{name: value}`` dict."""
    return {
        p["name"]: p["value"]
        for p in item.get("property", [])
        if isinstance(p, dict) and "name" in p and "value" in p
    }


def _wrap_item(
    item: dict,
    *,
    summary: str | None = None,
    suggested_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Normalise a single NetLicensing API item into the response envelope.

    All entity properties are promoted to the top level as plain key/value
    pairs.  ``active`` is converted from the string ``"true"`` / ``"false"``
    to a Python bool.  A ``console_url`` is added when the entity kind and
    number are both known.
    """
    kind: str = item.get("type", "")
    props: dict[str, str] = _props_to_dict(item)

    # Build the envelope starting from all entity properties.
    envelope: dict[str, Any] = dict(props)

    # Overwrite/inject well-known typed fields.
    envelope["type"] = kind

    # Convert active string → bool.
    active_str = props.get("active", "")
    if active_str.lower() == "true":
        envelope["active"] = True
    elif active_str.lower() == "false":
        envelope["active"] = False

    # Inject Console deep link.
    number = props.get("number", "")
    url = console_url(kind, number)
    if url:
        envelope["console_url"] = url

    # Envelope meta fields.
    envelope["warnings"] = []
    envelope["suggested_actions"] = suggested_actions or []
    if summary is not None:
        envelope["summary"] = summary

    return envelope


# ── Public API ────────────────────────────────────────────────────────────────


def wrap(
    entity: dict,
    kind: str | None = None,
    *,
    summary: str | None = None,
    suggested_actions: list[str] | None = None,
    raw: dict | None = None,
) -> dict[str, Any]:
    """Normalise a NetLicensing API response into a flat envelope with console_url.

    Handles both single-entity responses (get / create / update — exactly one
    item in ``items.item``) and list responses (zero or more items).

    * **Single-item response** — returns a flat dict with all entity properties
      at the top level, plus ``console_url``, ``warnings``, and
      ``suggested_actions``.
    * **List response** — returns::

          {
              "type": "list",
              "kind": "<EntityKind>",
              "count": N,
              "items": [<envelope>, ...],
              "warnings": [],
              "suggested_actions": []
          }

    When *raw* is not ``None`` its value is attached under the ``"raw"`` key.
    Pass the original (stripped) response as *raw* when ``include_raw=True`` is
    requested at the tool level so callers can access the upstream payload.

    Args:
        entity:            The NetLicensing API response dict (after
                           ``strip_output_fields``).
        kind:              Optional entity type hint used as the ``kind`` field
                           in list envelopes and as fallback when ``type`` is
                           absent from items.
        summary:           Human-readable one-line summary injected into the
                           envelope.
        suggested_actions: List of suggested follow-up actions.
        raw:               When not ``None``, attached as ``envelope["raw"]``.
    """
    items_obj = entity.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    if not isinstance(item_list, list):
        item_list = []

    # Determine effective kind from first item when not explicitly supplied.
    effective_kind = kind
    if not effective_kind and item_list:
        effective_kind = item_list[0].get("type", "") if isinstance(item_list[0], dict) else ""

    if len(item_list) == 1:
        # Single entity (get / create / update path).
        envelope = _wrap_item(
            item_list[0],
            summary=summary,
            suggested_actions=suggested_actions,
        )
        # Override kind from caller hint if the item has no type.
        if not envelope.get("type") and effective_kind:
            envelope["type"] = effective_kind
    else:
        # List or empty response.
        wrapped_items = [_wrap_item(item) for item in item_list if isinstance(item, dict)]
        envelope = {
            "type": "list",
            "kind": effective_kind or "",
            "count": len(wrapped_items),
            "items": wrapped_items,
            "warnings": [],
            "suggested_actions": suggested_actions or [],
        }
        if summary is not None:
            envelope["summary"] = summary

    if raw is not None:
        envelope["raw"] = raw

    return envelope
