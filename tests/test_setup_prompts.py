"""Setup and troubleshooting prompts (Task 8) and prompt/tool consistency.

Every prompt (audit and setup) is rendered through the real FastMCP server
with sample arguments. The consistency tests read the rendered text and check
that each ``netlicensing_*`` name is a registered tool, and that each argument
written as ``netlicensing_x(arg=...)`` or ``` `netlicensing_x` with arg=...```
is in that tool's input schema, so prompts cannot drift from the tools.
"""

from __future__ import annotations

import inspect
import json
import re

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import Message
from mcp.types import PromptMessage, TextContent

# server first: importing it registers the tools in their canonical order
# (tests/test_tool_registry_snapshot.py checks that order).
import netlicensing_mcp.server as server
from netlicensing_mcp.prompts.setup import register_setup_prompts

# Prompt name -> argument names, in signature order (fixed by the task brief).
SETUP_PROMPTS: dict[str, list[str]] = {
    "setup_subscription_product": ["product_name", "plans"],
    "setup_trial": ["product_number", "trial_days"],
    "onboard_customer": [
        "customer_name",
        "product_number",
        "licensee_number",
        "module_number",
        "license_template_number",
    ],
    "migrate_customer": ["from_licensee_number", "to_licensee_number"],
    "troubleshoot_validation": ["licensee_number", "product_number", "product_module_number"],
    "issue_api_key": ["purpose"],
}

REQUIRED_ARGS: dict[str, set[str]] = {
    "setup_subscription_product": {"product_name", "plans"},
    "setup_trial": {"product_number"},
    "onboard_customer": {"customer_name", "product_number"},
    "migrate_customer": {"from_licensee_number", "to_licensee_number"},
    "troubleshoot_validation": {"licensee_number"},
    "issue_api_key": {"purpose"},
}

AUDIT_PROMPTS = ["audit_full", "audit_customer", "audit_expiry", "audit_cleanup", "audit_anomaly"]

# Sample arguments (MCP sends prompt arguments as strings). Several variants per
# prompt so every optional branch of the text is rendered at least once.
SAMPLE_ARGS: dict[str, list[dict[str, str]]] = {
    "audit_full": [{"product_number": "P001"}],
    "audit_customer": [{"licensee_number": "I001"}],
    "audit_expiry": [{"product_number": "P001", "days_threshold": "45"}],
    "audit_cleanup": [{"product_number": "P001"}],
    "audit_anomaly": [{"product_number": "P001"}],
    "setup_subscription_product": [
        {"product_name": "Acme Cloud", "plans": "1 MONTH 9.99 EUR; 1 YEAR 99.00 EUR"}
    ],
    "setup_trial": [{"product_number": "P001"}, {"product_number": "P001", "trial_days": "30"}],
    "onboard_customer": [
        {"customer_name": "Acme Corp", "product_number": "P001"},
        {"customer_name": "Acme Corp", "product_number": "P001", "licensee_number": "I042"},
        {"customer_name": "Acme Corp", "product_number": "P001", "module_number": "M01"},
        {
            "customer_name": "Acme Corp",
            "product_number": "P001",
            "license_template_number": "LT01",
        },
    ],
    "migrate_customer": [{"from_licensee_number": "I001", "to_licensee_number": "I002"}],
    "troubleshoot_validation": [
        {"licensee_number": "I001"},
        {"licensee_number": "I001", "product_number": "P001", "product_module_number": "M01"},
    ],
    "issue_api_key": [{"purpose": "embed in the desktop client for license validation"}],
}


def _json_wrapped_text(text: str) -> str | None:
    """The inner text when *text* is a JSON dump of a PromptMessage, else None.

    The audit prompts return ``mcp.types.PromptMessage`` objects, which FastMCP
    does not recognise as messages: it sends them as a JSON dump of the object.
    """
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("content"), dict):
        inner = data["content"].get("text")
        return inner if isinstance(inner, str) else None
    return None


async def _render(name: str, args: dict[str, str]) -> str:
    result = await server.mcp.get_prompt(name, args)
    assert result.messages, f"{name} rendered no messages"
    texts = []
    for msg in result.messages:
        assert isinstance(msg, PromptMessage) and msg.role == "user"
        assert isinstance(msg.content, TextContent)
        text = msg.content.text
        inner = _json_wrapped_text(text)
        if name in SETUP_PROMPTS:
            # The setup prompts send their text as the message text.
            assert inner is None, f"{name} sent a JSON-wrapped message"
        elif inner is not None:
            text = inner
        assert text.strip()
        texts.append(text)
    return "\n".join(texts)


async def _all_rendered() -> dict[str, list[str]]:
    return {
        name: [await _render(name, args) for args in variants]
        for name, variants in SAMPLE_ARGS.items()
    }


async def _tool_schemas() -> dict[str, set[str]]:
    return {
        t.name: set((t.inputSchema or {}).get("properties", {}))
        for t in await server.mcp.list_tools()
    }


# ── Registration ─────────────────────────────────────────────────────────────


async def test_setup_prompts_are_registered_on_the_server():
    prompts = {p.name: p for p in await server.mcp.list_prompts()}
    for name, args in SETUP_PROMPTS.items():
        assert name in prompts, name
        p = prompts[name]
        assert p.description and p.description.strip(), name
        assert p.title, name
        assert [a.name for a in p.arguments or []] == args, name
        assert {a.name for a in p.arguments or [] if a.required} == REQUIRED_ARGS[name], name
        for a in p.arguments or []:
            assert a.description and a.description.strip(), f"{name}.{a.name}"


async def test_server_lists_audit_then_setup_prompts():
    names = [p.name for p in await server.mcp.list_prompts()]
    assert names == AUDIT_PROMPTS + list(SETUP_PROMPTS)


def test_register_setup_prompts_on_a_fresh_server():
    fresh = FastMCP("test-server")
    register_setup_prompts(fresh)
    names = [p.name for p in fresh._prompt_manager.list_prompts()]
    assert names == list(SETUP_PROMPTS)


def test_setup_prompt_functions_have_typed_arguments():
    fresh = FastMCP("test-server")
    register_setup_prompts(fresh)
    for prompt in fresh._prompt_manager.list_prompts():
        sig = inspect.signature(prompt.fn)
        for param in sig.parameters.values():
            assert param.annotation is not inspect.Parameter.empty, (
                f"{prompt.name}.{param.name} has no type annotation"
            )


# ── Rendering ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", list(SAMPLE_ARGS))
async def test_every_prompt_renders_with_sample_args(name):
    for args in SAMPLE_ARGS[name]:
        text = await _render(name, args)
        for value in args.values():
            assert value in text, f"{name}: argument value {value!r} not in the text"


async def test_setup_prompts_render_as_plain_text_prompt_messages():
    fresh = FastMCP("test-server")
    register_setup_prompts(fresh)
    for prompt in fresh._prompt_manager.list_prompts():
        args = SAMPLE_ARGS[prompt.name][0]
        msgs = prompt.fn(**args)
        assert isinstance(msgs, list) and msgs
        assert all(isinstance(m, Message) and m.role == "user" for m in msgs)
        result = await fresh.get_prompt(prompt.name, args)
        assert [type(m) for m in result.messages] == [PromptMessage] * len(msgs)
        text = result.messages[0].content.text
        assert text.startswith("You are a Labs64 NetLicensing assistant"), text[:80]


async def test_setup_trial_coerces_and_checks_trial_days():
    text = await _render("setup_trial", {"product_number": "P9", "trial_days": "21"})
    assert "time_volume=21" in text
    default = await _render("setup_trial", {"product_number": "P9"})
    assert "time_volume=14" in default
    with pytest.raises(Exception):
        await server.mcp.get_prompt("setup_trial", {"product_number": "P9", "trial_days": "0"})


async def test_optional_arguments_change_the_steps():
    by_number = await _render(
        "onboard_customer",
        {"customer_name": "Acme", "product_number": "P1", "licensee_number": "I042"},
    )
    assert 'netlicensing_get_licensee(licensee_number="I042")' in by_number
    by_template = await _render(
        "onboard_customer",
        {"customer_name": "Acme", "product_number": "P1", "license_template_number": "LT7"},
    )
    assert 'netlicensing_get_license_template(template_number="LT7")' in by_template
    by_module = await _render(
        "onboard_customer",
        {"customer_name": "Acme", "product_number": "P1", "module_number": "M7"},
    )
    assert 'netlicensing_list_license_templates(module_number="M7")' in by_module
    scoped = await _render(
        "troubleshoot_validation",
        {"licensee_number": "I1", "product_number": "P1", "product_module_number": "M1"},
    )
    assert 'product_number="P1"' in scoped
    assert '"product_module_number": "M1"' in scoped


# ── Workflow content (safety rules) ──────────────────────────────────────────


async def test_migrate_customer_previews_before_transfer():
    text = await _render(
        "migrate_customer", {"from_licensee_number": "I001", "to_licensee_number": "I002"}
    )
    transfer = text.index(
        'netlicensing_transfer_licenses(from_licensee_number="I001", to_licensee_number="I002")'
    )
    for preview in (
        'netlicensing_list_licenses(licensee_number="I001")',
        'netlicensing_list_licenses(licensee_number="I002")',
        'netlicensing_get_licensee(licensee_number="I001")',
        'netlicensing_get_licensee(licensee_number="I002")',
    ):
        assert text.index(preview) < transfer, preview
    assert text.index("explicit confirmation") < transfer
    assert "markedForTransfer" in text


async def test_issue_api_key_handles_the_one_time_secret():
    text = await _render("issue_api_key", {"purpose": "CI reporting"})
    assert "netlicensing_create_api_token(api_key_role=" in text
    assert "shown_once" in text
    assert "ONCE" in text
    assert "Do not repeat" in text
    for role in (
        "ROLE_APIKEY_LICENSEE",
        "ROLE_APIKEY_ANALYTICS",
        "ROLE_APIKEY_OPERATION",
        "ROLE_APIKEY_MAINTENANCE",
        "ROLE_APIKEY_ADMIN",
    ):
        assert role in text
    # Least privilege: a confirmation step comes before the create call.
    assert text.index("Confirm") < text.index("netlicensing_create_api_token(")


async def test_troubleshoot_validation_uses_read_only_diagnostics_first():
    text = await _render("troubleshoot_validation", {"licensee_number": "I001"})
    order = [
        "netlicensing_server_info(",
        'netlicensing_get_licensee(licensee_number="I001")',
        'netlicensing_explain_validation(licensee_number="I001"',
        'netlicensing_validate_licensee(licensee_number="I001"',
        'netlicensing_get_customer_health(licensee_number="I001"',
    ]
    positions = [text.index(s) for s in order]
    assert positions == sorted(positions)
    # Every validate call in this prompt is a dry run.
    for call in re.findall(r"netlicensing_validate_licensee\([^)]*\)", text):
        assert "dry_run=true" in call, call


async def test_setup_prompts_use_only_documented_licensing_models():
    sub = await _render("setup_subscription_product", SAMPLE_ARGS["setup_subscription_product"][0])
    assert 'licensing_model="Subscription"' in sub
    assert 'license_type="TIMEVOLUME"' in sub
    trial = await _render("setup_trial", {"product_number": "P1", "trial_days": "14"})
    assert 'licensing_model="TryAndBuy"' in trial
    assert 'license_type="TIMEVOLUME"' in trial and 'license_type="FEATURE"' in trial
    # Every licensing_model / license_type value written in a call is one the
    # tool docs list.
    models = {
        "TryAndBuy",
        "Subscription",
        "Rental",
        "Floating",
        "MultiFeature",
        "PayPerUse",
        "PricingTable",
        "Quota",
        "NodeLocked",
    }
    types = {"FEATURE", "TIMEVOLUME", "FLOATING", "QUANTITY"}
    rendered = await _all_rendered()
    for texts in rendered.values():
        for text in texts:
            assert set(re.findall(r'licensing_model="(\w+)"', text)) <= models
            assert set(re.findall(r'license_type="(\w+)"', text)) <= types
            assert set(re.findall(r'time_volume_period="(\w+)"', text)) <= {
                "DAY",
                "WEEK",
                "MONTH",
                "YEAR",
            }


async def test_no_prompt_calls_a_tool_with_force_cascade():
    rendered = await _all_rendered()
    for name, texts in rendered.items():
        for text in texts:
            for call in re.findall(r"netlicensing_\w+\([^)]*\)", text):
                assert "force_cascade" not in call, f"{name}: {call}"


async def test_setup_prompts_carry_the_safety_rules():
    rendered = await _all_rendered()
    for name in SETUP_PROMPTS:
        for text in rendered[name]:
            assert "## Safety rules" in text, name
            assert "force_cascade" in text, name
            assert "netlicensing_preview_delete_" in text, name


# ── Consistency: prompts ↔ registered tools ──────────────────────────────────

_TOOL_TOKEN = re.compile(r"netlicensing_\w+\*?")
_CALL = re.compile(r"(netlicensing_\w+)\(([^)]*)\)")
_WITH = re.compile(r"`(netlicensing_\w+)`\s+with\s+([^\n]*)")
_ARG = re.compile(r"(?<![\w\"'])(\w+)\s*=")


def _tool_tokens(text: str) -> set[str]:
    return set(_TOOL_TOKEN.findall(text))


def _arg_references(text: str) -> list[tuple[str, str]]:
    refs = []
    for pattern in (_CALL, _WITH):
        for tool_name, arg_text in pattern.findall(text):
            for arg in _ARG.findall(arg_text):
                refs.append((tool_name, arg))
    return refs


async def test_every_tool_named_in_a_prompt_is_registered():
    schemas = await _tool_schemas()
    rendered = await _all_rendered()
    seen: set[str] = set()
    for name, texts in rendered.items():
        for text in texts:
            for token in _tool_tokens(text):
                seen.add(token)
                if token.endswith("*"):
                    prefix = token[:-1]
                    assert any(t.startswith(prefix) for t in schemas), f"{name}: {token}"
                else:
                    assert token in schemas, f"{name}: {token} is not a registered tool"
    # Non-vacuous: the prompts reference a good part of the tool surface.
    assert len(seen) >= 30


async def test_every_argument_named_in_a_prompt_exists_on_the_tool():
    schemas = await _tool_schemas()
    rendered = await _all_rendered()
    count = 0
    for name, texts in rendered.items():
        for text in texts:
            for tool_name, arg in _arg_references(text):
                assert tool_name in schemas, f"{name}: {tool_name}"
                assert arg in schemas[tool_name], (
                    f"{name}: {tool_name} has no argument {arg!r} "
                    f"(has {sorted(schemas[tool_name])})"
                )
                count += 1
    # Non-vacuous: the parser found the argument references.
    assert count >= 60


def test_consistency_parser_catches_drift():
    # The checks above would fail on an unknown tool or argument.
    text = (
        'Call `netlicensing_get_product` with product_numbr="P1".\n'
        'Then netlicensing_create_licensee(product_number="P1", nam="x").\n'
        "Then `netlicensing_frobnicate`."
    )
    assert ("netlicensing_get_product", "product_numbr") in _arg_references(text)
    assert ("netlicensing_create_licensee", "nam") in _arg_references(text)
    assert "netlicensing_frobnicate" in _tool_tokens(text)
    # JSON-style keys inside a call are not mistaken for keyword arguments.
    assert _arg_references('netlicensing_x(a=[{"b": 1}], c="d=e")') == [
        ("netlicensing_x", "a"),
        ("netlicensing_x", "c"),
    ]
