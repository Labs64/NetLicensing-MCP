"""P1.9 — Smart Validation Explainer synthesiser.

Pure module — no I/O. The MCP tool wrapper in server.py calls
validate_licensee(dry_run=True) and passes the response here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from netlicensing_mcp.workflows._thresholds import WARN_DAYS, WARN_QUOTA_PCT


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
    return int((dt - now).total_seconds() // 86400)


def _module_blocks(payload: dict) -> list[dict[str, str]]:
    items_obj = payload.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    return [_props(item) for item in item_list if isinstance(item, dict)]


def _classify_module(props: dict[str, str], now: datetime) -> dict[str, Any]:
    row: dict[str, Any] = {}
    mno = props.get("productModuleNumber", "")
    row["module_number"] = mno

    mname = props.get("productModuleName", "")
    if mname:
        row["module_name"] = mname

    model = props.get("licensingModel", "")
    if model:
        row["licensing_model"] = model

    valid_str = props.get("valid", "")
    row["valid"] = valid_str.lower() == "true" if valid_str else True

    wl = props.get("warningLevel", "")
    if wl:
        row["warning_level"] = wl

    model_lower = model.lower()

    if "subscription" in model_lower or "time-volume" in model_lower:
        expires_str = props.get("expires") or props.get("expirationTime") or ""
        if expires_str:
            row["expires_at"] = expires_str
            days = _days_until(expires_str, now)
            if days is not None:
                row["expires_in_days"] = days

    elif "pay-per-use" in model_lower or "pay per use" in model_lower:
        for key in ("quota", "quotaTotal"):
            if key in props:
                try:
                    row["quota_total"] = int(props[key])
                except ValueError:
                    pass
                break
        for key in ("quotaUsed", "usedQuantity"):
            if key in props:
                try:
                    row["quota_used"] = int(props[key])
                except ValueError:
                    pass
                break
        if "quota_total" in row and "quota_used" in row:
            row["quota_remaining"] = row["quota_total"] - row["quota_used"]
            if row["quota_total"] > 0:
                row["quota_pct"] = round(row["quota_used"] / row["quota_total"], 2)

    elif "floating" in model_lower:
        for key in ("maxSessions", "maxCheckouts"):
            if key in props:
                try:
                    row["max_sessions"] = int(props[key])
                except ValueError:
                    pass
                break
        for key in ("activeSessions", "activeCheckouts"):
            if key in props:
                try:
                    row["active_sessions"] = int(props[key])
                except ValueError:
                    pass
                break

    elif "try" in model_lower and "buy" in model_lower:
        pass  # valid field already set above

    elif "node" in model_lower or "locked" in model_lower:
        # Don't echo secret values — just note the binding result.
        bound = props.get("nodeLocked", props.get("nodeMatched", ""))
        if bound:
            row["node_matched"] = bound.lower() == "true"

    return row


def _explanation_for(row: dict[str, Any]) -> str:
    model_lower = row.get("licensing_model", "").lower()
    valid = row.get("valid", True)
    mno = row.get("module_number", "")

    if "subscription" in model_lower or "time-volume" in model_lower:
        days = row.get("expires_in_days")
        expires_at = row.get("expires_at", "")
        if days is None:
            if not valid:
                return "Subscription is invalid."
            return "Subscription is active."
        if days < 0:
            return f"Subscription expired on {expires_at}."
        if days <= WARN_DAYS:
            return f"Subscription is valid but expires in {days} days."
        return f"Subscription is valid until {expires_at}."

    if "pay-per-use" in model_lower or "pay per use" in model_lower:
        pct = row.get("quota_pct")
        remaining = row.get("quota_remaining")
        total = row.get("quota_total")
        if pct is not None and pct >= WARN_QUOTA_PCT:
            return f"Pay-per-use module is at {int(pct * 100)}% of its quota."
        if remaining is not None and total is not None:
            return f"Pay-per-use module has {remaining} of {total} units remaining."
        return "Pay-per-use module is active." if valid else "Pay-per-use module is invalid."

    if "floating" in model_lower:
        max_s = row.get("max_sessions")
        active_s = row.get("active_sessions")
        if max_s is not None and active_s is not None:
            if active_s >= max_s:
                return "Floating module is saturated — no free seats."
            return f"Floating module: {active_s}/{max_s} sessions in use."
        return "Floating module is active." if valid else "Floating module is invalid."

    if "try" in model_lower and "buy" in model_lower:
        if valid:
            return "Trial license is active."
        return "Trial license has ended — convert to a paid license."

    if "node" in model_lower or "locked" in model_lower:
        matched = row.get("node_matched")
        if matched is False:
            return "Node secret mismatch — license bound to a different device."
        if not valid:
            return "Node-locked license is invalid."
        return "License bound to the current node."

    if not valid:
        return f"Module {mno} is invalid."

    wl = row.get("warning_level", "GREEN")
    return f"Validation result: warningLevel={wl}, valid={valid}."


def _actions_for(row: dict[str, Any], licensee_number: str) -> list[str]:
    model_lower = row.get("licensing_model", "").lower()
    valid = row.get("valid", True)
    mno = row.get("module_number", "")
    actions: list[str] = []

    if "subscription" in model_lower or "time-volume" in model_lower:
        days = row.get("expires_in_days")
        if days is not None:
            if days < 0:
                actions.append(
                    f"Renew expired subscription via SHOP token, or call "
                    f"netlicensing_create_license for module {mno}."
                )
            elif days <= WARN_DAYS:
                actions.append(
                    f"Send a renewal token: netlicensing_create_token("
                    f'licensee_number="{licensee_number}", token_type="SHOP").'
                )

    if "pay-per-use" in model_lower or "pay per use" in model_lower:
        if row.get("quota_pct", 0) >= WARN_QUOTA_PCT:
            actions.append(
                "Top up the licensee's quota via a SHOP token or POST a new "
                "Pay-per-Use transaction."
            )

    if "floating" in model_lower:
        max_s = row.get("max_sessions")
        active_s = row.get("active_sessions")
        if max_s is not None and active_s is not None and active_s >= max_s:
            actions.append(
                "Identify a stale session and force a check-in, or raise "
                "maxSessions on the template."
            )

    if "try" in model_lower and "buy" in model_lower:
        if not valid:
            actions.append("Issue a SHOP token to convert the trial to a paid license.")

    if "node" in model_lower or "locked" in model_lower:
        if row.get("node_matched") is False:
            actions.append(
                "Reset the device binding: netlicensing_update_license("
                'license_number=..., node_secret="").'
            )

    if not valid and not actions:
        actions.append(
            "Inspect the raw validation payload (include_raw=true) and check "
            "upstream NetLicensing logs."
        )

    return actions


def _overall_status(blocks: list[dict[str, Any]]) -> str:
    has_red = any(b.get("warning_level") == "RED" for b in blocks)
    has_invalid = any(not b.get("valid", True) for b in blocks)
    has_yellow = any(b.get("warning_level") == "YELLOW" for b in blocks)
    if has_red:
        return "critical"
    if has_invalid:
        return "invalid"
    if has_yellow:
        return "warning"
    return "ok"


def _dedupe(actions: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result


def _summary_line(modules: list[dict[str, Any]], overall_status: str) -> str:
    if not modules:
        return "Licensee has no licensed modules."
    n = len(modules)
    if overall_status == "ok":
        return f"Validation passed for all {n} module{'s' if n != 1 else ''}."
    issues = sum(
        1
        for m in modules
        if not m.get("valid", True) or m.get("warning_level") in ("YELLOW", "RED")
    )
    return (
        f"Validation passed for {n - issues} module{'s' if n - issues != 1 else ''}; "
        f"{issues} module{'s' if issues != 1 else ''} need{'s' if issues == 1 else ''} attention."
    )


def explain_validation(
    payload: dict,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a ValidationExplanation envelope from a raw validate response.

    Args:
        payload: Response from POST /licensee/{n}/validate.
        now:     UTC datetime for expiry calculations; defaults to
                 datetime.now(timezone.utc). Pass a fixed value in tests.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    raw_blocks = _module_blocks(payload)
    modules: list[dict[str, Any]] = []
    all_actions: list[str] = []

    for props in raw_blocks:
        row = _classify_module(props, now)
        row["explanation"] = _explanation_for(row)
        module_actions = _actions_for(row, licensee_number="<licensee>")
        row["suggested_actions"] = module_actions
        all_actions.extend(module_actions)
        modules.append(row)

    overall = _overall_status(modules)
    top_actions = _dedupe(all_actions)
    warnings = [m["explanation"] for m in modules if m.get("warning_level") in ("YELLOW", "RED")]

    envelope: dict[str, Any] = {
        "type": "ValidationExplanation",
        "overall_status": overall,
        "summary": _summary_line(modules, overall),
        "modules": modules,
        "warnings": warnings,
        "suggested_actions": top_actions,
    }

    # Preserve upstream metadata (signature, ttl) verbatim.
    for key in ("signature", "ttl"):
        if key in payload:
            envelope[key] = payload[key]

    return envelope
