"""
Next-step hints for error blobs
===============================
:func:`error_hint` turns a :class:`~netlicensing_mcp.client.NetLicensingError`
(plus the name of the tool that hit it) into the extra keys of an error blob:

- ``hint`` — one actionable sentence (or two);
- ``suggested_actions`` — names of tools that help with the next step;
- ``retryable`` — whether the same call may succeed later unchanged;
- ``retry_after_seconds`` — only for ``429`` with a ``Retry-After`` header.

:func:`confirmation_hint` does the same for a rejected confirmation token.

The mapping follows what NetLicensing returns (API Conventions,
https://netlicensing.io/wiki/api-conventions, and the sandbox): a missing
entity is ``400`` with info id ``NotFoundException`` (``Requested licensee
does not exist.``), a duplicate number ``400`` ``DuplicateEntityException``,
a delete blocked by dependents ``400`` ``IllegalOperationException``
(``This product has Licensees.``), ``401`` bad credentials, ``402`` not in
the pricing plan, ``403`` key role too low, ``429`` rate limit with
``Retry-After``, ``500`` internal error. ``502`` / ``504`` and the ``503``
"no API key configured" come from ``client.py`` itself.

Hints never contain the error ``detail``, an API key or the base URL beyond
its host name: they are built from fixed text, tool names and the host only.
Both functions are pure apart from reading ``client.BASE_URL``.
"""

from __future__ import annotations

from collections.abc import Container
from typing import Any
from urllib.parse import urlsplit

from netlicensing_mcp import client
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.toolsets import TOOLSETS, toolset_of

_KNOWN_TOOLS = frozenset(name for names in TOOLSETS.values() for name in names)

# Entity key → (phrase used in NetLicensing messages and in hints, plural for list tools).
_ENTITIES: dict[str, tuple[str, str]] = {
    "product_module": ("product module", "product_modules"),
    "license_template": ("license template", "license_templates"),
    "payment_method": ("payment method", "payment_methods"),
    "licensee": ("licensee", "licensees"),
    "license": ("license", "licenses"),
    "product": ("product", "products"),
    "bundle": ("bundle", "bundles"),
    "token": ("token", "tokens"),
    "transaction": ("transaction", "transactions"),
}

# Toolset → the entity its tools act on (workflow tools take a licensee_number).
_TOOLSET_ENTITY: dict[str, str] = {
    "products": "product",
    "bundles": "bundle",
    "modules": "product_module",
    "templates": "license_template",
    "licensees": "licensee",
    "licenses": "license",
    "tokens": "token",
    "transactions": "transaction",
    "payments": "payment_method",
    "workflows": "licensee",
}

# Longest first, so "preview_delete_" wins over "delete_".
_VERBS = (
    "preview_delete",
    "preview_update",
    "create",
    "update",
    "delete",
    "get",
    "list",
    "obtain",
    "validate",
    "transfer",
    "explain",
)
_WRITE_VERBS = frozenset({"create", "update", "delete", "obtain", "validate", "transfer"})

_NO_KEY_PREFIX = "No NetLicensing API key configured"
_KEY_SETTINGS = (
    "NETLICENSING_API_KEY (stdio) or the X-NetLicensing-API-Key / "
    "Authorization: Bearer header (HTTP mode)"
)


def _verb(tool_name: str | None) -> str | None:
    if not tool_name:
        return None
    rest = tool_name.removeprefix("netlicensing_")
    for verb in _VERBS:
        if rest.startswith(verb + "_"):
            return verb
    return None


def _tool_entity(tool_name: str | None) -> str | None:
    toolset = toolset_of(tool_name) if tool_name else None
    return _TOOLSET_ENTITY.get(toolset) if toolset else None


def _message_entity(detail: str) -> str | None:
    """The entity a NetLicensing message names, matched against fixed phrases only."""
    text = detail.lower()
    for key, (phrase, _) in _ENTITIES.items():
        if f"requested {phrase} does not exist" in text:
            return key
        if f"{phrase} with the given number" in text:
            return key
    return None


class _Tools:
    """Builds tool names and keeps only those that exist (and are registered)."""

    def __init__(self, available: Container[str] | None) -> None:
        self._available = available

    def ok(self, name: str | None) -> str | None:
        if name is None or name not in _KNOWN_TOOLS:
            return None
        if self._available is not None and name not in self._available:
            return None
        return name

    def for_entity(self, verb: str, entity: str | None) -> str | None:
        if entity is None:
            return None
        if verb == "list":
            return self.ok(f"netlicensing_list_{_ENTITIES[entity][1]}")
        return self.ok(f"netlicensing_{verb}_{entity}")


def _host() -> str:
    return urlsplit(client.BASE_URL).hostname or "the NETLICENSING_BASE_URL host"


def _result(
    hint: str, actions: list[str | None], retryable: bool = False, **extra: Any
) -> dict[str, Any]:
    return {
        "hint": hint,
        "suggested_actions": [a for a in actions if a],
        "retryable": retryable,
        **extra,
    }


def _is_not_found(exc: NetLicensingError) -> bool:
    if exc.status_code == 404 or "NotFoundException" in exc.info_ids:
        return True
    text = exc.detail.lower()
    return exc.status_code == 400 and (
        "does not exist" in text or "with the given number not found" in text
    )


def _state_check(verb: str | None, entity: str | None, tools: _Tools) -> tuple[str, str | None]:
    """For a failed write: sentence + tool to check whether it was applied anyway."""
    if verb not in _WRITE_VERBS:
        return "", None
    if verb in ("update", "delete"):
        check = tools.for_entity("get", entity)
    elif verb in ("obtain", "transfer"):
        check = tools.for_entity("list", "license")
    elif verb == "create":
        check = tools.for_entity("list", entity)
    else:
        check = None
    with_tool = f" with {check}" if check else ""
    return (
        f" The request may have been applied before the error: check the current state"
        f"{with_tool} before retrying.",
        check,
    )


def _server_error(
    exc: NetLicensingError, verb: str | None, entity: str | None, tools: _Tools
) -> dict[str, Any]:
    host = _host()
    status = exc.status_code
    if status == 504:
        hint = (
            f"The request to the NetLicensing API at {host} timed out; "
            "this is usually temporary, retry later."
        )
    elif status == 502 and exc.detail.startswith("Could not reach"):
        hint = (
            f"Could not reach the NetLicensing API at {host}: check the network and "
            "NETLICENSING_BASE_URL, then retry."
        )
        if host == "go.netlicensing.io":
            hint += (
                " If go.netlicensing.io cannot be resolved, NetLicensing documents "
                "netlicensing.labs64.com as the backup host."
            )
    elif status == 502:
        hint = (
            f"{host} did not answer with a NetLicensing JSON response (a proxy, or "
            "NETLICENSING_BASE_URL not pointing at the REST API?): check the base URL, then retry."
        )
    else:
        hint = (
            f"The NetLicensing API at {host} failed with HTTP {status}; this is usually "
            "temporary: retry later, and contact NetLicensing support if it persists."
        )
    sentence, check = _state_check(verb, entity, tools)
    return _result(hint + sentence, [check], retryable=True)


def error_hint(
    exc: NetLicensingError,
    tool_name: str | None = None,
    *,
    available: Container[str] | None = None,
) -> dict[str, Any]:
    """Hint keys for the error blob of *exc* raised in tool *tool_name*.

    *available*, when given, limits ``suggested_actions`` (and the tool names
    in ``hint``) to these tool names, e.g. the tools registered under
    ``MCP_TOOLSETS`` / ``MCP_READ_ONLY``. Suggestions are always real tool
    names from ``toolsets.TOOLSETS``.
    """
    tools = _Tools(available)
    status = exc.status_code
    verb = _verb(tool_name)
    entity = _message_entity(exc.detail) or _tool_entity(tool_name)
    phrase = _ENTITIES[entity][0] if entity else "entity"

    if status == 503 and exc.detail.startswith(_NO_KEY_PREFIX):
        return _result(
            f"No API key reached this server: set {_KEY_SETTINGS}. "
            "For the sandbox only, set NETLICENSING_ALLOW_DEMO=true.",
            [],
        )
    if status == 401:
        return _result(
            "NetLicensing rejected the credentials (missing or invalid API key): "
            f"check {_KEY_SETTINGS}.",
            [],
        )
    if status == 402:
        return _result(
            "This operation is not included in your NetLicensing pricing plan; "
            "it cannot succeed until the plan includes it.",
            [],
        )
    if status == 403:
        return _result(
            "The API key's role does not allow this operation (roles, lowest first: LICENSEE, "
            "ANALYTICS, OPERATION, MAINTENANCE, ADMIN; reads need ANALYTICS, writes to licensees "
            "and licenses OPERATION, writes to products, modules and templates MAINTENANCE): "
            "use a key with a higher role in "
            f"{_KEY_SETTINGS}.",
            [],
        )
    if _is_not_found(exc):
        lookup = tools.for_entity("list", entity)
        with_tool = f", or look it up with {lookup}" if lookup else ""
        return _result(
            f"The {phrase} was not found. Identifiers are case-sensitive: "
            f"check the number{with_tool}.",
            [lookup],
        )
    if verb == "delete" and (status == 409 or "IllegalOperationException" in exc.info_ids):
        preview = tools.for_entity("preview_delete", entity)
        update = tools.for_entity("update", entity)
        review = f" Review them with {preview}." if preview else ""
        return _result(
            f"NetLicensing refused to delete the {phrase} because other entities still depend "
            f"on it (see 'detail').{review} Pass force_cascade=true only if the user explicitly "
            "asks to delete all dependents too; to disable rather than remove, prefer "
            "deactivating (active=false) over deleting.",
            [preview, update],
        )
    text = exc.detail.lower()
    if (
        "DuplicateEntityException" in exc.info_ids
        or "already exists" in text
        or (status == 409 and verb == "create")
    ):
        get = tools.for_entity("get", entity)
        update = tools.for_entity("update", entity)
        existing = ", ".join(t for t in (get, update) if t)
        use_existing = f", or work with the existing {phrase} ({existing})" if existing else ""
        return _result(
            f"A {phrase} with this number already exists: use another number or leave "
            f"number empty to let NetLicensing generate one{use_existing}.",
            [get, update],
        )
    if status == 429:
        extra: dict[str, Any] = {}
        wait = "Wait"
        if exc.retry_after is not None:
            extra["retry_after_seconds"] = exc.retry_after
            wait = f"Wait {exc.retry_after} seconds (Retry-After)"
        return _result(
            "NetLicensing is busy and this account is above its plan's API rate limit. "
            f"{wait} and retry the same call; a 429 says nothing about license validity.",
            [],
            retryable=True,
            **extra,
        )
    if status >= 500:
        return _server_error(exc, verb, entity, tools)
    if status in (400, 409, 422):
        return _result(
            "NetLicensing rejected the request; its own message is in 'detail'. Check the "
            "required fields and value formats in this tool's description, then call it again "
            "with corrected arguments.",
            [],
        )
    return _result(f"NetLicensing returned HTTP {status}; its message is in 'detail'.", [])


def confirmation_hint(
    tool_name: str | None = None, *, available: Container[str] | None = None
) -> dict[str, Any]:
    """Hint keys for a rejected ``confirm_token`` (``safety.validate_and_consume``)."""
    tools = _Tools(available)
    preview = None
    if tool_name:
        rest = tool_name.removeprefix("netlicensing_")
        preview = tools.ok(f"netlicensing_preview_{rest}")
    source = preview or "the matching preview tool (or this tool without confirm_token)"
    return _result(
        "The confirmation token was not accepted (unknown, already used, older than 5 minutes, "
        f"or issued for another operation, target or API key). Get a new one from {source}, "
        "show the preview to the user and repeat this call with the new token once they confirm.",
        [preview],
    )
