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

Contract:

* **List tools and validate always return the list envelope**
  ``{"type": "list", "kind": "...", "count": N, "items": [...]}`` — also for
  zero or one item (they call :func:`wrap` with ``as_list=True``).
* **get / create / update return a single envelope** — a flat dict.

Nested ``list`` groups inside an item (e.g. the per-session data Core returns
for a Floating ``ProductModuleValidation``) are kept, flattened the same way,
under their ``name``.  Upstream ``infos`` of type ERROR / WARNING (plus INFO
for validate) are copied into ``warnings`` so callers see API messages without
``include_raw``.

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


def _flatten_list_group(group: dict) -> dict[str, Any]:
    """Flatten a nested NetLicensing ``list`` group (``{"name", "property", "list"}``)."""
    out: dict[str, Any] = dict(_props_to_dict(group))
    _merge_nested_lists(out, group)
    return out


def _merge_nested_lists(target: dict[str, Any], item: dict) -> None:
    """Copy nested ``list`` groups of *item* into *target*, keyed by group name.

    A name that occurs once maps to a dict; repeated names map to a list of
    dicts. Existing keys in *target* (entity properties) are never overwritten.
    """
    groups = item.get("list", [])
    if not isinstance(groups, list):
        return
    collected: dict[str, list[dict[str, Any]]] = {}
    for g in groups:
        if isinstance(g, dict):
            collected.setdefault(str(g.get("name", "")), []).append(_flatten_list_group(g))
    for name, values in collected.items():
        key = name or "list"
        if key in target:
            continue
        target[key] = values[0] if len(values) == 1 else values


#: ``infos`` types copied into ``warnings`` by default.
DEFAULT_WARN_INFO_TYPES: tuple[str, ...] = ("ERROR", "WARNING")


def _info_warnings(
    meta: dict[str, Any], types: tuple[str, ...] = DEFAULT_WARN_INFO_TYPES
) -> list[str]:
    """Return ``infos`` messages of the given *types* from an upstream response."""
    infos = meta.get("infos")
    info_list = infos.get("info", []) if isinstance(infos, dict) else []
    if not isinstance(info_list, list):
        return []
    return [
        str(i.get("value", ""))
        for i in info_list
        if isinstance(i, dict) and str(i.get("type", "")).upper() in types and i.get("value")
    ]


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
    # Keep nested groups (e.g. Floating session data on a validation result).
    _merge_nested_lists(envelope, item)

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
    as_list: bool = False,
    warn_info_types: tuple[str, ...] = DEFAULT_WARN_INFO_TYPES,
) -> dict[str, Any]:
    """Normalise a NetLicensing API response into a flat envelope with console_url.

    Handles both single-entity responses (get / create / update — exactly one
    item in ``items.item``) and list responses (zero or more items).  List
    tools and validate pass ``as_list=True`` so the list envelope is returned
    for any item count, including 0 and 1.

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
        as_list:           Always return the list envelope, even for one item.
        warn_info_types:   Upstream ``infos`` types copied into ``warnings``.
                           Validate adds ``INFO``: Core reports a refused
                           checkOut (``NoFreeSessions``) or node binding
                           (``NoFreeNodes``) as INFO.
    """
    items_obj = entity.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    if not isinstance(item_list, list):
        item_list = []

    # Preserve upstream top-level metadata (e.g. ``signature``, ``ttl`` on
    # validate-licensee responses; ``infos`` on certain create responses) so
    # that callers don't need ``include_raw=True`` just to read non-entity
    # fields. ``items`` itself is consumed below.
    meta: dict[str, Any] = {k: v for k, v in entity.items() if k != "items"}

    # Determine effective kind from first item when not explicitly supplied.
    effective_kind = kind
    if not effective_kind and item_list:
        effective_kind = item_list[0].get("type", "") if isinstance(item_list[0], dict) else ""

    if len(item_list) == 1 and not as_list:
        # Single entity (get / create / update path).
        envelope = _wrap_item(
            item_list[0],
            summary=summary,
            suggested_actions=suggested_actions,
        )
        # Override kind from caller hint if the item has no type.
        if not envelope.get("type") and effective_kind:
            envelope["type"] = effective_kind
        # Merge upstream meta without clobbering envelope-defined fields.
        for k, v in meta.items():
            envelope.setdefault(k, v)
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
        for k, v in meta.items():
            envelope.setdefault(k, v)

    for msg in _info_warnings(meta, warn_info_types):
        if msg not in envelope["warnings"]:
            envelope["warnings"].append(msg)

    if raw is not None:
        envelope["raw"] = raw

    return envelope
