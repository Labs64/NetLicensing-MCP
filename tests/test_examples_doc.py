"""docs/EXAMPLES.md and the README install snippets name real tools, arguments and prompts."""

from __future__ import annotations

import base64
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Import the server first: it registers the tool modules in their fixed order.
import netlicensing_mcp.server  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "docs" / "EXAMPLES.md"
SCRIPT = ROOT / "scripts" / "gen_tools_doc.py"


def _load_generator() -> ModuleType:
    name = "gen_tools_doc"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def registry():
    return _load_generator().collect()


def _examples() -> str:
    return EXAMPLES.read_text(encoding="utf-8")


def test_examples_name_only_registered_tools(registry):
    tools = {t.name for t in registry.tools}
    named = set(re.findall(r"\bnetlicensing_\w+", _examples()))
    assert len(named) >= 15
    assert named <= tools, sorted(named - tools)


def test_example_calls_use_real_argument_names(registry):
    params = {t.name: {p.name for p in t.params} for t in registry.tools}
    calls = re.findall(r"\b(netlicensing_\w+)\(([^)]*)\)", _examples())
    assert len(calls) >= 20
    for name, args in calls:
        # Drop quoted values first: a filter value such as "active=true" is not an argument.
        used = set(re.findall(r"(\w+)=", re.sub(r'"[^"]*"', '""', args)))
        assert used <= params[name], (name, sorted(used - params[name]))


def test_examples_name_only_registered_prompts(registry):
    prompts = {p.name: {a.name for a in p.args} for p in registry.prompts}
    mentioned = re.findall(r"`(\w+)` prompt(?: \(([^)]*)\))?", _examples())
    assert len(mentioned) >= 4
    for name, args in mentioned:
        assert name in prompts, name
        used = set(re.findall(r"(\w+)=", re.sub(r'"[^"]*"', '""', args)))
        assert used <= prompts[name], (name, sorted(used - prompts[name]))


def test_examples_are_labelled_illustrative():
    assert "**Illustrative, not recorded.**" in _examples()


def test_readme_links_examples():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "](docs/EXAMPLES.md)" in readme


def test_readme_cursor_install_link_decodes_to_the_documented_config():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(
        r"cursor://anysphere\.cursor-deeplink/mcp/install\?name=([\w-]+)&config=([A-Za-z0-9+/=]+)",
        readme,
    )
    assert len(links) == 1
    name, encoded = links[0]
    assert name == "netlicensing"
    config = json.loads(base64.b64decode(encoded, validate=True))
    assert config == {
        "command": "uvx",
        "args": ["netlicensing-mcp"],
        "env": {"NETLICENSING_API_KEY": "YOUR_API_KEY"},
    }
    # The README spells out the JSON that the link carries.
    assert json.dumps(config, separators=(",", ":")) in readme
