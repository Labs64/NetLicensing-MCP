"""Shared helpers for MCP tool input/output post-processing."""

from __future__ import annotations

from typing import Any

from netlicensing_mcp.client import NetLicensingError

# Fields that carry large binary/base64 blobs and should be stripped from all
# tool outputs to keep MCP responses concise.  They are intentionally NOT sent
# in create/update requests either — omitting them preserves the existing value
# on the NetLicensing server side.
STRIP_OUTPUT_FIELDS: frozenset[str] = frozenset({"logo"})


def merge_custom_properties(data: dict[str, str], custom_properties: dict[str, str] | None) -> None:
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
    data.update({k: str(v) for k, v in custom_properties.items()})


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
