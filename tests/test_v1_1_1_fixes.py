"""1.1.1 fixes: token supersession, cascade binding, dependency hints, JSON delete results."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from netlicensing_mcp import safety
from netlicensing_mcp.server import (
    netlicensing_delete_bundle,
    netlicensing_delete_license,
    netlicensing_delete_license_template,
    netlicensing_delete_licensee,
    netlicensing_delete_product,
    netlicensing_delete_product_module,
    netlicensing_delete_token,
    netlicensing_preview_delete_product,
)


@pytest.fixture(autouse=True)
def clear_store():
    safety._store.clear()
    yield
    safety._store.clear()


def _items(n: int) -> dict:
    return {
        "item": [{"property": [{"name": "number", "value": f"L{i}"}]} for i in range(n)],
        "items": {"totalitems": str(n)},
    }


def _patch_deps(licensees: int = 0, modules: int = 0):
    return (
        patch("netlicensing_mcp.tools.products.get_product", AsyncMock(return_value={})),
        patch(
            "netlicensing_mcp.tools.product_modules.list_product_modules",
            AsyncMock(return_value=_items(modules)),
        ),
        patch(
            "netlicensing_mcp.tools.licensees.list_licensees",
            AsyncMock(return_value=_items(licensees)),
        ),
    )


# ── Issue 1 ──────────────────────────────────────────────────────────────────
async def test_preview_twice_keeps_first_token_usable():
    p1, p2, p3 = _patch_deps()
    with (
        p1,
        p2,
        p3,
        patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)),
    ):
        t0 = json.loads(await netlicensing_preview_delete_product("P"))["confirmation_token"]
        t1 = json.loads(await netlicensing_preview_delete_product("P"))["confirmation_token"]
        assert t0 != t1
        r = json.loads(await netlicensing_delete_product("P", confirm_token=t0))
        assert r["deleted"] is True


async def test_delete_without_token_then_preview_keeps_first_token_usable():
    p1, p2, p3 = _patch_deps()
    with (
        p1,
        p2,
        p3,
        patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)),
    ):
        t0 = json.loads(await netlicensing_delete_product("P"))["confirmation_token"]
        await netlicensing_preview_delete_product("P")
        r = json.loads(await netlicensing_delete_product("P", confirm_token=t0))
        assert r["deleted"] is True


# ── Issue 2 ──────────────────────────────────────────────────────────────────
async def test_preview_flags_requires_force_cascade_with_dependents():
    p1, p2, p3 = _patch_deps(licensees=1)
    with p1, p2, p3:
        r = json.loads(await netlicensing_preview_delete_product("P"))
    assert r["requires_force_cascade"] is True
    assert r["blocking_dependencies"] == {"licensees": 1}
    assert "force_cascade=true" in r["instructions"]


async def test_preview_without_dependents_does_not_require_cascade():
    p1, p2, p3 = _patch_deps()
    with p1, p2, p3:
        r = json.loads(await netlicensing_preview_delete_product("P"))
    assert r["requires_force_cascade"] is False
    assert r["blocking_dependencies"] == {}


async def test_delete_without_token_flags_dependents_too():
    p1, p2, p3 = _patch_deps(modules=2)
    with p1, p2, p3:
        r = json.loads(await netlicensing_delete_product("P"))
    assert r["requires_force_cascade"] is True
    assert r["blocking_dependencies"] == {"product_modules": 2}


# ── Issue 3 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("tool", "module", "op", "arg"),
    [
        (netlicensing_delete_product, "products", "delete_product", "product_number"),
        (netlicensing_delete_licensee, "licensees", "delete_licensee", "licensee_number"),
        (netlicensing_delete_license, "licenses", "delete_license", "license_number"),
        (
            netlicensing_delete_license_template,
            "license_templates",
            "delete_license_template",
            "template_number",
        ),
        (
            netlicensing_delete_product_module,
            "product_modules",
            "delete_product_module",
            "module_number",
        ),
        (netlicensing_delete_bundle, "bundles", "delete_bundle", "bundle_number"),
        (netlicensing_delete_token, "tokens", "delete_token", "token_number"),
    ],
)
async def test_successful_delete_returns_json(tool, module, op, arg):
    token, _ = safety.issue_token(op, "X1")
    with patch(f"netlicensing_mcp.tools.{module}.nl_delete", AsyncMock(return_value=204)):
        raw = await tool(**{arg: "X1", "confirm_token": token})
    r = json.loads(raw)
    assert r["operation"] == op
    assert r["deleted"] is True
    assert r["status"] == 204
    assert r["cascade"] is False


# ── Issue 4 ──────────────────────────────────────────────────────────────────
async def test_non_cascade_token_rejected_for_cascade_delete():
    token, _ = safety.issue_token("delete_product", "P", force_cascade=False)
    r = json.loads(await netlicensing_delete_product("P", force_cascade=True, confirm_token=token))
    assert r["error"] is True
    assert "non-cascade" in r["detail"]


async def test_cascade_token_rejected_for_plain_delete():
    token, _ = safety.issue_token("delete_product", "P", force_cascade=True)
    r = json.loads(await netlicensing_delete_product("P", confirm_token=token))
    assert r["error"] is True
    assert "cascade" in r["detail"]


async def test_cascade_mismatch_does_not_consume_token():
    token, _ = safety.issue_token("delete_product", "P", force_cascade=False)
    await netlicensing_delete_product("P", force_cascade=True, confirm_token=token)
    with patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)):
        r = json.loads(await netlicensing_delete_product("P", confirm_token=token))
    assert r["deleted"] is True


async def test_preview_accepts_force_cascade_and_binds_it():
    p1, p2, p3 = _patch_deps(licensees=1)
    with (
        p1,
        p2,
        p3,
        patch("netlicensing_mcp.tools.products.nl_delete", AsyncMock(return_value=204)),
    ):
        t = json.loads(await netlicensing_preview_delete_product("P", force_cascade=True))
        r = json.loads(
            await netlicensing_delete_product(
                "P", force_cascade=True, confirm_token=t["confirmation_token"]
            )
        )
    assert r["deleted"] is True and r["cascade"] is True
