"""Tests for P1.8 customer_health pure synthesiser."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from netlicensing_mcp.workflows.customer_health import build_health

FIXTURES = Path(__file__).parent / "fixtures" / "customer_health"
NOW = datetime(2026, 6, 9, 0, 0, 0, tzinfo=timezone.utc)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def licensee():
    return load("licensee_acme.json")


@pytest.fixture
def licensee_inactive():
    return load("licensee_acme_inactive.json")


@pytest.fixture
def licenses():
    return load("licenses_acme.json")


@pytest.fixture
def empty_licenses():
    return {"items": {"item": []}}


def test_all_green(licensee, licenses):
    validation = load("validate_acme_all_green.json")
    result = build_health(licensee, licenses, validation, now=NOW)
    assert result["overall_status"] == "ok"
    assert result["suggested_actions"] == []
    assert result["warnings"] == []


def test_subscription_near_expiry(licensee, licenses):
    validation = load("validate_acme_near_expiry.json")
    result = build_health(licensee, licenses, validation, now=NOW)
    assert result["overall_status"] == "warning"
    core_module = next(m for m in result["modules"] if m["module_number"] == "M-CORE")
    assert core_module["expires_in_days"] == 14
    assert any("renewal" in a.lower() for a in result["suggested_actions"])


def test_quota_exhausted(licensee, licenses):
    validation = load("validate_acme_quota_exhausted.json")
    result = build_health(licensee, licenses, validation, now=NOW)
    assert result["overall_status"] == "warning"
    api_module = next(m for m in result["modules"] if m["module_number"] == "M-API")
    assert api_module["quota_pct"] == 0.95
    assert api_module["quota_remaining"] == 500
    assert any("top-up" in a.lower() for a in result["suggested_actions"])


def test_floating_saturated(licensee, licenses):
    validation = load("validate_acme_floating_saturated.json")
    result = build_health(licensee, licenses, validation, now=NOW)
    assert result["overall_status"] == "critical"
    float_module = next(m for m in result["modules"] if m["module_number"] == "M-FLOAT")
    assert float_module["active_sessions"] == float_module["max_sessions"]
    assert any("seat" in a.lower() for a in result["suggested_actions"])


def test_inactive_licensee(licensee_inactive, licenses):
    result = build_health(licensee_inactive, licenses, None, now=NOW)
    assert result["active"] is False
    assert any("re-activate" in a.lower() for a in result["suggested_actions"])


def test_no_warning_level_without_refresh(licensee, licenses):
    result = build_health(licensee, licenses, None, now=NOW)
    for m in result["modules"]:
        assert "warning_level" not in m


def test_overall_status_red_dominates_yellow(licensee, licenses):
    # near_expiry has YELLOW on M-CORE; floating_saturated has RED on M-FLOAT.
    # Merge: create a fixture with both.
    mixed_validation = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-CORE"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "true"},
                        {"name": "warningLevel", "value": "YELLOW"},
                        {"name": "expires", "value": "2026-06-23T00:00:00Z"},
                    ],
                },
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-FLOAT"},
                        {"name": "licensingModel", "value": "Floating"},
                        {"name": "valid", "value": "false"},
                        {"name": "warningLevel", "value": "RED"},
                        {"name": "maxSessions", "value": "50"},
                        {"name": "activeSessions", "value": "50"},
                    ],
                },
            ]
        }
    }
    result = build_health(licensee, licenses, mixed_validation, now=NOW)
    assert result["overall_status"] == "critical"


def test_envelope_has_console_url(licensee, licenses):
    result = build_health(licensee, licenses, None, now=NOW)
    assert "console_url" in result
    assert "CUST-ACME" in result["console_url"]


def test_licensee_name_present(licensee, licenses):
    result = build_health(licensee, licenses, None, now=NOW)
    assert result["licensee_name"] == "ACME Inc."


def test_include_raw_counts(licensee, licenses):
    validation = load("validate_acme_all_green.json")
    result = build_health(licensee, licenses, validation, now=NOW)
    # build_health itself doesn't attach raw — the tool wrapper does.
    # But counts and type should be correct.
    assert result["type"] == "CustomerHealth"
    assert result["counts"]["total_licenses"] == 3
    assert result["counts"]["active_licenses"] == 3
    assert result["counts"]["inactive_licenses"] == 0
    assert result["counts"]["modules"] == 3


def test_heuristic_critical_expiry(licensee, licenses):
    # No validation; license expires in 3 days → critical via heuristic.
    licenses_expiring_soon = {
        "items": {
            "item": [
                {
                    "type": "License",
                    "property": [
                        {"name": "number", "value": "L-CORE-1"},
                        {"name": "active", "value": "true"},
                        {"name": "licenseeNumber", "value": "CUST-ACME"},
                        {"name": "productModuleNumber", "value": "M-CORE"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "expires", "value": "2026-06-12T00:00:00Z"},
                    ],
                }
            ]
        }
    }
    result = build_health(licensee, licenses_expiring_soon, None, now=NOW)
    assert result["overall_status"] == "critical"


def test_subscription_expired_via_validation(licensee, licenses):
    expired_validation = {
        "items": {
            "item": [
                {
                    "type": "ProductModuleValidation",
                    "property": [
                        {"name": "productModuleNumber", "value": "M-CORE"},
                        {"name": "licensingModel", "value": "Subscription"},
                        {"name": "valid", "value": "false"},
                        {"name": "warningLevel", "value": "RED"},
                        {"name": "expires", "value": "2026-04-01T00:00:00Z"},
                    ],
                }
            ]
        }
    }
    result = build_health(licensee, licenses, expired_validation, now=NOW)
    core = next(m for m in result["modules"] if m["module_number"] == "M-CORE")
    assert core["expires_in_days"] < 0
    assert any("renew" in a.lower() and "expired" in a.lower() for a in result["suggested_actions"])
    assert result["overall_status"] == "critical"
