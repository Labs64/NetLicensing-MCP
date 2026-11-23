"""Shared helpers for MCP tool input/output post-processing."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from netlicensing_mcp.client import ClientValidationError

# Fields that carry large binary/base64 blobs and should be stripped from all
# tool outputs to keep MCP responses concise.  They are intentionally NOT sent
# in create/update requests either — omitting them preserves the existing value
# on the NetLicensing server side.
STRIP_OUTPUT_FIELDS: frozenset[str] = frozenset({"logo"})

# JSON scalar types MCP clients may send for a custom property value.
CustomPropertyValue = str | int | float | bool


# Allowed values of enumerated arguments, checked before any request is sent.
LICENSE_TYPES = ("FEATURE", "TIMEVOLUME", "FLOATING", "QUANTITY")
TRANSACTION_STATUSES = ("CANCELLED", "CLOSED", "PENDING")
TIME_VOLUME_PERIODS = ("DAY", "WEEK", "MONTH", "YEAR")
LICENSING_MODELS = (
    "Rental",
    "TryAndBuy",
    "Subscription",
    "Floating",
    "MultiFeature",
    "PayPerUse",
    "PricingTable",
    "Quota",
    "NodeLocked",
    "Discount",
)
TRANSACTION_SOURCES = ("SHOP", "AUTO")
VAT_MODES = ("GROSS", "NET")
LICENSEE_SECRET_MODES = ("DISABLED", "PREDEFINED", "CLIENT")
API_KEY_ROLES = (
    "ROLE_APIKEY_LICENSEE",
    "ROLE_APIKEY_ANALYTICS",
    "ROLE_APIKEY_OPERATION",
    "ROLE_APIKEY_MAINTENANCE",
    "ROLE_APIKEY_ADMIN",
)


def require_one_of(name: str, value: str | None, allowed: tuple[str, ...]) -> None:
    """Raise ``NetLicensingError(400)`` unless *value* is empty or one of *allowed*.

    Empty / ``None`` mean "not given" and pass. The message lists the allowed
    values, so the caller can correct the argument without a round trip.
    """
    if value is None or value == "":
        return
    if value not in allowed:
        raise ClientValidationError(
            f"Invalid {name} {value!r}: allowed values are {', '.join(allowed)}"
        )


# ── Free-text, identifier, currency and URL validation ───────────────────────

#: Form fields that may hold multi-line text (tab / newline allowed).
MULTILINE_FIELDS = frozenset({"description", "licensingInfo"})

#: Characters never allowed in a ``number`` (identifier) field. NetLicensing's
#: documented rule is not published, so this is a deny list of characters that
#: are path/query/markup syntax or whitespace; ``@``, ``.``, ``-``, ``_`` etc. stay valid.
_NUMBER_FORBIDDEN = set("/\\?#%;,=&<>\"'`|{}[]()*!$^~:")

_CURRENCY = re.compile(r"[A-Z]{3}")

#: Currency codes of ISO 4217 that NetLicensing accepts are not published; only
#: the format is checked, so any three-letter code of the right shape passes.


def _is_control(ch: str, allow_whitespace: bool) -> bool:
    if allow_whitespace and ch in "\t\n\r":
        return False
    return ord(ch) < 32 or ord(ch) == 127


def validate_form_data(data: dict[str, str]) -> None:
    """Reject control characters in any form value and bad ``number`` values.

    Runs on every POST/PUT body before the request is sent. The error names the
    field and the rule. Tab and newline are allowed in multi-line text fields only.
    """
    for key, value in data.items():
        if not isinstance(value, str):
            continue
        multiline = key in MULTILINE_FIELDS
        if any(_is_control(ch, multiline) for ch in value):
            where = " (tab and newline are allowed)" if multiline else ""
            raise ClientValidationError(
                f"Invalid {key}: control characters and null bytes are not allowed{where}"
            )
        if key == "price":
            try:
                require_price(float(value))
            except ValueError:
                raise ClientValidationError(f"Invalid price {value!r}: must be a number") from None
        if key == "currency":
            require_currency(value)
        if key == "number" and value:
            bad = sorted({ch for ch in value if ch in _NUMBER_FORBIDDEN or ch.isspace()})
            if bad:
                shown = " ".join(repr(c) if not c.isspace() else "whitespace" for c in bad)
                raise ClientValidationError(
                    f"Invalid number {value!r}: contains {shown}. Use letters, digits and "
                    "'-', '_', '.', '@' (no whitespace, slashes, quotes, brackets, ';' or '=')"
                )


def require_currency(value: str | None) -> None:
    """Raise unless *value* is empty or an ISO 4217-shaped code (three capital letters)."""
    if value is None or value == "":
        return
    if not _CURRENCY.fullmatch(value):
        raise ClientValidationError(
            f"Invalid currency {value!r}: expected an ISO 4217 code such as EUR"
        )


def require_price(value: float | None) -> None:
    """Raise unless *value* is ``None`` or a non-negative number."""
    if value is not None and value < 0:
        raise ClientValidationError(f"Invalid price {value!r}: must be 0 or greater")


def require_redirect_url(name: str, value: str | None) -> None:
    """Raise unless *value* is empty or an ``https://`` URL (``http://`` only for localhost)."""
    if value is None or value == "":
        return
    allowed = f"{name} must be an https:// URL (http:// is allowed only for localhost or 127.0.0.1)"
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ClientValidationError(f"Invalid {name}: whitespace and control characters. {allowed}")
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        raise ClientValidationError(f"Invalid {name}: not a valid URL. {allowed}") from None
    if not host:
        raise ClientValidationError(f"Invalid {name} {value!r}: {allowed}")
    if parts.scheme == "https":
        return
    if parts.scheme == "http" and host in ("localhost", "127.0.0.1"):
        return
    raise ClientValidationError(f"Invalid {name} {value!r}: {allowed}")


def require_plain_text(name: str, value: str | None) -> None:
    """Raise if *value* contains control characters (titles, labels)."""
    if value and any(_is_control(ch, False) for ch in value):
        raise ClientValidationError(f"Invalid {name}: control characters are not allowed")


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
        raise ClientValidationError(
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
        raise ClientValidationError(f"Invalid {scope_key}: must be non-empty without ';' or '='")
    parts = [f"{scope_key}={scope_value}"]
    if page is not None:
        parts.append(f"page={page}")
    if items_per_page is not None:
        parts.append(f"items={items_per_page}")
    if filter_str:
        keys = {p.split("=", 1)[0].strip() for p in filter_str.split(";") if p.strip()}
        if scope_key in keys:
            raise ClientValidationError(
                f"filter must not set {scope_key}; it is taken from the tool argument"
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


def delete_result(
    operation: str, label: str, shown: str, status: int, cascade: bool = False
) -> str:
    """Return the JSON string a successful delete tool sends back.

    *shown* is the target as it may be displayed (masked for token deletes).
    """
    return json.dumps(
        {
            "operation": operation,
            "target": shown,
            "deleted": True,
            "status": status,
            "cascade": cascade,
            "message": f"{label} {shown} deleted (HTTP {status}).",
            "warnings": [],
            "suggested_actions": [],
        },
        indent=2,  # same serializer settings as app._json
    )
