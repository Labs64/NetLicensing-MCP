"""Shared helpers for MCP tool input/output post-processing."""

from __future__ import annotations

from typing import Any

from netlicensing_mcp.client import NetLicensingError

# Fields that carry large binary/base64 blobs and should be stripped from all
# tool outputs to keep MCP responses concise.  They are intentionally NOT sent
# in create/update requests either — omitting them preserves the existing value
# on the NetLicensing server side.
STRIP_OUTPUT_FIELDS: frozenset[str] = frozenset({"logo"})

# JSON scalar types MCP clients may send for a custom property value.
CustomPropertyValue = str | int | float | bool


def _coerce_form_value(value: CustomPropertyValue) -> str:
    """Stringify *value* for a form-encoded request, matching the convention
    used elsewhere in the tools layer (lowercase ``"true"``/``"false"``)."""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def merge_custom_properties(
    data: dict[str, str], custom_properties: dict[str, CustomPropertyValue] | None
) -> None:
    """Merge *custom_properties* into the request payload *data* in place.

    Raises ``NetLicensingError`` instead of silently overwriting a reserved
    field already populated from an explicit named argument (e.g.
    ``productNumber``, ``licensingModel``). Values are coerced to ``str``
    since requests are form-encoded.
    """
    if not custom_properties:
        return
    conflicts = sorted(set(custom_properties) & set(data))
    if conflicts:
        raise NetLicensingError(
            400,
            f"custom_properties conflicts with reserved field(s): {', '.join(conflicts)}",
        )
    data.update({k: _coerce_form_value(v) for k, v in custom_properties.items()})


def first_item_property(response: dict[str, Any], name: str) -> str | None:
    """Return property *name* of the first item in a NetLicensing response."""
    items = response.get("items", {}).get("item", [])
    if not items or not isinstance(items[0], dict):
        return None
    for p in items[0].get("property", []):
        if isinstance(p, dict) and p.get("name") == name:
            value = p.get("value")
            return str(value) if value is not None else None
    return None


def scoped_filter(
    scope_key: str,
    scope_value: str,
    filter_str: str | None = None,
    page: int | None = None,
    items_per_page: int | None = None,
) -> dict[str, str]:
    """Build the ``filter`` query parameter for a list scoped to a parent entity.

    The NetLicensing list endpoints ignore a bare ``?productNumber=X`` query
    parameter and return the whole vendor account. The parent scope only takes
    effect inside the single ``filter`` parameter, as ``;``-separated
    ``key=value`` pairs (e.g. ``filter=productNumber=P001;page=0;items=100``).

    Raises ``NetLicensingError(400)`` when the scope value could break out of
    its pair, or when *filter_str* tries to set the scope key itself, so a
    caller can never widen the scope it asked for.
    """
    if not scope_value or any(ch in scope_value for ch in ";="):
        raise NetLicensingError(400, f"Invalid {scope_key}: must be non-empty without ';' or '='")
    parts = [f"{scope_key}={scope_value}"]
    if page is not None:
        parts.append(f"page={page}")
    if items_per_page is not None:
        parts.append(f"items={items_per_page}")
    if filter_str:
        keys = {p.split("=", 1)[0].strip() for p in filter_str.split(";") if p.strip()}
        if scope_key in keys:
            raise NetLicensingError(
                400, f"filter must not set {scope_key}; it is taken from the tool argument"
            )
        parts.append(filter_str)
    return {"filter": ";".join(parts)}


def strip_output_fields(data: Any, fields: frozenset[str] = STRIP_OUTPUT_FIELDS) -> Any:
    """Recursively remove large/binary fields from a NetLicensing API response.

    Handles two common patterns:
    - Plain dict keys  (e.g. ``{"logo": "data:image/png;base64,...", ...}``)
    - NetLicensing *property* arrays  (``[{"name": "logo", "value": "..."}, ...]``)

    Any field whose name appears in *fields* is dropped at every nesting level.
    """
    if isinstance(data, list):
        return [strip_output_fields(item, fields) for item in data]
    if isinstance(data, dict):
        # 1. Drop matching top-level keys and recurse into kept values.
        result = {k: strip_output_fields(v, fields) for k, v in data.items() if k not in fields}
        # 2. If this dict contains a NetLicensing "property" list, also filter
        #    entries whose "name" field matches.
        if "property" in result and isinstance(result["property"], list):
            result["property"] = [
                p
                for p in result["property"]
                if not (isinstance(p, dict) and p.get("name") in fields)
            ]
        return result
    return data
