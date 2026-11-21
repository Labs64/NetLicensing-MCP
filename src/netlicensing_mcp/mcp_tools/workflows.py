"""High-level workflow MCP tools (customer health, validation explanation)."""

from __future__ import annotations

from netlicensing_mcp.app import (
    _READONLY,
    _error,
    _json,
    tool,
)
from netlicensing_mcp.client import NetLicensingError
from netlicensing_mcp.tools import (
    licensees,
    licenses,
)
from netlicensing_mcp.workflows import customer_health as _customer_health


@tool(title="Get customer health", annotations=_READONLY)
async def netlicensing_get_customer_health(
    licensee_number: str,
    refresh_warning_level: bool = False,
    include_raw: bool = False,
) -> str:
    """Return a normalized health summary for one licensee.

    Combines licensee details, license list, and (optionally) a dry-run
    validation into a single CustomerHealth envelope with per-module rows,
    warnings, and suggested actions. This tool is READ-ONLY — it never
    modifies data or consumes quota.

    Args:
        licensee_number:       Licensee identifier (e.g. 'CUST-ACME').
        refresh_warning_level: When True, runs a dry-run validate_licensee to
                               get live warning levels and quota/session info.
                               Slightly slower but more accurate.
        include_raw:           When True, include the sanitized upstream
                               NetLicensing API responses (licensee, licenses,
                               validation) under 'raw'.
    """
    try:
        licensee = await licensees.get_licensee(licensee_number)
        licenses_payload = await licenses.list_all_licenses(licensee_number)
        validation = None
        if refresh_warning_level:
            validation = await licensees.validate_licensee(licensee_number, dry_run=True)
        envelope = _customer_health.build_health(licensee, licenses_payload, validation)
        if include_raw:
            envelope["raw"] = {
                "licensee": licensee,
                "licenses": licenses_payload,
                "validation": validation,
            }
        return _json(envelope)
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_get_customer_health")


@tool(title="Explain validation", annotations=_READONLY)
async def netlicensing_explain_validation(
    licensee_number: str,
    product_number: str = "",
    module_parameters: list[dict] | None = None,
    include_raw: bool = False,
) -> str:
    """Run a dry-run validation and return a plain-language explanation.

    Wraps validate_licensee with dryRun=true and translates the result into
    per-module status, explanations, and suggested_actions (renewal tokens,
    top-up flows, force-checkin advice). This tool is READ-ONLY — it never
    consumes floating sessions, quota, or node-lock slots.

    Note: module_parameters currently passes the first entry's fields only
    (single-module shorthand). Full multi-module indexed support is planned
    for a future release (P0.5).

    Args:
        licensee_number:   Licensee identifier (e.g. 'CUST-ACME').
        product_number:    Optional — scope validation to a single product.
        module_parameters: Optional per-module overrides. Each dict may
                           contain: product_module_number, node_secret,
                           session_id, action.
        include_raw:       When True, include the sanitized upstream
                           validate_licensee API response under 'raw'.
    """
    from netlicensing_mcp.workflows import validation_explain as _val_explain

    try:
        first = (module_parameters or [{}])[0]
        payload = await licensees.validate_licensee(
            licensee_number,
            product_number=product_number or None,
            product_module_number=first.get("product_module_number"),
            node_secret=first.get("node_secret"),
            session_id=first.get("session_id"),
            action=first.get("action"),
            dry_run=True,
        )
        envelope = _val_explain.explain_validation(payload)
        envelope["licensee_number"] = licensee_number
        if include_raw:
            envelope["raw"] = payload
        return _json(envelope)
    except NetLicensingError as exc:
        return _error(exc, "netlicensing_explain_validation")
