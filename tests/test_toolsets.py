"""``MCP_TOOLSETS`` and ``MCP_READ_ONLY``: which tools get registered.

The filter is read from the environment when ``netlicensing_mcp.app`` is
imported. Most tests build a fresh server with :func:`app.new_server` /
:func:`app.register_tools` from a :class:`ToolFilter` parsed from a test
environment, so the shared ``mcp`` instance is never touched. One test runs
a subprocess to check the real import-time path end to end.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

import pytest
from mcp.server.fastmcp import FastMCP

from netlicensing_mcp import app
from netlicensing_mcp.server import (
    mcp,
    netlicensing_list_products,
    netlicensing_server_info,
)
from netlicensing_mcp.toolsets import TOOLSET_NAMES, TOOLSETS, ToolFilter, toolset_of

ALL_TOOLS = 61
READ_ONLY_TOOLS = 34


async def _registered(env: dict[str, str]) -> list[str]:
    tool_filter = ToolFilter.from_env(env)
    server = app.new_server(tool_filter)
    app.register_tools(server, tool_filter)
    return [t.name for t in await server.list_tools()]


async def _default_tools() -> list:
    return await mcp.list_tools()


# ── The toolset table ────────────────────────────────────────────────────────


def test_toolset_names():
    assert TOOLSET_NAMES == (
        "products",
        "bundles",
        "modules",
        "templates",
        "licensees",
        "licenses",
        "tokens",
        "transactions",
        "payments",
        "system",
        "workflows",
    )
    assert tuple(TOOLSETS) == TOOLSET_NAMES


async def test_every_registered_tool_is_in_exactly_one_toolset():
    registered = [t.name for t in await _default_tools()]
    for name in registered:
        owners = [ts for ts, names in TOOLSETS.items() if name in names]
        assert len(owners) == 1, f"{name} is in {owners}"
    # No stale entries: the table lists exactly the registered tools.
    table = [n for names in TOOLSETS.values() for n in names]
    assert sorted(table) == sorted(registered)
    assert len(table) == ALL_TOOLS


def test_toolset_membership_examples():
    assert toolset_of("netlicensing_validate_licensee") == "licensees"
    assert toolset_of("netlicensing_transfer_licenses") == "licensees"
    assert toolset_of("netlicensing_obtain_bundle") == "bundles"
    assert toolset_of("netlicensing_create_product_module") == "modules"
    assert toolset_of("netlicensing_preview_update_license_template") == "templates"
    assert toolset_of("netlicensing_update_payment_method") == "payments"
    assert set(TOOLSETS["system"]) == {
        "netlicensing_list_licensing_models",
        "netlicensing_list_license_types",
        "netlicensing_list_countries",
        "netlicensing_server_info",
    }
    assert set(TOOLSETS["workflows"]) == {
        "netlicensing_get_customer_health",
        "netlicensing_explain_validation",
    }
    assert toolset_of("netlicensing_no_such_tool") is None


def test_unknown_tool_name_is_rejected_at_registration(monkeypatch):
    monkeypatch.setattr(app, "_TOOL_SPECS", [])

    async def netlicensing_not_in_any_toolset() -> str:
        return "{}"

    with pytest.raises(ValueError, match="toolset"):
        app.tool(title="x", annotations=app._READONLY)(netlicensing_not_in_any_toolset)


# ── Parsing the environment ──────────────────────────────────────────────────


def test_parse_default_is_unrestricted():
    f = ToolFilter.from_env({})
    assert f.toolsets is None
    assert f.read_only is False
    assert f.is_restricted is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "TRUE", " Yes "])
def test_parse_read_only_truthy(value):
    assert ToolFilter.from_env({"MCP_READ_ONLY": value}).read_only is True


@pytest.mark.parametrize("value", ["", "false", "0", "no", "on"])
def test_parse_read_only_falsy(value):
    assert ToolFilter.from_env({"MCP_READ_ONLY": value}).read_only is False


def test_parse_toolsets_trims_and_lowercases():
    f = ToolFilter.from_env({"MCP_TOOLSETS": " Licenses , licensees,,"})
    assert f.toolsets == frozenset({"licenses", "licensees"})


@pytest.mark.parametrize("value", ["", "  ", ",", "all", "ALL", "licenses,all"])
def test_parse_toolsets_all_or_blank_means_everything(value, caplog):
    with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.toolsets"):
        f = ToolFilter.from_env({"MCP_TOOLSETS": value})
    assert f.toolsets is None
    assert caplog.records == []


def test_parse_unknown_toolset_warns_and_is_ignored(caplog):
    with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.toolsets"):
        f = ToolFilter.from_env({"MCP_TOOLSETS": "licenses,bogus"})
    assert f.toolsets == frozenset({"licenses"})
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 1
    assert "bogus" in messages[0]
    assert caplog.records[0].levelno == logging.WARNING


def test_parse_only_unknown_toolsets_falls_back_to_all(caplog):
    with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.toolsets"):
        f = ToolFilter.from_env({"MCP_TOOLSETS": "bogus,nope"})
    assert f.toolsets is None
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "bogus" in messages and "nope" in messages
    assert "all" in messages
    assert all(r.levelno == logging.WARNING for r in caplog.records)
    assert len(caplog.records) == 2


# ── Registered tool sets ─────────────────────────────────────────────────────


async def test_default_registers_all_61_tools_in_order():
    names = await _registered({})
    assert len(names) == ALL_TOOLS
    assert names == [t.name for t in await _default_tools()]


async def test_read_only_registers_only_read_only_tools():
    names = await _registered({"MCP_READ_ONLY": "true"})
    assert len(names) == READ_ONLY_TOOLS
    tool_filter = ToolFilter.from_env({"MCP_READ_ONLY": "true"})
    server = app.new_server(tool_filter)
    app.register_tools(server, tool_filter)
    for t in await server.list_tools():
        assert t.annotations is not None
        assert t.annotations.readOnlyHint is True, t.name
    # Previews are read-only and stay; writes and validate (it can check out
    # floating sessions or bind nodes) are gone.
    assert "netlicensing_preview_delete_licensee" in names
    assert "netlicensing_preview_update_product" in names
    assert "netlicensing_create_product" not in names
    assert "netlicensing_delete_license" not in names
    assert "netlicensing_validate_licensee" not in names


async def test_toolsets_licenses_licensees_only():
    names = await _registered({"MCP_TOOLSETS": "licenses,licensees"})
    expected = set(TOOLSETS["licenses"]) | set(TOOLSETS["licensees"])
    expected.add("netlicensing_server_info")
    assert set(names) == expected
    assert len(names) == 6 + 8 + 1


async def test_toolsets_then_read_only():
    names = await _registered({"MCP_TOOLSETS": "licenses", "MCP_READ_ONLY": "yes"})
    assert set(names) == {
        "netlicensing_list_licenses",
        "netlicensing_get_license",
        "netlicensing_preview_delete_license",
        "netlicensing_server_info",
    }


async def test_unknown_toolset_only_falls_back_to_all_tools(caplog):
    with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.toolsets"):
        names = await _registered({"MCP_TOOLSETS": "bogus"})
    assert len(names) == ALL_TOOLS
    assert caplog.records


@pytest.mark.parametrize(
    "env",
    [
        {"MCP_TOOLSETS": "licenses"},
        {"MCP_TOOLSETS": "workflows", "MCP_READ_ONLY": "true"},
        {"MCP_READ_ONLY": "1"},
        {"MCP_TOOLSETS": "system"},
    ],
)
async def test_server_info_is_always_registered(env):
    assert "netlicensing_server_info" in await _registered(env)


# ── Server instructions ──────────────────────────────────────────────────────


def test_instructions_unchanged_without_restriction():
    assert mcp.instructions == app.INSTRUCTIONS
    assert app.new_server(ToolFilter.from_env({})).instructions == app.INSTRUCTIONS


def test_instructions_note_read_only():
    text = app.new_server(ToolFilter.from_env({"MCP_READ_ONLY": "true"})).instructions
    assert text is not None
    assert text.startswith(app.INSTRUCTIONS)
    note = text[len(app.INSTRUCTIONS) :]
    assert "Read-only mode: write tools are not available" in note
    assert note.strip().count("\n") <= 2


def test_instructions_note_toolsets():
    text = app.new_server(ToolFilter.from_env({"MCP_TOOLSETS": "licensees,licenses"})).instructions
    assert text is not None
    note = text[len(app.INSTRUCTIONS) :]
    assert "licensees, licenses" in note
    assert "Read-only" not in note


# ── Decorator and direct calls ───────────────────────────────────────────────


async def test_decorator_skips_filtered_tool_but_returns_function(monkeypatch):
    server = FastMCP("test")
    monkeypatch.setattr(app, "mcp", server)
    monkeypatch.setattr(app, "_TOOL_SPECS", [])
    monkeypatch.setattr(app, "_active_filter", ToolFilter.from_env({"MCP_READ_ONLY": "true"}))

    async def netlicensing_create_product() -> str:
        return '{"ok": true}'

    async def netlicensing_get_product() -> str:
        return '{"ok": true}'

    write = app.tool(title="w", annotations=app._WRITE)(netlicensing_create_product)
    read = app.tool(title="r", annotations=app._READONLY)(netlicensing_get_product)
    assert write is netlicensing_create_product
    assert read is netlicensing_get_product
    assert json.loads(await write()) == {"ok": True}
    assert [t.name for t in await server.list_tools()] == ["netlicensing_get_product"]
    # The spec is recorded either way, so a fresh server can still get it.
    assert [s.name for s in app._TOOL_SPECS] == [
        "netlicensing_create_product",
        "netlicensing_get_product",
    ]


def test_direct_imports_are_plain_functions():
    assert callable(netlicensing_list_products)
    assert callable(netlicensing_server_info)


# ── Settings helper (for netlicensing_server_info, Task 6) ───────────────────


async def test_active_tool_settings_default():
    settings = app.active_tool_settings()
    assert settings == {"toolsets": ["all"], "read_only": False, "tool_count": ALL_TOOLS}
    assert settings["tool_count"] == len(await _default_tools())


def test_tool_settings_for_restricted_filter():
    f = ToolFilter.from_env({"MCP_TOOLSETS": "licenses,licensees", "MCP_READ_ONLY": "true"})
    assert app.tool_settings(f) == {
        "toolsets": ["licensees", "licenses"],
        "read_only": True,
        "tool_count": 3 + 3 + 1,
    }


# ── End to end: env read at import time ──────────────────────────────────────

_PROBE = """
import asyncio, json
from netlicensing_mcp.server import mcp
from netlicensing_mcp.app import INSTRUCTIONS, active_tool_settings
names = [t.name for t in asyncio.run(mcp.list_tools())]
print(json.dumps({
    "names": names,
    "note": (mcp.instructions or "")[len(INSTRUCTIONS):],
    "settings": active_tool_settings(),
    "prompts": len(asyncio.run(mcp.list_prompts())),
}))
"""


def test_env_is_applied_at_import_time():
    env = {
        **os.environ,
        "MCP_TOOLSETS": "licenses, bogus",
        "MCP_READ_ONLY": "true",
        "NETLICENSING_ALLOW_DEMO": "true",
    }
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["names"] == [
        "netlicensing_list_licenses",
        "netlicensing_get_license",
        "netlicensing_preview_delete_license",
        "netlicensing_server_info",
    ]
    assert out["settings"] == {"toolsets": ["licenses"], "read_only": True, "tool_count": 4}
    assert "Read-only mode" in out["note"]
    assert out["prompts"] == 11
    # The warning goes to stderr; stdout carries only the probe's JSON.
    assert "bogus" in proc.stderr
    assert "bogus" not in proc.stdout


def test_toolset_table_rejects_duplicates():
    from netlicensing_mcp.toolsets import _index

    with pytest.raises(ValueError, match="netlicensing_x"):
        _index({"a": ("netlicensing_x",), "b": ("netlicensing_x",)})
