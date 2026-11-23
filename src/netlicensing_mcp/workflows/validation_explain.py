"""P1.9 — Smart Validation Explainer synthesiser.

Pure module — no I/O. The MCP tool wrapper in mcp_tools/workflows.py calls
validate_licensee(dry_run=True) and passes the response here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from netlicensing_mcp.responses import feature_results
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


def _norm_model(model: str) -> str:
    """Lowercase *model* without separators (``Pay-Per-Use`` and ``PayPerUse`` match)."""
    return re.sub(r"[\s_-]", "", model).lower()


def _module_blocks(payload: dict) -> list[tuple[dict[str, str], list[dict[str, Any]]]]:
    """Per module: its flat properties and its normalized MultiFeature results."""
    items_obj = payload.get("items", {})
    item_list = items_obj.get("item", []) if isinstance(items_obj, dict) else []
    return [(_props(item), feature_results(item)) for item in item_list if isinstance(item, dict)]


def _classify_module(
    props: dict[str, str], now: datetime, features: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    mno = props.get("productModuleNumber", "")
    row["module_number"] = mno

    mname = props.get("productModuleName", "")
    if mname:
        row["module_name"] = mname

    model = props.get("licensingModel", "")
    if model:
        row["licensing_model"] = model

    # A missing "valid" is unknown (None), never assumed true.
    valid_str = props.get("valid", "")
    row["valid"] = valid_str.lower() == "true" if valid_str else None
    if features:
        row["features"] = features

    wl = props.get("warningLevel", "")
    if wl:
        row["warning_level"] = wl

    model_lower = _norm_model(model)

    if "subscription" in model_lower or "timevolume" in model_lower:
        expires_str = props.get("expires") or props.get("expirationTime") or ""
        if expires_str:
            row["expires_at"] = expires_str
            days = _days_until(expires_str, now)
            if days is not None:
                row["expires_in_days"] = days

    elif "payperuse" in model_lower or model_lower == "quota":
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


def _state(row: dict[str, Any]) -> str:
    """``valid`` / ``invalid`` / ``unknown`` from the module's ``valid`` flag."""
    v = row.get("valid")
    return "unknown" if v is None else ("valid" if v else "invalid")


def _needs_attention(row: dict[str, Any]) -> bool:
    return _state(row) != "valid" or row.get("warning_level") in ("YELLOW", "RED")


def _explanation_for(row: dict[str, Any]) -> str:
    model_lower = _norm_model(row.get("licensing_model", ""))
    state = _state(row)
    valid = state == "valid"
    mno = row.get("module_number", "")

    if "subscription" in model_lower or "timevolume" in model_lower:
        days = row.get("expires_in_days")
        expires_at = row.get("expires_at", "")
        if days is None:
            if state == "invalid":
                return "Subscription is invalid."
            if state == "unknown":
                return "Subscription status is unknown: the validation result has no 'valid' flag."
            return "Subscription is active."
        if days < 0:
            return f"Subscription expired on {expires_at}."
        if days <= WARN_DAYS:
            return f"Subscription is valid but expires in {days} days."
        return f"Subscription is valid until {expires_at}."

    if "payperuse" in model_lower:
        pct = row.get("quota_pct")
        remaining = row.get("quota_remaining")
        total = row.get("quota_total")
        if pct is not None and pct >= WARN_QUOTA_PCT:
            return f"Pay-per-use module is at {int(pct * 100)}% of its quota."
        if remaining is not None and total is not None:
            return f"Pay-per-use module has {remaining} of {total} units remaining."
        if state == "invalid":
            return "Pay-per-use module is invalid: the prepaid quota is exhausted (or none was bought)."
        return "Pay-per-use module is active." if valid else _unknown_text("Pay-per-use module")

    if model_lower == "quota":
        remaining = row.get("quota_remaining")
        total = row.get("quota_total")
        if remaining is not None and total is not None:
            return f"Quota module has {remaining} of {total} units remaining."
        if state == "invalid":
            return "Quota module is invalid: the quota is 0 or used up."
        return "Quota module is active." if valid else _unknown_text("Quota module")

    if "floating" in model_lower:
        max_s = row.get("max_sessions")
        active_s = row.get("active_sessions")
        if max_s is not None and active_s is not None:
            if active_s >= max_s:
                return "Floating module is saturated — no free seats."
            return f"Floating module: {active_s}/{max_s} sessions in use."
        if state == "invalid":
            return "Floating module is invalid: no free session is available."
        return "Floating module is active." if valid else _unknown_text("Floating module")

    if "try" in model_lower and "buy" in model_lower:
        if valid:
            return "Trial license is active."
        if state == "unknown":
            return _unknown_text("Trial license")
        return "Trial license has ended — convert to a paid license."

    if "node" in model_lower or "locked" in model_lower:
        matched = row.get("node_matched")
        if matched is False:
            return "Node secret mismatch — license bound to a different device."
        if state == "invalid":
            return "Node-locked license is invalid: check that the node secret matches."
        if state == "unknown":
            return _unknown_text("Node-locked license")
        return "License bound to the current node."

    if "multifeature" in model_lower:
        features = row.get("features") or []
        bad = [f for f in features if f.get("valid") is not True]
        if features and bad:
            names = ", ".join(str(f.get("name") or f.get("number")) for f in bad)
            return (
                f"MultiFeature module: {len(bad)} of {len(features)} features not valid ({names})."
            )
        if features:
            return f"MultiFeature module: all {len(features)} features are valid."

    if "rental" in model_lower:
        if state == "invalid":
            return "Rental module is invalid: the rented time volume is used up or expired."
        if state == "unknown":
            wl = row.get("warning_level")
            level = f" (warningLevel={wl})" if wl else ""
            return _unknown_text("Rental module") + level

    if state == "invalid":
        return f"Module {mno} is invalid."
    if state == "unknown":
        return _unknown_text(f"Module {mno}")

    wl = row.get("warning_level", "GREEN")
    return f"Validation result: warningLevel={wl}, valid={valid}."


def _unknown_text(subject: str) -> str:
    return f"{subject}: validity is unknown, the validation result has no 'valid' flag."


def _actions_for(row: dict[str, Any], licensee_number: str) -> list[str]:
    model_lower = _norm_model(row.get("licensing_model", ""))
    state = _state(row)
    invalid = state == "invalid"
    mno = row.get("module_number", "")
    actions: list[str] = []

    if "subscription" in model_lower or "timevolume" in model_lower:
        days = row.get("expires_in_days")
        if days is not None:
            if days < 0:
                actions.append(
                    f"Renew expired subscription via SHOP token, or call "
                    f"netlicensing_create_license for module {mno}."
                )
            elif days <= WARN_DAYS:
                actions.append(
                    f"Send a SHOP renewal token: netlicensing_create_shop_token("
                    f'licensee_number="{licensee_number}").'
                )

    if "payperuse" in model_lower or model_lower == "quota":
        if row.get("quota_pct", 0) >= WARN_QUOTA_PCT or invalid:
            actions.append(
                "Top up the licensee's quota via a SHOP token or POST a new "
                "Pay-per-Use transaction."
            )

    if "floating" in model_lower:
        max_s = row.get("max_sessions")
        active_s = row.get("active_sessions")
        if (max_s is not None and active_s is not None and active_s >= max_s) or invalid:
            actions.append(
                "Check in a stale session (netlicensing_validate_licensee with action="
                "checkIn), wait for a free seat, or raise maxSessions on the template."
            )

    if "try" in model_lower and "buy" in model_lower:
        if invalid:
            actions.append("Issue a SHOP token to convert the trial to a paid license.")

    if "node" in model_lower or "locked" in model_lower:
        if row.get("node_matched") is False:
            actions.append(
                "Reset the device binding: netlicensing_update_license("
                'license_number=..., node_secret="").'
            )
        elif invalid:
            actions.append(
                "Check the node secret the client sends against the one bound to the license."
            )

    if "rental" in model_lower and (invalid or state == "unknown"):
        actions.append(
            "Check the license's remaining time volume and extend it or create a new one."
        )

    if state == "unknown" and not actions:
        actions.append(
            f"Check module {mno} with netlicensing_list_licenses: validation returned no "
            "'valid' flag, so its validity cannot be confirmed."
        )
    if invalid and not actions:
        actions.append(
            f"List the licensee's licenses for module {mno} (netlicensing_list_licenses) and "
            "check that one is active and not expired."
        )

    return actions


def _overall_status(blocks: list[dict[str, Any]], infos: list[str] | None = None) -> str:
    # An invalid module is as serious as RED — same rule as get_customer_health.
    has_red = any(b.get("warning_level") == "RED" for b in blocks)
    has_invalid = any(_state(b) == "invalid" for b in blocks)
    has_yellow = any(b.get("warning_level") == "YELLOW" for b in blocks)
    has_unknown = any(_state(b) == "unknown" for b in blocks)
    if has_red or has_invalid:
        return "critical"
    if has_yellow or has_unknown or infos:
        return "warning"
    return "ok"


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _validation_infos(payload: dict) -> list[str]:
    """ERROR / WARNING ``infos`` messages from a validate response, once each."""
    infos = payload.get("infos")
    info_list = infos.get("info", []) if isinstance(infos, dict) else []
    if not isinstance(info_list, list):
        return []
    return _dedupe(
        [
            str(i.get("value", ""))
            for i in info_list
            if isinstance(i, dict)
            and str(i.get("type", "")).upper() in ("ERROR", "WARNING")
            and i.get("value")
        ]
    )


def _summary_line(modules: list[dict[str, Any]], overall_status: str) -> str:
    """Summary whose counts come from the lists it names."""
    if not modules:
        return "Licensee has no licensed modules."
    n = len(modules)
    plural = "s" if n != 1 else ""
    attention = [m for m in modules if _needs_attention(m)]
    if not attention and overall_status == "ok":
        return f"Validation passed for all {n} module{plural}."
    invalid = [m.get("module_number", "") for m in modules if _state(m) == "invalid"]
    other = [
        m.get("module_number", "")
        for m in modules
        if _state(m) != "invalid" and _needs_attention(m)
    ]
    line = f"Validation passed for {n - len(attention)} of {n} module{plural}."
    if invalid:
        line += f" Invalid ({len(invalid)}): {', '.join(invalid)}."
    if other:
        line += f" Unknown or warning level ({len(other)}): {', '.join(other)}."
    return line


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

    modules: list[dict[str, Any]] = []
    all_actions: list[str] = []

    for props, features in _module_blocks(payload):
        row = _classify_module(props, now, features)
        row["explanation"] = _explanation_for(row)
        module_actions = _actions_for(row, licensee_number="<licensee>")
        row["suggested_actions"] = module_actions
        all_actions.extend(module_actions)
        modules.append(row)

    infos = _validation_infos(payload)
    overall = _overall_status(modules, infos)
    top_actions = _dedupe(all_actions)
    warnings = [m["explanation"] for m in modules if _needs_attention(m)]
    warnings = _dedupe(warnings + infos)

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
