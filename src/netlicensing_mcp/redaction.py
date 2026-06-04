"""Redaction layer for NetLicensing MCP (P0.3).

Masks sensitive field values in API responses and verbose log output so that
secrets are never echoed back to LLM clients or written to log files in
plaintext.

Default redact set: ``apiKey``, ``licenseeSecret``, ``nodeSecret``,
``password``, ``secret``.  Extendable at runtime via ``MCP_REDACT_FIELDS``
(comma-separated list of additional field names).

Handles two patterns used throughout the NetLicensing REST API:

* Plain dict keys — ``{"licenseeSecret": "s3cret", ...}``
* NetLicensing property arrays — ``{"property": [{"name": "licenseeSecret",
  "value": "s3cret"}, ...]}``

Usage::

    from netlicensing_mcp.redaction import redact, tag_one_time_display, redact_token_read

    safe = redact(api_response)
    create_resp = tag_one_time_display(create_api_token_response)
    read_resp = redact_token_read(list_tokens_response)
"""

from __future__ import annotations

import os
from typing import Any

# ── Default sensitive field names ────────────────────────────────────────────

#: Fields redacted in all tool outputs by default.
DEFAULT_REDACT: frozenset[str] = frozenset(
    {"apiKey", "licenseeSecret", "nodeSecret", "password", "secret"}
)

_ONE_TIME_WARNING: str = (
    "This credential is shown ONCE. "
    "Store it securely — it cannot be retrieved in full again via this API."
)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _extra_fields() -> frozenset[str]:
    """Return additional redact fields from the ``MCP_REDACT_FIELDS`` env var.

    The env var accepts a comma-separated list of field names, e.g.
    ``MCP_REDACT_FIELDS=ssn,phone``.
    """
    raw = os.getenv("MCP_REDACT_FIELDS", "")
    if not raw:
        return frozenset()
    return frozenset(f.strip() for f in raw.split(",") if f.strip())


def _effective_fields(fields: frozenset[str]) -> frozenset[str]:
    """Merge caller-supplied fields with runtime extensions."""
    return fields | _extra_fields()


def _mask(value: str) -> str:
    """Partially mask *value*, keeping the first 3 and last 4 characters.

    Examples::

        _mask("s3cret")          → "****"
        _mask("apikey-abc12345") → "api****2345"
    """
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}****{value[-4:]}"


# ── Public API ────────────────────────────────────────────────────────────────


def redact(
    payload: Any,
    fields: frozenset[str] = DEFAULT_REDACT,
    mode: str = "mask",
) -> Any:
    """Recursively redact sensitive fields from *payload*.

    Handles two common patterns in NetLicensing API responses:

    * Plain dict keys: ``{"licenseeSecret": "s3cret"}`` → key is masked.
    * Property arrays: ``{"property": [{"name": "licenseeSecret",
      "value": "s3cret"}]}`` → the matching entry's ``value`` is masked.

    The effective redact set is ``fields`` **union** any names supplied via
    the ``MCP_REDACT_FIELDS`` environment variable.

    Args:
        payload: The response object to sanitise (dict, list, or scalar).
        fields:  Field names whose values should be redacted.
                 Defaults to :data:`DEFAULT_REDACT`.
        mode:    ``"mask"`` (default) — replace the value with a partial mask
                 that preserves first/last chars for recognisability.
                 ``"remove"`` — drop the field key entirely.

    Returns:
        A new object of the same type as *payload* with sensitive values
        replaced.  Scalars are returned unchanged.
    """
    effective = _effective_fields(fields)
    return _redact_inner(payload, effective, mode)


def _redact_inner(payload: Any, fields: frozenset[str], mode: str) -> Any:
    if isinstance(payload, list):
        return [_redact_inner(item, fields, mode) for item in payload]
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for k, v in payload.items():
            if k in fields:
                # Sensitive plain-dict key.
                if mode != "remove":
                    result[k] = _mask(str(v)) if isinstance(v, str) else "****"
                # else: drop the key entirely (mode == "remove")
            elif k == "property" and isinstance(v, list):
                # NetLicensing property-array pattern.
                result[k] = [_redact_property(p, fields, mode) for p in v]
            else:
                result[k] = _redact_inner(v, fields, mode)
        return result
    return payload


def _redact_property(prop: Any, fields: frozenset[str], mode: str) -> Any:
    """Redact a single ``{"name": ..., "value": ...}`` property entry."""
    if not isinstance(prop, dict):
        return prop
    name = prop.get("name", "")
    if name in fields:
        if mode == "remove":
            # Drop the value key but keep name/other meta.
            return {k: v for k, v in prop.items() if k != "value"}
        return {**prop, "value": _mask(str(prop.get("value", "")))}
    return prop


# ── One-time-display tagging (create_api_token / create_shop_token) ──────────


def tag_one_time_display(response: Any) -> Any:
    """Tag a *create* token response as one-time-display.

    Adds ``"shown_once": true`` and a ``"_warning"`` string to the top-level
    response dict so that LLM clients understand this is the only chance to
    see the credential in full.

    The raw credential value is preserved in the returned dict (callers should
    then pass the result through normal :func:`redact` so DEFAULT_REDACT fields
    are masked).  Subsequent :func:`redact_token_read` calls on *get/list*
    paths will mask the credential.

    Args:
        response: The raw dict returned by ``create_api_token`` or
                  ``create_shop_token``.

    Returns:
        A new dict with ``shown_once`` and ``_warning`` injected, or the
        original object unchanged if it is not a dict.
    """
    if not isinstance(response, dict):
        return response
    return {
        **response,
        "shown_once": True,
        "_warning": _ONE_TIME_WARNING,
    }


# ── Token read-path masking (get_token / list_tokens) ────────────────────────


def redact_token_read(response: Any) -> Any:
    """Apply extra masking for the *get_token* / *list_tokens* read paths.

    For **APIKEY** tokens the ``number`` property IS the API key value — it
    must be masked on read paths (it was shown once at creation time).

    For **SHOP** tokens the ``shopURL`` property contains a one-time checkout
    URL that should similarly be masked after the initial create response.

    After token-specific masking, :func:`redact` is applied for the standard
    DEFAULT_REDACT fields.

    Args:
        response: Raw dict from ``get_token`` or ``list_tokens``.

    Returns:
        A new dict with APIKEY ``number`` / SHOP ``shopURL`` masked, plus all
        DEFAULT_REDACT fields masked.
    """
    if not isinstance(response, dict):
        return redact(response)

    items_obj = response.get("items", {})
    if not isinstance(items_obj, dict):
        return redact(response)

    item_list = items_obj.get("item", [])
    if not isinstance(item_list, list):
        return redact(response)

    new_items: list[Any] = []
    for item in item_list:
        if not isinstance(item, dict):
            new_items.append(item)
            continue

        props = item.get("property", [])
        if not isinstance(props, list):
            new_items.append(item)
            continue

        # Determine token type from properties.
        token_type = ""
        for p in props:
            if isinstance(p, dict) and p.get("name") == "tokenType":
                token_type = p.get("value", "")
                break

        # Fields requiring extra masking on reads.
        extra_mask: set[str] = set()
        if token_type == "APIKEY":
            extra_mask.add("number")
        if token_type == "SHOP":
            extra_mask.add("shopURL")

        if extra_mask:
            new_props = []
            for p in props:
                if isinstance(p, dict) and p.get("name") in extra_mask:
                    new_props.append({**p, "value": _mask(str(p.get("value", "")))})
                else:
                    new_props.append(p)
            new_items.append({**item, "property": new_props})
        else:
            new_items.append(item)

    masked_response = {
        **response,
        "items": {**items_obj, "item": new_items},
    }
    # Apply standard DEFAULT_REDACT on top.
    return redact(masked_response)
