"""Registry metadata: server.json, glama.json, Dockerfile labels and the release workflow.

``server.json`` is published to the MCP Registry by the release workflow after
``sed "s/\\${VERSION}/<tag>/g"``. These tests apply the same substitution and
validate the result against the registry schema it declares (vendored in
``tests/fixtures/registry``, so no network is needed), and check that names and
descriptions agree across the places that carry them.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "registry"
REGISTRY_SCHEMA = FIXTURES / "server.schema.2025-12-11.json"
GLAMA_SCHEMA = FIXTURES / "glama.schema.json"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "netlicensing-release.yml"


def _schema() -> dict[str, Any]:
    return json.loads(REGISTRY_SCHEMA.read_text(encoding="utf-8"))


def _released(version: str) -> dict[str, Any]:
    """server.json as the release workflow publishes it for tag *version*."""
    text = (ROOT / "server.json").read_text(encoding="utf-8")
    return json.loads(text.replace("${VERSION}", version))


def _packages(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["registryType"]: p for p in data["packages"]}


def _allowed(schema: dict[str, Any], *defs: str) -> set[str]:
    names: set[str] = set()
    for name in defs:
        definition = schema["definitions"][name]
        names |= set(definition.get("properties", {}))
        for part in definition.get("allOf", []):
            if "$ref" in part:
                names |= _allowed(schema, part["$ref"].rsplit("/", 1)[1])
            names |= set(part.get("properties", {}))
    return names


def _dockerfile_labels() -> dict[str, str]:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    block = text.split("LABEL ", 1)[1].split("\n\n", 1)[0]
    return dict(re.findall(r'([\w.]+)="([^"]*)"', block))


def _workflow_labels() -> dict[str, str]:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    block = text.split("labels: |\n", 1)[1].split("\n\n", 1)[0]
    return dict(line.strip().split("=", 1) for line in block.splitlines() if "=" in line)


def test_release_workflow_still_substitutes_and_publishes():
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert 'sed -i "s/\\${VERSION}/${REF_NAME}/g" server.json' in text
    assert "mcp-publisher publish" in text


def test_server_json_declares_the_vendored_schema():
    data = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert data["$schema"] == _schema()["$id"]


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3-rc.1"])
def test_released_server_json_validates_against_registry_schema(version):
    validator = jsonschema.Draft7Validator(_schema())
    errors = [
        f"{'/'.join(map(str, e.path))}: {e.message}"
        for e in validator.iter_errors(_released(version))
    ]
    assert errors == []


def test_version_placeholders_land_in_the_right_fields():
    data = _released("9.8.7")
    assert "${" not in json.dumps(data)
    assert data["version"] == "9.8.7"
    packages = _packages(data)
    assert set(packages) == {"pypi", "oci"}
    assert packages["pypi"]["version"] == "9.8.7"
    # OCI carries the version in the image tag; the schema's `version` is for npm/PyPI/NuGet.
    assert packages["oci"]["identifier"] == "ghcr.io/labs64/netlicensing-mcp:9.8.7"
    assert "version" not in packages["oci"]


def test_server_json_uses_only_schema_field_names():
    """Unknown keys pass a plain schema check but the registry drops them (e.g. `required`)."""
    schema = _schema()
    data = _released("1.0.0")
    assert set(data) <= _allowed(schema, "ServerDetail")
    package_keys = _allowed(schema, "Package")
    variable_keys = _allowed(schema, "KeyValueInput")
    for package in data["packages"]:
        assert set(package) <= package_keys, package["registryType"]
        for variable in package["environmentVariables"]:
            assert set(variable) <= variable_keys, (package["registryType"], variable["name"])


def test_server_json_environment_variables():
    packages = _packages(_released("1.0.0"))
    assert packages["pypi"]["environmentVariables"] == packages["oci"]["environmentVariables"]
    variables = {v["name"]: v for v in packages["pypi"]["environmentVariables"]}
    assert variables["NETLICENSING_API_KEY"]["isRequired"] is True
    assert variables["NETLICENSING_API_KEY"]["isSecret"] is True
    assert [n for n, v in variables.items() if v.get("isRequired")] == ["NETLICENSING_API_KEY"]
    for name in ("NETLICENSING_ALLOW_DEMO", "MCP_VERBOSE", "MCP_READ_ONLY"):
        assert variables[name]["format"] == "boolean", name


def test_names_and_descriptions_agree():
    data = _released("1.0.0")
    labels = _dockerfile_labels()
    assert labels["io.modelcontextprotocol.server.name"] == data["name"]
    assert labels["org.opencontainers.image.title"] == data["title"]
    assert labels["org.opencontainers.image.description"] == data["description"]

    # docker/metadata-action would otherwise replace them with the GitHub repo's values.
    workflow = _workflow_labels()
    for key in (
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.url",
    ):
        assert workflow[key] == labels[key], key

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {data['name']} -->" in readme  # PyPI ownership check

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == _packages(data)["pypi"]["identifier"]
    assert project["description"].startswith(data["description"].rstrip("."))


def test_glama_json_validates():
    schema = json.loads(GLAMA_SCHEMA.read_text(encoding="utf-8"))
    data = json.loads((ROOT / "glama.json").read_text(encoding="utf-8"))
    assert data["$schema"] == schema["$id"]
    jsonschema.validate(data, schema)
