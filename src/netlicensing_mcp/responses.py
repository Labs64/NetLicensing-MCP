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
* List envelopes add the paging data upstream reports (``total``, ``page``,
  ``total_pages``, ``has_more``, ``page_size``, ``next_page_hint``); ``count``
  stays the number of items in this response.

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
    #    "console_url": "https://ui.netlicensing.io/#/customers/I001/edit", ...}
"""

from __future__ import annotations

import json
import os
from typing import Any

# ── Console URL mapping ───────────────────────────────────────────────────────

_DEFAULT_CONSOLE_BASE = "https://ui.netlicensing.io/#"

#: Maps NetLicensing entity ``type`` strings to Console route templates.
#: ``{number}`` is the entity number; other placeholders are parent numbers
#: read from the entity's own properties.  Kinds absent here (LicenseTemplate,
#: Transaction, Token, PaymentMethod) have no direct Console page.
ENTITY_PATH: dict[str, str] = {
    "Product": "products/{number}/edit",
    "ProductModule": "products/{productNumber}/modules/{number}/edit",
    "Licensee": "customers/{number}/edit",
    "License": "customers/{licenseeNumber}/licenses/{number}/edit",
    "Bundle": "bundles/{number}/edit",
}


def _console_base() -> str:
    """Return the Console base URL, stripped of trailing slashes."""
    return os.getenv("MCP_CONSOLE_BASE_URL", _DEFAULT_CONSOLE_BASE).rstrip("/")


def console_url(kind: str, number: str, props: dict[str, str] | None = None) -> str | None:
    """Build a Console deep link for *kind* / *number*.

    Returns ``None`` when the entity kind has no Console page, *number* is
    empty, or a required parent number (e.g. ``productNumber`` for a module)
    is missing from *props*.

    Args:
        kind:   Entity type string, e.g. ``"Licensee"``.
        number: Entity identifier, e.g. ``"CUST-ACME"``.
        props:  Entity properties, used to resolve parent numbers.
    """
    template = ENTITY_PATH.get(kind)
    if not template or not number:
        return None
    values = {**(props or {}), "number": number}
    try:
        path = template.format_map(values)
    except KeyError:
        return None
    if "{" in path or any(not values.get(k) for k in _placeholders(template)):
        return None
    return f"{_console_base()}/{path}"


def _placeholders(template: str) -> list[str]:
    return [seg[1:-1] for seg in template.split("/") if seg.startswith("{")]


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
    url = console_url(kind, number, props)
    if url:
        envelope["console_url"] = url

    # Envelope meta fields.
    envelope["warnings"] = []
    envelope["suggested_actions"] = suggested_actions or []
    if summary is not None:
        envelope["summary"] = summary

    return envelope


# ── Pagination ────────────────────────────────────────────────────────────────

#: Filter keys that select the page (``page`` is 0-based, ``items`` is the
#: page size; default 100, maximum 100 — https://netlicensing.io/wiki/api-conventions).
_PAGING_FILTER_KEYS = frozenset({"page", "items"})


def _int_attr(items_obj: dict, name: str) -> int | None:
    """Return ``items_obj[name]`` as a non-negative int, or ``None``."""
    try:
        value = int(str(items_obj[name]).strip())
    except (KeyError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _bool_attr(items_obj: dict, name: str) -> bool | None:
    """Return ``items_obj[name]`` (``"true"`` / ``"false"``) as a bool, or ``None``."""
    value = str(items_obj.get(name, "")).strip().lower()
    return {"true": True, "false": False}.get(value)


def next_page_filter(user_filter: str, page: int, page_size: int) -> str:
    """Return the ``filter`` value that fetches *page* with *page_size* items.

    Keeps every ``key=value`` pair of *user_filter* except ``page`` / ``items``
    (any case), then appends ``page=<page>;items=<page_size>``.
    """
    parts = [
        p.strip()
        for p in user_filter.split(";")
        if p.strip() and p.split("=", 1)[0].strip().lower() not in _PAGING_FILTER_KEYS
    ]
    parts += [f"page={page}", f"items={page_size}"]
    return ";".join(parts)


def _paging_fields(items_obj: dict, paging_filter: str | None) -> dict[str, Any]:
    """Map the upstream ``items`` paging attributes to list-envelope fields.

    NetLicensing (XSD ``netlicensing-context-2.1.xsd``) sends ``pagenumber``
    (0-based), ``itemsnumber`` (items on this page), ``totalpages``,
    ``totalitems`` and ``hasnext`` as strings; some endpoints send them as
    ``null``.  Only values that are present and parse are reported:

    * ``total`` ← ``totalitems``; ``page`` ← ``pagenumber``;
      ``total_pages`` ← ``totalpages``; ``has_more`` ← ``hasnext``.
    * ``page_size`` ← ``itemsnumber``, only when ``hasnext`` is true: every
      page but the last is full, so its item count is the page size.
    * ``next_page_hint`` only when *paging_filter* is not ``None`` (the tool
      pages through its ``filter`` argument; the value is the caller's
      filter), ``has_more`` is true and ``page`` / ``page_size`` are known.
    """
    fields: dict[str, Any] = {}
    for key, attr in (
        ("total", "totalitems"),
        ("page", "pagenumber"),
        ("total_pages", "totalpages"),
    ):
        value = _int_attr(items_obj, attr)
        if value is not None:
            fields[key] = value
    has_more = _bool_attr(items_obj, "hasnext")
    if has_more is None:
        return fields
    fields["has_more"] = has_more
    if not has_more:
        return fields
    page_size = _int_attr(items_obj, "itemsnumber")
    if not page_size:
        return fields
    fields["page_size"] = page_size
    page = fields.get("page")
    if paging_filter is not None and page is not None:
        nxt = next_page_filter(paging_filter, page + 1, page_size)
        fields["next_page_hint"] = (
            f"More items available: call this tool again with the same other "
            f"arguments and filter={json.dumps(nxt, ensure_ascii=False)} (page is 0-based)."
        )
    return fields


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
    paging_filter: str | None = None,
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
              # paging fields, each only when upstream reports it:
              "total": T, "page": P, "total_pages": TP, "page_size": S,
              "has_more": bool, "next_page_hint": "...",
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
        paging_filter:     The caller's ``filter`` argument (``""`` when empty)
                           for tools that page through ``filter``; enables
                           ``next_page_hint``.  ``None`` (default) for tools
                           without a ``filter`` parameter.

    ``count`` is always the number of items in *this* response; ``total`` and
    the other paging fields come from the upstream ``items`` attributes (see
    :func:`_paging_fields`).
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
            **(_paging_fields(items_obj, paging_filter) if isinstance(items_obj, dict) else {}),
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
