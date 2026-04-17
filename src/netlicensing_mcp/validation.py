"""
Input validation helpers for NetLicensing MCP tools.

These validators run at the tool boundary (before any HTTP call) so invalid
input is rejected with a short, actionable message instead of a raw 4xx from
the upstream API. Each validator returns the trimmed/normalized value on
success and raises :class:`ValidationError` on failure.

Validators are permissive by design: they catch obvious mistakes (wrong enum
value, malformed e-mail, non-ISO date) without duplicating NetLicensing's
business rules.
"""

from __future__ import annotations

import re
from datetime import datetime

# ── Exception ────────────────────────────────────────────────────────────────


class ValidationError(ValueError):
    """Raised when a tool argument fails client-side validation."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Invalid {field}: {message}")


# ── Enum reference data (kept in sync with server.py instructions) ───────────

LICENSE_TYPES: frozenset[str] = frozenset({"FEATURE", "TIMEVOLUME", "FLOATING", "QUANTITY"})

LICENSING_MODELS: frozenset[str] = frozenset(
    {
        "TryAndBuy",
        "Subscription",
        "Rental",
        "Floating",
        "MultiFeature",
        "PayPerUse",
        "PricingTable",
        "Quota",
        "NodeLocked",
    }
)

TIME_VOLUME_PERIODS: frozenset[str] = frozenset({"DAY", "WEEK", "MONTH", "YEAR"})

VAT_MODES: frozenset[str] = frozenset({"GROSS", "NET"})

LICENSEE_SECRET_MODES: frozenset[str] = frozenset({"DISABLED", "PREDEFINED", "CLIENT"})

NODE_SECRET_MODES: frozenset[str] = frozenset({"PREDEFINED", "CLIENT"})

TRANSACTION_STATUSES: frozenset[str] = frozenset({"CANCELLED", "CLOSED", "PENDING"})

TRANSACTION_SOURCES: frozenset[str] = frozenset({"SHOP", "AUTO"})

API_KEY_ROLES: frozenset[str] = frozenset(
    {
        "ROLE_APIKEY_LICENSEE",
        "ROLE_APIKEY_ANALYTICS",
        "ROLE_APIKEY_OPERATION",
        "ROLE_APIKEY_MAINTENANCE",
        "ROLE_APIKEY_ADMIN",
    }
)

FLOATING_ACTIONS: frozenset[str] = frozenset({"checkOut", "checkIn"})


# ── Primitives ───────────────────────────────────────────────────────────────

# Per NetLicensing: identifier must be non-empty, printable, no whitespace
# or forward slashes (which would break URL paths).
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")

# RFC 5322-lite: covers the overwhelming majority of real addresses.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def identifier(value: str, field: str) -> str:
    """Validate a NetLicensing resource identifier (product_number, etc.)."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValidationError(field, "must not be empty")
    if not _IDENTIFIER_RE.match(stripped):
        raise ValidationError(
            field,
            "must be 1-64 chars, alphanumeric with '_', '.', or '-' (no whitespace or slashes)",
        )
    return stripped


def email(value: str, field: str) -> str:
    """Validate an e-mail address."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    stripped = value.strip()
    if not _EMAIL_RE.match(stripped):
        raise ValidationError(field, "is not a valid e-mail address")
    return stripped


def currency(value: str, field: str = "currency") -> str:
    """Validate an ISO 4217 currency code (3 uppercase letters)."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    stripped = value.strip().upper()
    if not _CURRENCY_RE.match(stripped):
        raise ValidationError(field, "must be a 3-letter ISO 4217 currency code (e.g. EUR, USD)")
    return stripped


def iso_datetime(value: str, field: str) -> str:
    """Validate an ISO-8601 datetime string; returns it unchanged."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    stripped = value.strip()
    try:
        # Accept "Z" as an alias for "+00:00".
        datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(field, f"is not a valid ISO-8601 datetime ({exc})") from exc
    return stripped


def positive_int(value: int, field: str, *, allow_zero: bool = False) -> int:
    """Validate a positive integer (or >= 0 when allow_zero=True)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(field, "must be an integer")
    if allow_zero and value < 0:
        raise ValidationError(field, "must be >= 0")
    if not allow_zero and value <= 0:
        raise ValidationError(field, "must be > 0")
    return value


def non_negative_number(value: float | int, field: str) -> float:
    """Validate a non-negative price/amount."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(field, "must be a number")
    if value < 0:
        raise ValidationError(field, "must be >= 0")
    return float(value)


def one_of(value: str, allowed: frozenset[str], field: str) -> str:
    """Validate that *value* is in *allowed* (case-sensitive)."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    stripped = value.strip()
    if stripped not in allowed:
        allowed_sorted = ", ".join(sorted(allowed))
        raise ValidationError(field, f"must be one of: {allowed_sorted}")
    return stripped


# ── Convenience wrappers ────────────────────────────────────────────────────


def license_type(value: str, field: str = "license_type") -> str:
    return one_of(value, LICENSE_TYPES, field)


def licensing_model(value: str, field: str = "licensing_model") -> str:
    return one_of(value, LICENSING_MODELS, field)


def time_volume_period(value: str, field: str = "time_volume_period") -> str:
    return one_of(value, TIME_VOLUME_PERIODS, field)


def vat_mode(value: str, field: str = "vat_mode") -> str:
    return one_of(value, VAT_MODES, field)


def licensee_secret_mode(value: str, field: str = "licensee_secret_mode") -> str:
    return one_of(value, LICENSEE_SECRET_MODES, field)


def node_secret_mode(value: str, field: str = "node_secret_mode") -> str:
    return one_of(value, NODE_SECRET_MODES, field)


def transaction_status(value: str, field: str = "status") -> str:
    return one_of(value, TRANSACTION_STATUSES, field)


def transaction_source(value: str, field: str = "source") -> str:
    return one_of(value, TRANSACTION_SOURCES, field)


def api_key_role(value: str, field: str = "api_key_role") -> str:
    return one_of(value, API_KEY_ROLES, field)


def floating_action(value: str, field: str = "action") -> str:
    return one_of(value, FLOATING_ACTIONS, field)
