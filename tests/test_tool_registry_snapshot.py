"""Golden snapshot of the public MCP surface (tools + prompts).

Guards against accidental changes to what MCP clients see: tool names,
titles, descriptions (docstrings), input/output schemas, annotations, the tool
registration order, and the registered prompts with their argument names.

Regenerate the snapshot after an *intentional* change with::

    UPDATE_SNAPSHOT=1 .venv/bin/python -m pytest tests/test_tool_registry_snapshot.py --no-cov

and review the diff of ``tests/fixtures/tools_snapshot.json`` before committing.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

from netlicensing_mcp.server import mcp

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "tools_snapshot.json"


async def _live_registry() -> dict:
    tools = await mcp.list_tools()
    prompts = await mcp.list_prompts()
    return {
        "tool_order": [t.name for t in tools],
        "tools": [
            {
                "name": t.name,
                "title": t.title,
                # cleandoc: Python 3.13+ strips docstring indentation at compile time,
                # 3.12 does not; compare the text, not the indentation.
                "description": inspect.cleandoc(t.description or ""),
                "inputSchema": t.inputSchema,
                "outputSchema": t.outputSchema,
                "annotations": (
                    t.annotations.model_dump(mode="json") if t.annotations is not None else None
                ),
            }
            for t in sorted(tools, key=lambda t: t.name)
        ],
        "prompts": [
            {
                "name": p.name,
                "arguments": [a.name for a in (p.arguments or [])],
            }
            for p in prompts
        ],
    }


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


async def test_tool_registry_matches_snapshot():
    live = _dump(await _live_registry())
    if os.getenv("UPDATE_SNAPSHOT") == "1":
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(live, encoding="utf-8")
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert live == expected, (
        "MCP tool/prompt registry differs from tests/fixtures/tools_snapshot.json. "
        "If the change is intentional, regenerate with UPDATE_SNAPSHOT=1 (see module docstring)."
    )


async def test_snapshot_covers_every_tool():
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert len(data["tools"]) == len(data["tool_order"]) == 61
    assert sorted(data["tool_order"]) == [t["name"] for t in data["tools"]]
    assert all(t["name"].startswith("netlicensing_") for t in data["tools"])
    assert len(data["prompts"]) == 11


async def test_default_registry_has_61_tools():
    # Without MCP_TOOLSETS / MCP_READ_ONLY every tool is registered.
    assert len(await mcp.list_tools()) == 61
