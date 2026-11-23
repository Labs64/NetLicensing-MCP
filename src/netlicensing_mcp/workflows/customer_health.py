"""P1.8 — Customer Health Summary synthesiser.

Pure module — no I/O. The MCP tool wrapper in mcp_tools/workflows.py fetches the three
upstream payloads and passes them here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from netlicensing_mcp.responses import console_url, feature_results
from netlicensing_mcp.workflows.validation_explain import module_state
from netlicensing_mcp.workflows._thresholds import (
    CRITICAL_DAYS,
    WARN_DAYS,
    WARN_QUOTA_PCT,
)


def _props(item: dict) -> dict[str, str]:
    return {
        p["name"]: p["value"]
        for p in item.get("property", [])
        if isinstance(p, dict) and "name" in p and "value" in p
    }


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _days_until(expires_str: str, now: datetime) -> int | None:
    dt = _parse_iso(expires_str)
    if dt is None:
        return None
    delta = dt - now
    return int(delta.total_seconds() // 86400)


def _group_licenses_by_module(licenses: dict) -> dict[str, list[dict]]:
    items_obj = licenses.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    groups: dict[str, list[dict]] = {}
    for item in item_list:
        if not isinstance(item, dict):
            continue
        p = _props(item)
        mod = p.get("productModuleNumber", "__unknown__")
        groups.setdefault(mod, []).append(item)
    return groups


def _validation_by_module(validation: dict | None) -> dict[str, dict[str, str]]:
    if not validation:
        return {}
    items_obj = validation.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    result: dict[str, dict[str, str]] = {}
    for item in item_list:
        if not isinstance(item, dict):
            continue
        p = _props(item)
        mod = p.get("productModuleNumber", "")
        if mod:
            result[mod] = p
    return result


def _features_by_module(validation: dict | None) -> dict[str, list[dict[str, Any]]]:
    """MultiFeature results per module number of a validate response."""
    items_obj = (validation or {}).get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    out: dict[str, list[dict[str, Any]]] = {}
    for item in item_list if isinstance(item_list, list) else []:
        if isinstance(item, dict):
            mod = _props(item).get("productModuleNumber", "")
            feats = feature_results(item)
            if mod and feats:
                out[mod] = feats
    return out


def _module_row(
    module_number: str,
    license_group: list[dict],
    val_props: dict[str, str],
    now: datetime,
) -> dict[str, Any]:
    row: dict[str, Any] = {"module_number": module_number}

    # Pull names/model from first license if present.
    first_props = _props(license_group[0]) if license_group else {}
    module_name = first_props.get("productModuleName") or val_props.get("productModuleName") or ""
    if module_name:
        row["module_name"] = module_name

    licensing_model = val_props.get("licensingModel") or first_props.get("licensingModel") or ""
    if licensing_model:
        row["licensing_model"] = licensing_model

    # valid from validation
    # Always present: None means "not reported", never assumed true.
    valid_str = val_props.get("valid", "")
    row["valid"] = valid_str.lower() == "true" if valid_str else None

    # warning_level from validation
    wl = val_props.get("warningLevel", "")
    if wl:
        row["warning_level"] = wl

    row["license_count"] = len(license_group)

    # Model-specific fields from validation payload.
    model_lower = re.sub(r"[\s_-]", "", licensing_model).lower()

    if "subscription" in model_lower or "timevolume" in model_lower:
        expires_str = val_props.get("expires") or val_props.get("expirationTime") or ""
        if not expires_str:
            # Fall back to the earliest expiry on the licenses themselves.
            candidates = [
                _props(lic).get("expires", "")
                for lic in license_group
                if _props(lic).get("expires")
            ]
            expires_str = min(candidates) if candidates else ""
        if expires_str:
            row["expires_at"] = expires_str
            days = _days_until(expires_str, now)
            if days is not None:
                row["expires_in_days"] = days

    elif "payperuse" in model_lower:
        for key, out in [("quota", "quota_total"), ("quotaTotal", "quota_total")]:
            if key in val_props:
                try:
                    row["quota_total"] = int(val_props[key])
                except ValueError:
                    pass
                break
        for key in ("quotaUsed", "usedQuantity"):
            if key in val_props:
                try:
                    row["quota_used"] = int(val_props[key])
                except ValueError:
                    pass
                break
        if "quota_total" in row and "quota_used" in row:
            row["quota_remaining"] = row["quota_total"] - row["quota_used"]
            if row["quota_total"] > 0:
                row["quota_pct"] = round(row["quota_used"] / row["quota_total"], 2)

    elif "floating" in model_lower:
        for key in ("maxSessions", "maxCheckouts"):
            if key in val_props:
                try:
                    row["max_sessions"] = int(val_props[key])
                except ValueError:
                    pass
                break
        for key in ("activeSessions", "activeCheckouts", "checkedOutQuantity"):
            if key in val_props:
                try:
                    row["active_sessions"] = int(val_props[key])
                except ValueError:
                    pass
                break

    # A Floating module validates only for a given session. Without session data in the
    # reply, valid=false cannot tell "no free seat" from "no session was requested",
    # so the module is reported as unknown instead of invalid.
    if (
        "floating" in model_lower
        and row.get("valid") is False
        and row.get("max_sessions") is None
        and row.get("active_sessions") is None
    ):
        row["valid"] = None
        row["session_required"] = True

    return row


def _invalid_modules(modules: list[dict]) -> list[str]:
    """Module numbers whose validation result is ``valid: false``."""
    return [m.get("module_number", "") for m in modules if m.get("valid") is False]


def _validation_infos(validation: dict | None) -> list[str]:
    """ERROR / WARNING ``infos`` messages from a validate response."""
    if not validation:
        return []
    infos = validation.get("infos")
    info_list = infos.get("info", []) if isinstance(infos, dict) else []
    if not isinstance(info_list, list):
        return []
    return [
        str(i.get("value", ""))
        for i in info_list
        if isinstance(i, dict)
        and str(i.get("type", "")).upper() in ("ERROR", "WARNING")
        and i.get("value")
    ]


_MODULE_IN_INFO = re.compile(r"[Pp]roduct module '([^']+)'")


def _info_warning(msg: str) -> str:
    """Prefix an API info with its module number when the message names one."""
    m = _MODULE_IN_INFO.search(msg)
    return f"Module {m.group(1)}: {msg}" if m else msg


def _overall_status_from_validation(modules: list[dict]) -> str:
    if _invalid_modules(modules):
        return "critical"
    has_red = any(m.get("warning_level") == "RED" for m in modules)
    has_yellow = any(m.get("warning_level") == "YELLOW" for m in modules)
    if has_red:
        return "critical"
    if has_yellow:
        return "warning"
    return "ok"


def _overall_status_from_heuristics(modules: list[dict], licensee_active: bool) -> str:
    if not licensee_active:
        return "warning"
    for m in modules:
        days = m.get("expires_in_days")
        if days is not None:
            if days <= CRITICAL_DAYS:
                return "critical"
    for m in modules:
        days = m.get("expires_in_days")
        if days is not None:
            if days <= WARN_DAYS:
                return "warning"
    return "ok"


def _build_warnings(modules: list[dict], infos: list[str] | None = None) -> list[str]:
    msgs = []
    for m in modules:
        mno = m.get("module_number", "")
        if m.get("valid") is False:
            msgs.append(f"Module {mno}: validation result is invalid.")
        if m.get("session_required"):
            msgs.append(
                f"Module {mno}: Floating modules validate only for a session; "
                "no session id was supplied, so its validity is unknown."
            )
        days = m.get("expires_in_days")
        if days is not None and days <= WARN_DAYS:
            if days < 0:
                msgs.append(f"Module {mno}: subscription has expired.")
            else:
                msgs.append(f"Module {mno}: subscription expires in {days} days.")
        pct = m.get("quota_pct")
        if pct is not None and pct >= WARN_QUOTA_PCT:
            msgs.append(f"Module {mno}: {int(pct * 100)}% of pay-per-use quota consumed.")
        max_s = m.get("max_sessions")
        active_s = m.get("active_sessions")
        if max_s is not None and active_s is not None and active_s >= max_s:
            msgs.append(f"Module {mno}: floating sessions saturated ({active_s}/{max_s}).")
    for info in infos or []:
        msg = _info_warning(info)
        if msg not in msgs and info not in msgs:
            msgs.append(msg)
    return msgs


def _build_suggested_actions(
    modules: list[dict],
    licensee_number: str,
    licensee_active: bool,
) -> list[str]:
    actions: list[str] = []
    if not licensee_active:
        actions.append(f"Re-activate licensee {licensee_number}.")
    for m in modules:
        mno = m.get("module_number", "")
        if m.get("valid") is False:
            actions.append(
                f"Run netlicensing_explain_validation for {licensee_number} (module {mno})."
            )
        days = m.get("expires_in_days")
        if days is not None:
            if days < 0:
                actions.append(f"Renew expired subscription for {licensee_number} (module {mno}).")
            elif days <= WARN_DAYS:
                actions.append(f"Send a renewal token for {licensee_number} (module {mno}).")
        pct = m.get("quota_pct")
        if pct is not None and pct >= WARN_QUOTA_PCT:
            actions.append(f"Trigger a top-up flow for {licensee_number} (module {mno}).")
        max_s = m.get("max_sessions")
        active_s = m.get("active_sessions")
        if max_s is not None and active_s is not None and active_s >= max_s:
            actions.append(
                f"Free a floating seat for {licensee_number} (module {mno}) — sessions saturated."
            )
    return actions


def _summary_line(
    modules: list[dict],
    counts: dict[str, int],
    licensee_active: bool,
    overall_status: str,
    validation_run: bool = False,
) -> str:
    if not licensee_active:
        return f"Licensee is inactive — {counts['total_licenses']} licenses on record."
    if (
        overall_status == "unknown"
        and any(m.get("valid") is None and "state" in m for m in modules)
        and validation_run
    ):
        missing = [m.get("module_number", "") for m in modules if m.get("valid") is None]
        return (
            f"Health unknown: {len(missing)} module(s) returned no validity result "
            f"({', '.join(missing)})."
        )
    if overall_status == "unknown":
        return (
            "Health unknown: live validation was not run, and license counts alone do not "
            f"show whether a license is valid ({counts['modules']} modules, "
            f"{counts['total_licenses']} licenses on record). "
            "Call again with refresh_warning_level=true."
        )
    invalid = _invalid_modules(modules)
    if (
        overall_status == "ok"
        and not invalid
        and not any(m.get("state") == "degraded" for m in modules)
    ):
        return f"All {counts['modules']} modules are healthy."
    parts = []
    degraded = [m.get("module_number", "") for m in modules if m.get("state") == "degraded"]
    if degraded:
        parts.append(f"module(s) {', '.join(degraded)} valid but no feature is valid")
    if len(invalid) == 1:
        parts.append(f"Module {invalid[0]} is invalid")
    elif invalid:
        parts.append(f"Modules {', '.join(invalid)} are invalid")
    for m in modules:
        days = m.get("expires_in_days")
        mno = m.get("module_number", "")
        if days is not None and days < 0:
            parts.append(f"subscription expired (module {mno})")
        elif days is not None and days <= WARN_DAYS:
            parts.append(f"subscription expiring in {days} days (module {mno})")
        pct = m.get("quota_pct")
        if pct is not None and pct >= WARN_QUOTA_PCT:
            parts.append(f"quota at {int(pct * 100)}% usage (module {mno})")
        max_s = m.get("max_sessions")
        active_s = m.get("active_sessions")
        if max_s is not None and active_s is not None and active_s >= max_s:
            parts.append(f"floating sessions saturated (module {mno})")
    if parts:
        # Not str.capitalize(): it lowercases the rest, mangling module numbers.
        return "; ".join(p[:1].upper() + p[1:] for p in parts) + "."
    return f"{counts['modules']} modules active."


def build_health(
    licensee: dict,
    licenses: dict,
    validation: dict | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a CustomerHealth envelope from raw NetLicensing API payloads.

    Args:
        licensee:   Response from GET /licensee/{n}.
        licenses:   Response from GET /license?licenseeNumber={n}.
        validation: Response from POST /licensee/{n}/validate (dry_run=True),
                    or None if refresh_warning_level was not requested.
        now:        UTC datetime used for expiry calculations; defaults to
                    datetime.now(timezone.utc). Pass a fixed value in tests.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Extract licensee entity.
    lic_items = licensee.get("items", {}).get("item", [])
    lic_entity = lic_items[0] if lic_items else {}
    lic_props = _props(lic_entity)
    licensee_number = lic_props.get("number", "")
    licensee_name = lic_props.get("name", "")
    licensee_active = lic_props.get("active", "true").lower() == "true"

    # Group licenses by module.
    groups = _group_licenses_by_module(licenses)
    val_by_module = _validation_by_module(validation)
    features_by_module = _features_by_module(validation)

    # All module numbers: union of licenses + validation.
    all_modules = sorted(set(groups) | set(val_by_module))

    # Build per-module rows.
    modules: list[dict[str, Any]] = []
    for mno in all_modules:
        if mno == "__unknown__":
            continue
        row = _module_row(
            mno,
            groups.get(mno, []),
            val_by_module.get(mno, {}),
            now,
        )
        feats = features_by_module.get(mno)
        if feats:
            row["features_total"] = len(feats)
            row["features_valid"] = sum(1 for f in feats if f.get("valid") is True)
        row["state"] = module_state(row["valid"], feats)
        modules.append(row)

    # Counts.
    all_license_items = []
    for grp in groups.values():
        all_license_items.extend(grp)
    active_count = sum(
        1 for lic in all_license_items if _props(lic).get("active", "true").lower() == "true"
    )
    counts = {
        "total_licenses": len(all_license_items),
        "active_licenses": active_count,
        "inactive_licenses": len(all_license_items) - active_count,
        "modules": len(modules),
    }

    # Overall status.
    has_warning_levels = any("warning_level" in m for m in modules)
    validated = validation is not None and any(m["valid"] is not None for m in modules)
    if has_warning_levels or validated or _invalid_modules(modules):
        overall_status = _overall_status_from_validation(modules)
    else:
        overall_status = _overall_status_from_heuristics(modules, licensee_active)
        if overall_status == "ok":
            # Nothing was validated: counts and expiry dates never prove "healthy".
            overall_status = "unknown"

    if validation is not None and overall_status in ("ok", "warning"):
        # A module that says valid with no valid feature is not a clean pass; one with
        # no reported validity cannot be called healthy.
        if overall_status == "ok" and any(m["state"] == "unknown" for m in modules):
            overall_status = "unknown"
        elif overall_status == "ok" and any(m["state"] == "degraded" for m in modules):
            overall_status = "warning"

    infos = _validation_infos(validation)
    if infos and overall_status == "ok":
        # An API ERROR/WARNING on the validation call is never "healthy".
        overall_status = "warning"

    warnings = _build_warnings(modules, infos)
    if validation is not None:
        for m in modules:
            if m["state"] == "degraded":
                warnings.append(
                    f"Module {m['module_number']}: valid, but none of its "
                    f"{m['features_total']} features is valid."
                )
            elif m["state"] == "unknown":
                warnings.append(
                    f"Module {m['module_number']}: validation reported no 'valid' flag."
                )
    suggested_actions = _build_suggested_actions(modules, licensee_number, licensee_active)
    if overall_status == "unknown" and validation is None:
        suggested_actions.append(
            f"Re-run netlicensing_get_customer_health for {licensee_number} "
            "with refresh_warning_level=true."
        )
    summary = _summary_line(
        modules, counts, licensee_active, overall_status, validation is not None
    )

    envelope: dict[str, Any] = {
        "type": "CustomerHealth",
        "licensee_number": licensee_number,
        "active": licensee_active,
        "overall_status": overall_status,
        "validation_run": validation is not None,
        "counts": counts,
        "validation_counts": {
            state: sum(1 for m in modules if m["state"] == state)
            for state in ("valid", "degraded", "invalid", "unknown")
        },
        "modules": modules,
        "warnings": warnings,
        "suggested_actions": suggested_actions,
        "summary": summary,
    }
    if licensee_name:
        envelope["licensee_name"] = licensee_name

    url = console_url("Licensee", licensee_number)
    if url:
        envelope["console_url"] = url

    return envelope
