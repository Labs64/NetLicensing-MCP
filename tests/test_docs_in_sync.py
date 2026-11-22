"""docs/TOOLS.md and the generated parts of README.md match the tool registry.

The generator is ``scripts/gen_tools_doc.py``; after changing a tool or a
prompt, run ``python scripts/gen_tools_doc.py`` and commit the result.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Import the server first: it registers the tool modules in their fixed order.
import netlicensing_mcp.server as server

ROOT = Path(__file__).resolve().parent.parent
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


gen = _load_generator()


@pytest.fixture(scope="module")
def registry():
    return gen.collect()


def _tools_md() -> str:
    return (ROOT / "docs" / "TOOLS.md").read_text(encoding="utf-8")


def test_committed_docs_are_in_sync(registry):
    stale = gen.stale_files(ROOT, registry)
    assert stale == [], (
        f"{', '.join(p.as_posix() for p in stale)} out of date: run "
        "`python scripts/gen_tools_doc.py` and commit the result"
    )


def test_check_mode_passes_on_committed_files(capsys):
    assert gen.main(["--check"]) == 0
    assert capsys.readouterr().err == ""


def test_check_mode_fails_on_stale_file(tmp_path, monkeypatch, capsys, registry):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "TOOLS.md").write_text("# outdated\n", encoding="utf-8")
    for name in ("README.md", "server.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    monkeypatch.setattr(gen, "ROOT", tmp_path)
    monkeypatch.setattr(gen, "collect", lambda: registry)

    assert gen.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "docs/TOOLS.md is out of date" in err
    assert "python scripts/gen_tools_doc.py" in err

    # Generating fixes it.
    assert gen.main([]) == 0
    assert gen.main(["--check"]) == 0


async def test_every_registered_tool_is_documented():
    text = _tools_md()
    names = [t.name for t in await server.mcp.list_tools()]
    assert len(names) == 61
    for name in names:
        assert f"### `{name}`" in text, name
    for prompt in await server.mcp.list_prompts():
        assert f"#### `{prompt.name}`" in text, prompt.name


def test_every_parameter_is_documented(registry):
    text = _tools_md()
    for tool in registry.tools:
        section = text.split(f"### `{tool.name}`\n", 1)[1].split("\n### ", 1)[0]
        for param in tool.params:
            assert f"| `{param.name}` |" in section, (tool.name, param.name)


def test_readme_counts_match_registry(registry):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(registry.tools) == 61 and len(registry.prompts) == 11
    tools = re.findall(r"<!-- count:tools -->(\d+)<!-- /count:tools -->", readme)
    prompts = re.findall(r"<!-- count:prompts -->(\d+)<!-- /count:prompts -->", readme)
    assert tools and set(tools) == {"61"}
    assert prompts and set(prompts) == {"11"}
    assert set(re.findall(r'"tool_count": (\d+)', readme)) == {"61"}
    for marker in ("tools", "prompts"):
        assert readme.count(f"<!-- {marker}:start -->") == 1
        assert readme.count(f"<!-- {marker}:end -->") == 1


def test_badges_follow_annotations(registry):
    by_name = {t.name: t for t in registry.tools}
    assert by_name["netlicensing_list_products"].badge == "R"
    assert by_name["netlicensing_preview_delete_product"].badge == "R"
    assert by_name["netlicensing_create_product"].badge == "W"
    assert by_name["netlicensing_validate_licensee"].badge == "W"
    assert by_name["netlicensing_delete_product"].badge == "D"
    # Spec defaults: no hints means not read-only and destructive.
    assert gen._badge({}) == "D"


def test_generation_is_deterministic(registry):
    first = gen.expected_files(ROOT, gen.collect())
    second = gen.expected_files(ROOT, gen.collect())
    assert first == second
    for text in first.values():
        assert "\r" not in text
        assert text.endswith("\n")


@pytest.mark.parametrize(
    "env",
    [{"MCP_READ_ONLY": "true"}, {"MCP_TOOLSETS": "licenses"}],
    ids=["read-only", "one-toolset"],
)
def test_output_ignores_tool_filter_env(monkeypatch, registry, env):
    baseline = gen.expected_files(ROOT, registry)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert gen.expected_files(ROOT, gen.collect()) == baseline


def test_server_json_names_every_toolset():
    assert gen.server_json_problems(ROOT) == []
    data = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    data["packages"][0]["environmentVariables"] = [
        {"name": "MCP_TOOLSETS", "description": "Comma-separated toolsets: products, or all"}
    ]
    assert len(gen.server_json_problems_from(data)) == 1


def test_docstring_split_is_indentation_independent():
    indented = "Summary line\n        continues.\n\n        Body.\n\n        Args:\n            a: First\n                more\n            b: Second\n        "
    flat = "Summary line\ncontinues.\n\nBody.\n\nArgs:\n    a: First\n        more\n    b: Second\n"
    assert gen._split_doc(indented) == gen._split_doc(flat)
    summary, body, args = gen._split_doc(flat)
    assert summary == "Summary line continues."
    assert body == "Summary line\ncontinues.\n\nBody."
    assert args == {"a": "First more", "b": "Second"}
