"""Error blobs carry next-step hints (``hint``, ``suggested_actions``, ``retryable``).

The upstream shapes used here were checked against the NetLicensing sandbox
(``demo:demo``) and the API Conventions page
(https://netlicensing.io/wiki/api-conventions):

- a missing entity is ``400`` with info id ``NotFoundException`` and the text
  ``Requested <entity> does not exist.`` (or ``<Entity> with the given number
  not found.``), not ``404``;
- a duplicate number is ``400`` ``DuplicateEntityException``
  (``Product with the given number already exists.``);
- deleting a product that still has licensees without ``forceCascade`` is
  ``400`` ``IllegalOperationException`` (``This product has Licensees.``);
- a missing required field is ``400`` ``MalformedRequestException``;
- ``401`` bad credentials, ``402`` not in plan, ``403`` role too low,
  ``429`` rate limit with ``Retry-After`` seconds, ``500`` internal error.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import netlicensing_mcp.app as app
import netlicensing_mcp.client as client
from netlicensing_mcp import safety, server
from netlicensing_mcp.app import to_call_tool_result
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.errors import CASCADE_DELETE_TOOLS, confirmation_hint, error_hint
from netlicensing_mcp.server import mcp
from netlicensing_mcp.toolsets import TOOLSETS, ToolFilter

ALL_TOOLS = [name for names in TOOLSETS.values() for name in names]

NO_KEY_DETAIL = (
    "No NetLicensing API key configured. "
    "Set NETLICENSING_API_KEY or supply X-NetLicensing-API-Key. "
    "For sandbox/demo access, set NETLICENSING_ALLOW_DEMO=true."
)


def _nf(entity: str) -> NetLicensingError:
    return NetLicensingError(
        400, f"Requested {entity} does not exist.", info_ids=("NotFoundException",)
    )


@pytest.fixture(autouse=True)
def _no_demo_mode(monkeypatch):
    monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)


@pytest.fixture(autouse=True)
def _clear_tokens():
    safety._store.clear()
    yield
    safety._store.clear()


# ── Not found: suggestion derived from the tool / the upstream message ───────


@pytest.mark.parametrize(
    ("tool", "exc", "suggestion"),
    [
        ("netlicensing_get_licensee", _nf("licensee"), "netlicensing_list_licensees"),
        ("netlicensing_update_licensee", _nf("licensee"), "netlicensing_list_licensees"),
        ("netlicensing_delete_licensee", _nf("licensee"), "netlicensing_list_licensees"),
        # A bare 404 (no info id) is treated as not found too.
        (
            "netlicensing_update_licensee",
            NetLicensingError(404, "x"),
            "netlicensing_list_licensees",
        ),
        ("netlicensing_get_product", _nf("product"), "netlicensing_list_products"),
        (
            "netlicensing_get_product_module",
            _nf("product module"),
            "netlicensing_list_product_modules",
        ),
        (
            "netlicensing_get_license_template",
            _nf("license template"),
            "netlicensing_list_license_templates",
        ),
        ("netlicensing_get_license", _nf("license"), "netlicensing_list_licenses"),
        ("netlicensing_get_bundle", _nf("bundle"), "netlicensing_list_bundles"),
        ("netlicensing_get_token", _nf("token"), "netlicensing_list_tokens"),
        ("netlicensing_get_transaction", _nf("transaction"), "netlicensing_list_transactions"),
        (
            "netlicensing_get_payment_method",
            NetLicensingError(404, "x"),
            "netlicensing_list_payment_methods",
        ),
        # The upstream message names the missing entity; it wins over the tool.
        (
            "netlicensing_validate_licensee",
            NetLicensingError(
                400,
                "Product with the given number not found.",
                info_ids=("NotFoundException",),
            ),
            "netlicensing_list_products",
        ),
        ("netlicensing_obtain_bundle", _nf("licensee"), "netlicensing_list_licensees"),
        ("netlicensing_get_customer_health", _nf("licensee"), "netlicensing_list_licensees"),
        ("netlicensing_explain_validation", _nf("licensee"), "netlicensing_list_licensees"),
        (None, _nf("product module"), "netlicensing_list_product_modules"),
    ],
)
def test_not_found_suggests_the_list_tool(tool, exc, suggestion):
    h = error_hint(exc, tool)
    assert h["suggested_actions"] == [suggestion]
    assert h["retryable"] is False
    assert "not found" in h["hint"]
    assert "case-sensitive" in h["hint"]
    assert suggestion in h["hint"]


def test_not_found_detected_from_message_without_info_id():
    h = error_hint(NetLicensingError(400, "Requested bundle does not exist."), None)
    assert h["suggested_actions"] == ["netlicensing_list_bundles"]


@pytest.mark.parametrize("info_ids", [(), ("NotFoundException",)])
def test_create_with_unnamed_missing_value_is_a_validation_error(info_ids):
    # The missing thing is a referenced value, not the product module being created.
    exc = NetLicensingError(400, "Licensing model 'Foo' does not exist", info_ids=info_ids)
    h = error_hint(exc, "netlicensing_create_product_module")
    assert "not found" not in h["hint"]
    assert "product module" not in h["hint"]
    assert "'detail'" in h["hint"] and "required fields" in h["hint"]
    assert h["suggested_actions"] == []
    assert h["retryable"] is False


def test_create_with_named_missing_parent_is_still_not_found():
    h = error_hint(_nf("licensee"), "netlicensing_create_license")
    assert "licensee was not found" in h["hint"]
    assert h["suggested_actions"] == ["netlicensing_list_licensees"]


def test_not_found_without_known_entity_has_no_suggestion():
    h = error_hint(NetLicensingError(404, "gone"), None)
    assert h["suggested_actions"] == []
    assert "not found" in h["hint"]


# ── Credentials and plan ────────────────────────────────────────────────────


@pytest.mark.parametrize("tool", [None, "netlicensing_list_products", "netlicensing_get_license"])
def test_401_points_at_key_settings(tool):
    h = error_hint(NetLicensingError(401, "Unauthorized", info_ids=("401",)), tool)
    assert "NETLICENSING_API_KEY" in h["hint"]
    assert "X-NetLicensing-API-Key" in h["hint"]
    assert h["retryable"] is False
    assert h["suggested_actions"] == []


def test_403_mentions_role_and_key_settings():
    h = error_hint(
        NetLicensingError(403, "Forbidden", info_ids=("403",)), "netlicensing_create_product"
    )
    assert "role" in h["hint"]
    assert "MAINTENANCE" in h["hint"] or "higher role" in h["hint"]
    # Role ladder as on https://netlicensing.io/wiki/api-conventions (cumulative, lowest first).
    ladder = ["LICENSEE (", "ANALYTICS (", "OPERATION (", "MAINTENANCE (", "ADMIN ("]
    positions = [h["hint"].index(role) for role in ladder]
    assert positions == sorted(positions)
    assert "cumulative" in h["hint"]
    assert "NETLICENSING_API_KEY" in h["hint"]
    assert "X-NetLicensing-API-Key" in h["hint"]
    assert h["retryable"] is False


def test_402_is_plan_limitation():
    h = error_hint(NetLicensingError(402, "x"), "netlicensing_create_licensee")
    assert "pricing plan" in h["hint"]
    assert h["retryable"] is False


def test_missing_key_503_is_configuration_not_outage():
    h = error_hint(NetLicensingError(503, NO_KEY_DETAIL), "netlicensing_list_products")
    assert h["retryable"] is False
    assert "NETLICENSING_API_KEY" in h["hint"]
    assert "X-NetLicensing-API-Key" in h["hint"]
    assert "NETLICENSING_ALLOW_DEMO" in h["hint"]


# ── Duplicates and cascade deletes ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("tool", "exc", "suggestions"),
    [
        (
            "netlicensing_create_product",
            NetLicensingError(
                400,
                "Product with the given number already exists.",
                info_ids=("DuplicateEntityException",),
            ),
            ["netlicensing_get_product", "netlicensing_update_product"],
        ),
        (
            "netlicensing_create_licensee",
            NetLicensingError(409, "conflict"),
            ["netlicensing_get_licensee", "netlicensing_update_licensee"],
        ),
        (
            "netlicensing_create_licensee",
            NetLicensingError(400, "Licensee with the given number already exists."),
            ["netlicensing_get_licensee", "netlicensing_update_licensee"],
        ),
    ],
)
def test_duplicate_number(tool, exc, suggestions):
    h = error_hint(exc, tool)
    assert h["suggested_actions"] == suggestions
    assert "already exists" in h["hint"]
    assert "empty" in h["hint"]
    assert h["retryable"] is False


@pytest.mark.parametrize(
    ("tool", "exc", "suggestions", "cascade_and_update"),
    [
        (
            "netlicensing_delete_product",
            NetLicensingError(
                400, "This product has Licensees.", info_ids=("IllegalOperationException",)
            ),
            ["netlicensing_preview_delete_product", "netlicensing_update_product"],
            True,
        ),
        (
            "netlicensing_delete_licensee",
            NetLicensingError(409, "conflict"),
            ["netlicensing_preview_delete_licensee", "netlicensing_update_licensee"],
            True,
        ),
        (
            # Tokens cannot be deactivated (no update tool) and delete_token has
            # no force_cascade parameter: the hint mentions neither.
            "netlicensing_delete_token",
            NetLicensingError(409, "conflict"),
            ["netlicensing_preview_delete_token"],
            False,
        ),
    ],
)
def test_delete_blocked_by_dependents(tool, exc, suggestions, cascade_and_update):
    h = error_hint(exc, tool)
    assert h["suggested_actions"] == suggestions
    assert ("force_cascade" in h["hint"]) is cascade_and_update
    assert ("explicitly" in h["hint"]) is cascade_and_update
    assert ("active=false" in h["hint"]) is cascade_and_update
    assert suggestions[0] in h["hint"]
    assert h["retryable"] is False


async def test_cascade_delete_tools_match_the_registry():
    tools = await mcp.list_tools()
    with_cascade = {
        t.name
        for t in tools
        if t.name.startswith("netlicensing_delete_")
        and "force_cascade" in t.inputSchema["properties"]
    }
    assert with_cascade == CASCADE_DELETE_TOOLS


def test_illegal_operation_outside_delete_is_a_validation_error():
    exc = NetLicensingError(400, "nope", info_ids=("IllegalOperationException",))
    h = error_hint(exc, "netlicensing_update_license")
    assert "force_cascade" not in h["hint"]
    assert "'detail'" in h["hint"]


# ── Validation ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", [400, 422])
def test_validation_refers_to_detail_then_required_fields(status):
    exc = NetLicensingError(
        status, "Product number is not provided.", info_ids=("MalformedRequestException",)
    )
    h = error_hint(exc, "netlicensing_create_licensee")
    assert h["hint"].index("'detail'") < h["hint"].index("required fields")
    assert h["retryable"] is False
    assert h["suggested_actions"] == []


# ── Rate limit, outages and transport failures ──────────────────────────────


def test_429_is_retryable_with_retry_after():
    h = error_hint(NetLicensingError(429, "busy", retry_after=30), "netlicensing_list_products")
    assert h["retryable"] is True
    assert h["retry_after_seconds"] == 30
    assert "30 seconds" in h["hint"]
    assert "rate limit" in h["hint"]


def test_429_without_retry_after():
    h = error_hint(NetLicensingError(429, "busy"), None)
    assert h["retryable"] is True
    assert "retry_after_seconds" not in h


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (500, "boom"),
        (502, "Could not reach the NetLicensing API"),
        (502, "NetLicensing API returned a non-JSON response"),
        (503, "Service Unavailable"),
        (504, "NetLicensing API request timed out"),
    ],
)
def test_5xx_is_retryable_and_names_only_the_host(status, detail, monkeypatch):
    monkeypatch.setattr(client, "BASE_URL", "https://user:pw@nl.example.com:8443/core/v2/rest")
    h = error_hint(NetLicensingError(status, detail), "netlicensing_list_products")
    assert h["retryable"] is True
    assert "nl.example.com" in h["hint"]
    for leak in ("pw", "user:", "/core", "8443", "https://"):
        assert leak not in h["hint"]


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (500, "boom"),
        (502, "Could not reach the NetLicensing API"),
        (502, "NetLicensing API returned a non-JSON response"),
        (504, "NetLicensing API request timed out"),
    ],
)
def test_malformed_base_url_does_not_raise(status, detail, monkeypatch):
    # urlsplit() raises ValueError ("Invalid IPv6 URL") for this URL.
    monkeypatch.setattr(client, "BASE_URL", "http://[::1/core/v2/rest")
    h = error_hint(NetLicensingError(status, detail), "netlicensing_list_products")
    assert "the NETLICENSING_BASE_URL host" in h["hint"]
    assert "[::1" not in h["hint"]


def test_unreachable_default_host_mentions_documented_backup_host(monkeypatch):
    monkeypatch.setattr(client, "BASE_URL", "https://go.netlicensing.io/core/v2/rest")
    h = error_hint(NetLicensingError(502, "Could not reach the NetLicensing API"), None)
    assert "go.netlicensing.io" in h["hint"]
    assert "netlicensing.labs64.com" in h["hint"]


@pytest.mark.parametrize(
    ("tool", "suggestion"),
    [
        ("netlicensing_create_license", "netlicensing_list_licenses"),
        ("netlicensing_update_license", "netlicensing_get_license"),
        ("netlicensing_delete_license", "netlicensing_get_license"),
    ],
)
def test_timeout_on_write_says_check_state_before_retrying(tool, suggestion):
    h = error_hint(NetLicensingError(504, "NetLicensing API request timed out"), tool)
    assert h["retryable"] is True
    assert "may have been applied" in h["hint"]
    assert h["suggested_actions"] == [suggestion]


def test_timeout_on_read_has_no_state_warning():
    h = error_hint(NetLicensingError(504, "x"), "netlicensing_get_license")
    assert "may have been applied" not in h["hint"]
    assert h["suggested_actions"] == []


def test_unknown_status_falls_back_to_detail():
    h = error_hint(NetLicensingError(418, "teapot"), "netlicensing_get_license")
    assert "'detail'" in h["hint"]
    assert h["retryable"] is False
    assert h["suggested_actions"] == []


# ── Confirmation-token errors (ValueError branches) ─────────────────────────


@pytest.mark.parametrize(
    ("tool", "suggestion"),
    [
        ("netlicensing_delete_licensee", "netlicensing_preview_delete_licensee"),
        ("netlicensing_delete_product", "netlicensing_preview_delete_product"),
        ("netlicensing_update_product", "netlicensing_preview_update_product"),
        ("netlicensing_update_payment_method", "netlicensing_preview_update_payment_method"),
    ],
)
def test_confirmation_hint_points_at_preview(tool, suggestion):
    h = confirmation_hint(tool)
    assert h["suggested_actions"] == [suggestion]
    assert suggestion in h["hint"]
    assert "5 minutes" in h["hint"]
    assert h["retryable"] is False


async def test_bad_confirm_token_blob_has_hint():
    out = json.loads(await server.netlicensing_delete_licensee("I001", confirm_token="not-a-token"))
    assert out["error"] is True
    assert "Invalid or already used confirmation token" in out["detail"]
    assert out["suggested_actions"] == ["netlicensing_preview_delete_licensee"]
    assert out["retryable"] is False


# ── Every hint ───────────────────────────────────────────────────────────────

SAMPLE_ERRORS = [
    NetLicensingError(400, "Requested licensee does not exist.", info_ids=("NotFoundException",)),
    NetLicensingError(400, "dup", info_ids=("DuplicateEntityException",)),
    NetLicensingError(400, "dep", info_ids=("IllegalOperationException",)),
    NetLicensingError(400, "bad", info_ids=("MalformedRequestException",)),
    NetLicensingError(401, "Unauthorized"),
    NetLicensingError(402, "plan"),
    NetLicensingError(403, "Forbidden"),
    NetLicensingError(404, "gone"),
    NetLicensingError(409, "conflict"),
    NetLicensingError(422, "invalid"),
    NetLicensingError(429, "busy", retry_after=5),
    NetLicensingError(500, "boom"),
    NetLicensingError(502, "Could not reach the NetLicensing API"),
    NetLicensingError(503, NO_KEY_DETAIL),
    NetLicensingError(504, "NetLicensing API request timed out"),
    NetLicensingError(418, "teapot"),
]


async def test_suggested_tools_exist_in_the_default_registry():
    registered = {t.name for t in await mcp.list_tools()}
    seen: set[str] = set()
    for tool in [None, *ALL_TOOLS]:
        for exc in SAMPLE_ERRORS:
            h = error_hint(exc, tool)
            assert set(h["suggested_actions"]) <= registered, (tool, exc)
            seen.update(h["suggested_actions"])
        seen.update(confirmation_hint(tool)["suggested_actions"])
    assert seen <= registered
    assert len(seen) > 10  # the mapping really suggests tools


@pytest.mark.parametrize("tool", [None, *ALL_TOOLS])
def test_hint_shape(tool):
    for exc in SAMPLE_ERRORS:
        h = error_hint(exc, tool)
        assert isinstance(h["hint"], str) and h["hint"]
        assert isinstance(h["suggested_actions"], list)
        assert all(isinstance(a, str) for a in h["suggested_actions"])
        assert isinstance(h["retryable"], bool)


KEY = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.mark.parametrize("tool", [None, *ALL_TOOLS])
def test_no_api_key_in_any_hint(tool, monkeypatch):
    monkeypatch.setenv("NETLICENSING_API_KEY", KEY)
    monkeypatch.setattr(client, "BASE_URL", f"https://apiKey:{KEY}@nl.example.com/{KEY}/rest")
    token = client.api_key_ctx.set(KEY)
    try:
        for base in SAMPLE_ERRORS:
            exc = NetLicensingError(
                base.status_code,
                f"{base.detail} apiKey:{KEY}",
                info_ids=base.info_ids,
                retry_after=base.retry_after,
            )
            h = error_hint(exc, tool)
            assert KEY not in json.dumps(h)
            assert KEY not in json.dumps(confirmation_hint(tool))
    finally:
        client.api_key_ctx.reset(token)


# ── Wired into the tools ────────────────────────────────────────────────────


@pytest.fixture
def fake_http():
    fake = AsyncMock()
    with patch("netlicensing_mcp.client._get_client", return_value=fake):
        tok = client.api_key_ctx.set(KEY)
        try:
            yield fake
        finally:
            client.api_key_ctx.reset(tok)


async def test_tool_blob_keeps_old_keys_and_adds_hint(fake_http):
    body = {
        "infos": {
            "info": [
                {
                    "value": "Requested licensee does not exist.",
                    "id": "NotFoundException",
                    "type": "ERROR",
                }
            ]
        }
    }
    fake_http.get.return_value = httpx.Response(400, json=body)
    text = await server.netlicensing_get_licensee("I-GONE")
    out = json.loads(text)
    assert list(out)[:3] == ["error", "status", "detail"]
    assert out["error"] is True
    assert out["status"] == 400
    assert out["detail"] == "Requested licensee does not exist."
    assert out["suggested_actions"] == ["netlicensing_list_licensees"]
    assert out["retryable"] is False
    assert to_call_tool_result(text).isError is True


async def test_tool_blob_never_echoes_key_from_upstream(fake_http):
    body = {"infos": {"info": [{"value": f"bad key {KEY}", "id": "401", "type": "ERROR"}]}}
    fake_http.get.return_value = httpx.Response(
        401, json=body, headers={"WWW-Authenticate": f'Basic realm="{KEY}"'}
    )
    out = json.loads(await server.netlicensing_list_products())
    assert out["status"] == 401
    assert KEY not in out["hint"]
    assert KEY not in json.dumps(out["suggested_actions"])


async def test_rate_limit_from_upstream_carries_retry_after(fake_http):
    fake_http.get.return_value = httpx.Response(
        429, json={"infos": {"info": []}}, headers={"Retry-After": "12"}
    )
    out = json.loads(await server.netlicensing_list_products())
    assert out["status"] == 429
    assert out["retryable"] is True
    assert out["retry_after_seconds"] == 12


async def test_timeout_blob_is_retryable(fake_http):
    fake_http.get.side_effect = httpx.ReadTimeout("slow")
    out = json.loads(await server.netlicensing_get_product("P1"))
    assert out["status"] == 504
    assert out["retryable"] is True


async def test_restricted_registry_drops_unregistered_suggestions(monkeypatch):
    monkeypatch.setattr(app, "_active_filter", ToolFilter.from_env({"MCP_TOOLSETS": "licenses"}))
    out = json.loads(app._error(_nf("licensee"), "netlicensing_get_licensee"))
    assert out["suggested_actions"] == []
    assert "netlicensing_list_licensees" not in out["hint"]
    monkeypatch.setattr(app, "_active_filter", ToolFilter.from_env({}))
    out = json.loads(app._error(_nf("licensee"), "netlicensing_get_licensee"))
    assert out["suggested_actions"] == ["netlicensing_list_licensees"]


def test_error_without_tool_name_still_works():
    out = json.loads(app._error(NetLicensingError(500, "boom")))
    assert out["error"] is True and out["status"] == 500 and out["retryable"] is True


# ── Client keeps the upstream info ids and Retry-After ──────────────────────


def test_raise_on_error_keeps_info_ids_and_retry_after():
    r = httpx.Response(
        429,
        json={"infos": {"info": [{"id": "A", "value": "x"}, {"id": "B", "value": "y"}]}},
        headers={"Retry-After": "7"},
    )
    with pytest.raises(NetLicensingError) as e:
        client._raise_on_error(r)
    assert e.value.detail == "x; y"
    assert e.value.info_ids == ("A", "B")
    assert e.value.retry_after == 7


@pytest.mark.parametrize("value", ["soon", "-3", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_retry_after_that_is_not_seconds_is_ignored(value):
    r = httpx.Response(429, text="busy", headers={"Retry-After": value})
    with pytest.raises(NetLicensingError) as e:
        client._raise_on_error(r)
    assert e.value.retry_after is None
    assert e.value.info_ids == ()


def test_netlicensing_error_positional_signature_unchanged():
    exc = NetLicensingError(404, "Product not found")
    assert (exc.status_code, exc.detail, exc.info_ids, exc.retry_after) == (
        404,
        "Product not found",
        (),
        None,
    )
    assert str(exc) == "HTTP 404: Product not found"


# ── Call sites pass their own tool name (grep-able, mechanical) ─────────────

MCP_TOOLS_DIR = Path(app.__file__).parent / "mcp_tools"


def _error_calls():
    for path in sorted(MCP_TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("_error", "_confirm_error")
                ):
                    yield path.name, fn.name, node


def test_every_error_call_site_passes_its_tool_name():
    calls = list(_error_calls())
    assert len(calls) > 60
    for filename, fn_name, call in calls:
        assert len(call.args) == 2, (filename, fn_name)
        name_arg = call.args[1]
        assert isinstance(name_arg, ast.Constant) and name_arg.value == fn_name, (
            filename,
            fn_name,
        )


def test_no_hand_built_error_blobs_left_in_tool_wrappers():
    for path in sorted(MCP_TOOLS_DIR.glob("*.py")):
        assert '{"error": True' not in path.read_text(), path.name
