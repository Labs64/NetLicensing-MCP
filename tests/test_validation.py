"""Tests for the input validation helpers."""

from __future__ import annotations

import pytest

from netlicensing_mcp import validation as v
from netlicensing_mcp.validation import ValidationError


# ── identifier ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    ["P001", "product-1", "module_42", "A.b.c", "X" * 64],
)
def test_identifier_accepts_valid(value: str) -> None:
    assert v.identifier(value, "field") == value


@pytest.mark.parametrize(
    "value",
    ["", " ", "has space", "slash/inside", "with\nnewline", "X" * 65, "-leadingdash"],
)
def test_identifier_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        v.identifier(value, "field")


def test_identifier_trims_whitespace() -> None:
    assert v.identifier("  P001  ", "field") == "P001"


# ── email ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["a@b.co", "alice.smith+tag@example.com"])
def test_email_accepts_valid(value: str) -> None:
    assert v.email(value, "paypal_subject") == value


@pytest.mark.parametrize("value", ["no-at-sign", "x@y", "a @b.c", "@b.c", "a@"])
def test_email_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        v.email(value, "paypal_subject")


# ── currency ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["EUR", "USD", "gbp"])
def test_currency_accepts_valid(value: str) -> None:
    assert v.currency(value) == value.upper()


@pytest.mark.parametrize("value", ["E", "EUROS", "123", ""])
def test_currency_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        v.currency(value)


# ── iso_datetime ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "2026-04-17",
        "2026-04-17T12:00:00",
        "2026-04-17T12:00:00+02:00",
        "2026-04-17T12:00:00Z",
    ],
)
def test_iso_datetime_accepts_valid(value: str) -> None:
    assert v.iso_datetime(value, "start_date") == value


@pytest.mark.parametrize("value", ["yesterday", "17/04/2026", "not-a-date"])
def test_iso_datetime_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        v.iso_datetime(value, "start_date")


# ── positive_int ────────────────────────────────────────────────────────────


def test_positive_int_accepts_positive() -> None:
    assert v.positive_int(5, "qty") == 5


def test_positive_int_allow_zero() -> None:
    assert v.positive_int(0, "qty", allow_zero=True) == 0


def test_positive_int_rejects_zero_by_default() -> None:
    with pytest.raises(ValidationError):
        v.positive_int(0, "qty")


def test_positive_int_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        v.positive_int(-1, "qty", allow_zero=True)


def test_positive_int_rejects_bool() -> None:
    # booleans subclass int — make sure we don't silently accept True/False.
    with pytest.raises(ValidationError):
        v.positive_int(True, "qty")  # type: ignore[arg-type]


# ── non_negative_number ─────────────────────────────────────────────────────


def test_non_negative_number_accepts_zero_and_float() -> None:
    assert v.non_negative_number(0, "price") == 0.0
    assert v.non_negative_number(9.99, "price") == 9.99


def test_non_negative_number_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        v.non_negative_number(-1, "price")


# ── enum wrappers ───────────────────────────────────────────────────────────


def test_license_type_accepts_valid() -> None:
    assert v.license_type("FEATURE") == "FEATURE"


def test_license_type_rejects_invalid() -> None:
    with pytest.raises(ValidationError) as exc:
        v.license_type("feature")  # case-sensitive
    assert "FEATURE" in str(exc.value)


def test_licensing_model_accepts_valid() -> None:
    assert v.licensing_model("Subscription") == "Subscription"


def test_licensing_model_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        v.licensing_model("PerpetualLicense")


def test_api_key_role_accepts_valid() -> None:
    assert v.api_key_role("ROLE_APIKEY_ADMIN") == "ROLE_APIKEY_ADMIN"


def test_floating_action_accepts_valid() -> None:
    assert v.floating_action("checkOut") == "checkOut"
    assert v.floating_action("checkIn") == "checkIn"


def test_transaction_status_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        v.transaction_status("OPEN")


# ── Error shape ─────────────────────────────────────────────────────────────


def test_validation_error_exposes_field_and_message() -> None:
    exc = ValidationError("product_number", "must not be empty")
    assert exc.field == "product_number"
    assert exc.message == "must not be empty"
    assert "product_number" in str(exc)
