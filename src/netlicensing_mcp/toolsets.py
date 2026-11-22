"""
Toolsets and the registration filter
====================================
``MCP_TOOLSETS`` and ``MCP_READ_ONLY`` shrink the tool list a client sees.

- :data:`TOOLSETS` is the single table that puts every tool into exactly one
  toolset. The ``tool`` decorator in ``netlicensing_mcp.app`` refuses a tool
  that is missing here, so a new tool cannot be forgotten.
- :class:`ToolFilter` holds the parsed settings and decides per tool:
  toolsets filter first, then the read-only filter
  (``readOnlyHint=True`` only). ``netlicensing_server_info`` always passes.

The settings are read once, when ``netlicensing_mcp.app`` is imported.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from mcp.types import ToolAnnotations

logger = logging.getLogger(__name__)

ALWAYS_REGISTERED = "netlicensing_server_info"

# Toolset → tool names. Every tool is in exactly one toolset.
TOOLSETS: dict[str, tuple[str, ...]] = {
    "products": (
        "netlicensing_list_products",
        "netlicensing_get_product",
        "netlicensing_create_product",
        "netlicensing_preview_update_product",
        "netlicensing_update_product",
        "netlicensing_preview_delete_product",
        "netlicensing_delete_product",
    ),
    "bundles": (
        "netlicensing_list_bundles",
        "netlicensing_get_bundle",
        "netlicensing_create_bundle",
        "netlicensing_update_bundle",
        "netlicensing_preview_delete_bundle",
        "netlicensing_delete_bundle",
        "netlicensing_obtain_bundle",
    ),
    "modules": (
        "netlicensing_list_product_modules",
        "netlicensing_get_product_module",
        "netlicensing_create_product_module",
        "netlicensing_update_product_module",
        "netlicensing_preview_delete_product_module",
        "netlicensing_delete_product_module",
    ),
    "templates": (
        "netlicensing_list_license_templates",
        "netlicensing_get_license_template",
        "netlicensing_create_license_template",
        "netlicensing_preview_update_license_template",
        "netlicensing_update_license_template",
        "netlicensing_preview_delete_license_template",
        "netlicensing_delete_license_template",
    ),
    "licensees": (
        "netlicensing_list_licensees",
        "netlicensing_get_licensee",
        "netlicensing_create_licensee",
        "netlicensing_update_licensee",
        "netlicensing_preview_delete_licensee",
        "netlicensing_delete_licensee",
        "netlicensing_validate_licensee",
        "netlicensing_transfer_licenses",
    ),
    "licenses": (
        "netlicensing_list_licenses",
        "netlicensing_get_license",
        "netlicensing_create_license",
        "netlicensing_update_license",
        "netlicensing_preview_delete_license",
        "netlicensing_delete_license",
    ),
    "tokens": (
        "netlicensing_list_tokens",
        "netlicensing_get_token",
        "netlicensing_create_shop_token",
        "netlicensing_create_api_token",
        "netlicensing_preview_delete_token",
        "netlicensing_delete_token",
    ),
    "transactions": (
        "netlicensing_list_transactions",
        "netlicensing_get_transaction",
        "netlicensing_create_transaction",
        "netlicensing_update_transaction",
    ),
    "payments": (
        "netlicensing_list_payment_methods",
        "netlicensing_get_payment_method",
        "netlicensing_preview_update_payment_method",
        "netlicensing_update_payment_method",
    ),
    "system": (
        "netlicensing_list_licensing_models",
        "netlicensing_list_license_types",
        "netlicensing_list_countries",
        "netlicensing_server_info",
    ),
    "workflows": (
        "netlicensing_get_customer_health",
        "netlicensing_explain_validation",
    ),
}

TOOLSET_NAMES: tuple[str, ...] = tuple(TOOLSETS)


def _index(table: Mapping[str, tuple[str, ...]]) -> dict[str, str]:
    owner: dict[str, str] = {}
    for toolset, names in table.items():
        for name in names:
            if name in owner:
                raise ValueError(f"{name} is in toolsets {owner[name]!r} and {toolset!r}")
            owner[name] = toolset
    return owner


_TOOLSET_OF = _index(TOOLSETS)


def toolset_of(name: str) -> str | None:
    """The toolset of tool *name*, or ``None`` when it is not in :data:`TOOLSETS`."""
    return _TOOLSET_OF.get(name)


_TRUE = ("true", "1", "yes")
_FALSE = ("false", "0", "no")


@dataclass(frozen=True)
class ToolFilter:
    """Which tools to register.

    ``toolsets`` is ``None`` for all toolsets. ``read_only`` keeps only tools
    annotated ``readOnlyHint=True``. :data:`ALWAYS_REGISTERED` always passes.
    """

    toolsets: frozenset[str] | None = None
    read_only: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> ToolFilter:
        """Parse ``MCP_TOOLSETS`` and ``MCP_READ_ONLY`` from *environ*.

        ``MCP_TOOLSETS`` is a comma list, trimmed and case-insensitive. Unset,
        blank or containing ``all`` means every toolset. Unknown names are
        logged as warnings and ignored (also next to ``all``); if no valid
        name remains, all toolsets are used and that is logged too.
        ``MCP_READ_ONLY`` is on for ``true``, ``1`` or ``yes``; any other
        non-blank value other than ``false``, ``0`` or ``no`` leaves it off
        and logs a warning.
        """
        raw_read_only = environ.get("MCP_READ_ONLY", "").strip().lower()
        read_only = raw_read_only in _TRUE
        if raw_read_only and not read_only and raw_read_only not in _FALSE:
            logger.warning(
                "MCP_READ_ONLY: unrecognised value %r; read-only mode is OFF "
                "(use true, 1 or yes to enable it)",
                raw_read_only[:20],
            )
        requested = [part.strip().lower() for part in environ.get("MCP_TOOLSETS", "").split(",")]
        requested = [part for part in requested if part]
        unknown = [part for part in requested if part != "all" and part not in TOOLSETS]
        if unknown:
            logger.warning(
                "MCP_TOOLSETS: ignoring unknown toolset(s) %s; valid toolsets: %s, all",
                ", ".join(unknown),
                ", ".join(TOOLSET_NAMES),
            )
        if not requested or "all" in requested:
            return cls(None, read_only)
        valid = frozenset(part for part in requested if part in TOOLSETS)
        if not valid:
            logger.warning("MCP_TOOLSETS: no valid toolset left; registering all toolsets")
            return cls(None, read_only)
        return cls(valid, read_only)

    @property
    def is_restricted(self) -> bool:
        return self.toolsets is not None or self.read_only

    def allows(self, name: str, annotations: ToolAnnotations | None) -> bool:
        """Whether tool *name* with *annotations* gets registered."""
        if name == ALWAYS_REGISTERED:
            return True
        if self.toolsets is not None and toolset_of(name) not in self.toolsets:
            return False
        if self.read_only and not (annotations is not None and annotations.readOnlyHint is True):
            return False
        return True

    def toolset_list(self) -> list[str]:
        """The active toolsets in table order, or ``["all"]``."""
        if self.toolsets is None:
            return ["all"]
        return [name for name in TOOLSET_NAMES if name in self.toolsets]

    def instructions_note(self) -> str:
        """One line for the server instructions when a restriction is active, else ``""``."""
        if not self.is_restricted:
            return ""
        parts = []
        if self.toolsets is not None:
            parts.append(f"Only these toolsets are registered: {', '.join(self.toolset_list())}.")
        if self.read_only:
            parts.append(
                "Read-only mode: write tools are not available, so a preview_* result is "
                "impact analysis only (its confirmation token cannot be used here)."
            )
        parts.append(
            "Prompts, workflow suggested_actions and preview instructions may mention tools "
            "that are not registered here; skip those steps."
        )
        return "\n## Restricted tool list\n\n" + " ".join(parts) + "\n"
