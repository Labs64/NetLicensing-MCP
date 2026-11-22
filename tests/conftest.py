"""Session-wide test setup, run by pytest before any test module is imported.

1. ``MCP_TOOLSETS`` / ``MCP_READ_ONLY`` are read once, when
   ``netlicensing_mcp.app`` is imported, and shrink the shared tool registry.
   Exported in the developer's shell they would make every test that expects
   the default registry fail, so they are removed from the environment here
   (and restored after the session). Tests that need them build their own
   server from an explicit environment (see ``tests/test_toolsets.py``).
2. ``netlicensing_mcp.server`` is imported here, so the tools are registered
   in the fixed order of ``server.py`` whatever test module pytest imports
   first (a module that imports ``netlicensing_mcp.mcp_tools.<x>`` directly
   would otherwise register that module's tools first and change the
   ``tools/list`` order the registry snapshot checks).
"""

from __future__ import annotations

import os
import sys

_FILTER_VARS = ("MCP_TOOLSETS", "MCP_READ_ONLY")
_saved = {name: os.environ.pop(name) for name in _FILTER_VARS if name in os.environ}
if _saved:
    print(
        f"tests/conftest.py: ignoring {', '.join(sorted(_saved))} from the environment "
        "for this test session (the tests expect the default tool registry)",
        file=sys.stderr,
    )

import netlicensing_mcp.server  # noqa: E402,F401  (registers the tools in canonical order)


def pytest_unconfigure(config: object) -> None:
    os.environ.update(_saved)
