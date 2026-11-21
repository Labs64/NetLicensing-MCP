"""Pagination hints on list envelopes.

NetLicensing reports paging on the ``items`` element of a list response
(XSD ``netlicensing-context-2.1.xsd``: ``pagenumber``, ``itemsnumber``,
``totalpages``, ``totalitems``, ``hasnext``; all strings). Some endpoints
(``/paymentmethod``, ``/utility/*``) send the keys with ``null`` values.
The list envelope turns them into ``total`` / ``page`` / ``total_pages`` /
``page_size`` / ``has_more`` and, for tools that page through ``filter``,
``next_page_hint``. ``count`` keeps meaning "items in this response".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp import server
from netlicensing_mcp.responses import next_page_filter, wrap

PAGING_KEYS = ("total", "page", "total_pages", "page_size", "has_more", "next_page_hint")


@pytest.fixture(autouse=True)
def _no_demo_mode(monkeypatch):
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)


def _item(kind: str, **props: str) -> dict:
    return {"type": kind, "property": [{"name": k, "value": v} for k, v in props.items()]}


def _page(kind: str, n: int, **meta: str | None) -> dict:
    """A list response with *n* items and the given ``items`` attributes."""
    items = [_item(kind, number=f"{kind[0]}{i}", active="true") for i in range(n)]
    return {"items": {"item": items, **meta}}


# Shapes copied from GET responses of the public demo sandbox (2026-11-21).
FIRST_OF_NINE = {
    "pagenumber": "0",
    "itemsnumber": "2",
    "totalpages": "9",
    "totalitems": "18",
    "hasnext": "true",
}
LAST_PAGE = {
    "pagenumber": "3",
    "itemsnumber": "3",
    "totalpages": "4",
    "totalitems": "18",
    "hasnext": "false",
}
NULL_META = {
    "pagenumber": None,
    "itemsnumber": None,
    "totalpages": None,
    "totalitems": None,
    "hasnext": None,
}


# ── wrap(): metadata → envelope fields ───────────────────────────────────────


def test_has_more_true_reports_all_known_fields():
    env = wrap(_page("Product", 2, **FIRST_OF_NINE), "Product", as_list=True)
    assert env["count"] == 2
    assert env["total"] == 18
    assert env["page"] == 0
    assert env["total_pages"] == 9
    assert env["page_size"] == 2
    assert env["has_more"] is True


def test_has_more_false_on_last_page_without_page_size():
    env = wrap(_page("Product", 3, **LAST_PAGE), "Product", as_list=True, paging_filter="")
    assert env["count"] == 3
    assert env["total"] == 18
    assert env["page"] == 3
    assert env["total_pages"] == 4
    assert env["has_more"] is False
    # The last page may be short, so its item count is not the page size.
    assert "page_size" not in env
    assert "next_page_hint" not in env


@pytest.mark.parametrize("meta", [{}, NULL_META], ids=["absent", "null"])
def test_no_metadata_adds_no_paging_fields(meta):
    env = wrap(_page("PaymentMethod", 4, **meta), "PaymentMethod", as_list=True, paging_filter="")
    assert env["count"] == 4
    for key in PAGING_KEYS:
        assert key not in env


def test_has_more_absent_when_hasnext_missing():
    meta = {k: v for k, v in FIRST_OF_NINE.items() if k != "hasnext"}
    env = wrap(_page("Product", 2, **meta), "Product", as_list=True, paging_filter="")
    assert env["total"] == 18
    assert env["page"] == 0
    assert "has_more" not in env
    assert "page_size" not in env
    assert "next_page_hint" not in env


def test_has_more_without_itemsnumber_gives_no_page_size_or_hint():
    meta = {k: v for k, v in FIRST_OF_NINE.items() if k != "itemsnumber"}
    env = wrap(_page("Product", 2, **meta), "Product", as_list=True, paging_filter="")
    assert env["has_more"] is True
    assert "page_size" not in env
    assert "next_page_hint" not in env


def test_unparseable_values_are_skipped():
    meta = {
        "pagenumber": "x",
        "itemsnumber": "2",
        "totalpages": "",
        "totalitems": "18",
        "hasnext": "maybe",
    }
    env = wrap(_page("Product", 2, **meta), "Product", as_list=True, paging_filter="")
    assert env["total"] == 18
    for key in ("page", "total_pages", "has_more", "page_size", "next_page_hint"):
        assert key not in env


def test_count_is_items_in_this_response_not_total():
    env = wrap(_page("Transaction", 100, **{**FIRST_OF_NINE, "itemsnumber": "100"}), "Transaction")
    assert env["count"] == 100
    assert env["total"] == 18


def test_single_entity_envelope_gets_no_paging_fields():
    env = wrap(_page("Product", 1, **LAST_PAGE), "Product")
    assert env["type"] == "Product"
    for key in PAGING_KEYS:
        assert key not in env


def test_raw_keeps_upstream_metadata():
    raw = _page("Product", 2, **FIRST_OF_NINE)
    env = wrap(raw, "Product", as_list=True, raw=raw)
    assert env["raw"]["items"]["hasnext"] == "true"


# ── next_page_hint ───────────────────────────────────────────────────────────


def test_next_page_hint_only_when_tool_pages_through_filter():
    env = wrap(_page("Bundle", 2, **FIRST_OF_NINE), "Bundle", as_list=True)
    assert env["has_more"] is True
    assert "next_page_hint" not in env


def test_next_page_hint_with_empty_filter():
    env = wrap(_page("Product", 2, **FIRST_OF_NINE), "Product", as_list=True, paging_filter="")
    assert "filter='page=1;items=2'" in env["next_page_hint"]


def test_next_page_hint_keeps_user_filter_and_replaces_paging():
    env = wrap(
        _page("Product", 2, **{**FIRST_OF_NINE, "pagenumber": "4"}),
        "Product",
        as_list=True,
        paging_filter=" active=true ; page=4;items=2",
    )
    assert "filter='active=true;page=5;items=2'" in env["next_page_hint"]


@pytest.mark.parametrize(
    ("user_filter", "expected"),
    [
        ("", "page=1;items=100"),
        ("active=true", "active=true;page=1;items=100"),
        ("items=500;active=true;page=0", "active=true;page=1;items=100"),
        ("PAGE=0;Items=7;status=CLOSED", "status=CLOSED;page=1;items=100"),
        ("active=true;;", "active=true;page=1;items=100"),
    ],
)
def test_next_page_filter(user_filter, expected):
    assert next_page_filter(user_filter, 1, 100) == expected


# ── Tool level: which list tools carry the hint ──────────────────────────────


@pytest.mark.parametrize(
    ("tool", "patch_target", "kind", "args"),
    [
        ("netlicensing_list_products", "products.list_products", "Product", ()),
        ("netlicensing_list_licensees", "licensees.list_licensees", "Licensee", ("P1",)),
        ("netlicensing_list_licenses", "licenses.list_licenses", "License", ("I1",)),
        (
            "netlicensing_list_product_modules",
            "product_modules.list_product_modules",
            "ProductModule",
            ("P1",),
        ),
        (
            "netlicensing_list_license_templates",
            "license_templates.list_license_templates",
            "LicenseTemplate",
            ("M1",),
        ),
        ("netlicensing_list_tokens", "tokens.list_tokens", "Token", ()),
        ("netlicensing_list_transactions", "transactions.list_transactions", "Transaction", ()),
        (
            "netlicensing_list_payment_methods",
            "payment_methods.list_payment_methods",
            "PaymentMethod",
            (),
        ),
    ],
)
async def test_filter_list_tools_emit_next_page_hint(tool, patch_target, kind, args):
    resp = _page(kind, 2, **FIRST_OF_NINE)
    with patch(f"netlicensing_mcp.server.{patch_target}", AsyncMock(return_value=resp)):
        out = json.loads(await getattr(server, tool)(*args, filter="active=true"))
    assert out["type"] == "list"
    assert out["count"] == 2
    assert out["total"] == 18
    assert out["has_more"] is True
    assert "filter='active=true;page=1;items=2'" in out["next_page_hint"]


async def test_list_bundles_reports_metadata_without_hint():
    resp = _page("Bundle", 2, **FIRST_OF_NINE)
    with patch("netlicensing_mcp.server.bundles.list_bundles", AsyncMock(return_value=resp)):
        out = json.loads(await server.netlicensing_list_bundles())
    assert out["total"] == 18
    assert out["has_more"] is True
    assert "next_page_hint" not in out


async def test_list_licensing_models_null_metadata_adds_nothing():
    resp = _page("LicensingModelProperties", 3, **NULL_META)
    with patch(
        "netlicensing_mcp.server.utilities.list_licensing_models", AsyncMock(return_value=resp)
    ):
        out = json.loads(await server.netlicensing_list_licensing_models())
    assert out["count"] == 3
    for key in PAGING_KEYS:
        assert key not in out
