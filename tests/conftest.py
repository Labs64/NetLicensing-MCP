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
2. ``NETLICENSING_BASE_URL`` / ``MCP_CONSOLE_BASE_URL`` are set to their
   documented defaults for the same reason (tests expect the
   ``go.netlicensing.io`` host and the default console deep links). They are
   not emptied: an empty value is used as is (``client.BASE_URL = ""``, an
   empty console base), not as "not set". ``client.BASE_URL`` is read at
   import time, so this must happen before the import below. Tests that need
   another value monkeypatch ``client.BASE_URL`` or the environment.
3. ``netlicensing_mcp.server`` is imported here, so the tools are registered
   in the fixed order of ``server.py`` whatever test module pytest imports
   first (a module that imports ``netlicensing_mcp.mcp_tools.<x>`` directly
   would otherwise register that module's tools first and change the
   ``tools/list`` order the registry snapshot checks).
"""

from __future__ import annotations

import os

# Emptied ("not set" to the tool filter).
_FILTER_VARS = ("MCP_TOOLSETS", "MCP_READ_ONLY")
# Set to the defaults in client.py / responses.py (an empty value is not "unset").
_DEFAULT_VARS = {
    "NETLICENSING_BASE_URL": "https://go.netlicensing.io/core/v2/rest",
    "MCP_CONSOLE_BASE_URL": "https://ui.netlicensing.io/#",
}
_saved = {name: os.environ.get(name) for name in (*_FILTER_VARS, *_DEFAULT_VARS)}
_ignored = sorted(
    name
    for name, value in _saved.items()
    if value is not None and value != _DEFAULT_VARS.get(name, "")
)
for _name in _FILTER_VARS:
    os.environ[_name] = ""
os.environ.update(_DEFAULT_VARS)

import netlicensing_mcp.server  # noqa: E402,F401  (registers the tools in canonical order)


def pytest_report_header(config: object) -> str | None:
    if not _ignored:
        return None
    return (
        f"tests/conftest.py: ignoring {', '.join(_ignored)} from the environment "
        "for this session (the tests expect the default tool registry, API host and "
        "console URL; a .env file cannot set them either)"
    )


def pytest_unconfigure(config: object) -> None:
    for name, value in _saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
