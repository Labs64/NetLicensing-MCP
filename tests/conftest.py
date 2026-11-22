"""Session-wide test setup, run by pytest before any test module is imported.

1. ``MCP_TOOLSETS`` / ``MCP_READ_ONLY`` are read once, when
   ``netlicensing_mcp.app`` is imported, and shrink the shared tool registry.
   Set in the developer's shell or in a ``.env`` file they would make every
   test that expects the default registry fail. So they are set to ``""``
   here for the session (restored afterwards): an empty value means "not
   set" to the filter, and ``load_dotenv()`` (``override=False``, called
   when ``netlicensing_mcp.client`` is imported) does not replace a variable
   that already exists, even an empty one. Tests that need a filter build
   their own server from an explicit environment (see
   ``tests/test_toolsets.py``).
2. ``netlicensing_mcp.server`` is imported here, so the tools are registered
   in the fixed order of ``server.py`` whatever test module pytest imports
   first (a module that imports ``netlicensing_mcp.mcp_tools.<x>`` directly
   would otherwise register that module's tools first and change the
   ``tools/list`` order the registry snapshot checks).
"""

from __future__ import annotations

import os

_FILTER_VARS = ("MCP_TOOLSETS", "MCP_READ_ONLY")
_saved = {name: os.environ.get(name) for name in _FILTER_VARS}
_ignored = sorted(name for name, value in _saved.items() if value)
for _name in _FILTER_VARS:
    os.environ[_name] = ""

import netlicensing_mcp.server  # noqa: E402,F401  (registers the tools in canonical order)


def pytest_report_header(config: object) -> str | None:
    if not _ignored:
        return None
    return (
        f"tests/conftest.py: ignoring {', '.join(_ignored)} from the environment "
        "for this session (the tests expect the default tool registry; a .env "
        "file cannot set them either)"
    )


def pytest_unconfigure(config: object) -> None:
    for name, value in _saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
