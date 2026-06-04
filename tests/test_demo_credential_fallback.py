"""
Tests for P0.1 — Eliminate silent demo-credential fallback.

Acceptance criteria:
  - No key + no ALLOW_DEMO → NetLicensingError(503) raised by _headers().
  - No key + ALLOW_DEMO=true → demo:demo used, loud warning emitted.
  - is_demo_mode() reflects the current context and env var state.
  - _json() injects {"demo_mode": True} when demo mode is active.
  - Tool calls return a structured error (not silently use demo creds) when
    no key and ALLOW_DEMO is absent.
  - Existing tool calls succeed when NETLICENSING_ALLOW_DEMO=true is set.
"""

from __future__ import annotations

import base64
import logging
from unittest.mock import AsyncMock, patch

import pytest

import netlicensing_mcp.client as nl_client
from netlicensing_mcp.client import (
    NetLicensingError,
    _allow_demo,
    _headers,
    is_demo_mode,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _decode_auth(headers: dict) -> str:
    """Decode the Basic auth credentials string from an Authorization header."""
    encoded = headers["Authorization"].split(" ", 1)[1]
    return base64.b64decode(encoded).decode()


# ── _allow_demo() ─────────────────────────────────────────────────────────────


class TestAllowDemo:
    def test_false_by_default(self, monkeypatch):
        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        assert _allow_demo() is False

    def test_true_string(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        assert _allow_demo() is True

    def test_true_uppercase(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "TRUE")
        assert _allow_demo() is True

    def test_1_activates(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "1")
        assert _allow_demo() is True

    def test_yes_activates(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "yes")
        assert _allow_demo() is True

    def test_false_string(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "false")
        assert _allow_demo() is False

    def test_empty_string(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "")
        assert _allow_demo() is False


# ── is_demo_mode() ────────────────────────────────────────────────────────────


class TestIsDemoMode:
    def test_false_when_api_key_present(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("real-api-key")
        try:
            assert is_demo_mode() is False
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_false_when_no_key_and_no_allow_demo(self, monkeypatch):
        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("")
        try:
            assert is_demo_mode() is False
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_true_when_no_key_and_allow_demo(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("")
        try:
            assert is_demo_mode() is True
        finally:
            nl_client.api_key_ctx.reset(token)


# ── _headers() ────────────────────────────────────────────────────────────────


class TestHeaders:
    def test_uses_api_key_when_set(self, monkeypatch):
        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("MY-API-KEY")
        try:
            h = _headers()
            assert _decode_auth(h) == "apiKey:MY-API-KEY"
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_raises_503_when_no_key_and_no_allow_demo(self, monkeypatch):
        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("")
        try:
            with pytest.raises(NetLicensingError) as exc_info:
                _headers()
            assert exc_info.value.status_code == 503
            assert "NETLICENSING_API_KEY" in exc_info.value.detail
            assert "NETLICENSING_ALLOW_DEMO" in exc_info.value.detail
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_uses_demo_creds_when_allow_demo(self, monkeypatch):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("")
        try:
            h = _headers()
            assert _decode_auth(h) == "demo:demo"
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_demo_mode_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        # Reset throttle timer so the warning fires immediately.
        nl_client._last_demo_warning_time = 0.0
        token = nl_client.api_key_ctx.set("")
        try:
            with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.client"):
                _headers()
            assert any("DEMO MODE" in r.message for r in caplog.records)
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_demo_mode_warning_throttled(self, monkeypatch, caplog):
        """Second call within 60 s must not repeat the warning."""
        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        nl_client._last_demo_warning_time = 0.0
        token = nl_client.api_key_ctx.set("")
        try:
            with caplog.at_level(logging.WARNING, logger="netlicensing_mcp.client"):
                _headers()  # first — emits warning
                count_after_first = sum(1 for r in caplog.records if "DEMO MODE" in r.message)
                _headers()  # second — throttled
                count_after_second = sum(1 for r in caplog.records if "DEMO MODE" in r.message)
            assert count_after_first == 1
            assert count_after_second == 1  # no additional warning
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_no_demo_creds_leak_when_no_allow_demo(self, monkeypatch):
        """demo:demo must NEVER appear in headers when ALLOW_DEMO is unset."""
        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("")
        try:
            with pytest.raises(NetLicensingError):
                h = _headers()
                # If somehow _headers() didn't raise, ensure demo:demo is absent.
                assert "demo:demo" not in _decode_auth(h)
        finally:
            nl_client.api_key_ctx.reset(token)


# ── _json() demo_mode tagging ─────────────────────────────────────────────────


class TestJsonDemoModeTag:
    """_json() must inject demo_mode=True into dict responses when in demo mode."""

    def test_injects_demo_mode_when_active(self, monkeypatch):
        from netlicensing_mcp.server import _json

        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("")
        try:
            import json

            result = json.loads(_json({"status": "ok"}))
            assert result.get("demo_mode") is True
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_no_demo_mode_tag_when_key_present(self, monkeypatch):
        from netlicensing_mcp.server import _json

        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("real-key")
        try:
            import json

            result = json.loads(_json({"status": "ok"}))
            assert "demo_mode" not in result
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_no_demo_mode_tag_when_no_allow_demo(self, monkeypatch):
        from netlicensing_mcp.server import _json

        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("")
        try:
            import json

            result = json.loads(_json({"status": "ok"}))
            assert "demo_mode" not in result
        finally:
            nl_client.api_key_ctx.reset(token)

    def test_non_dict_not_modified(self, monkeypatch):
        """Non-dict values (e.g. list) must not be wrapped even in demo mode."""
        from netlicensing_mcp.server import _json

        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("")
        try:
            import json

            result = json.loads(_json([1, 2, 3]))
            assert result == [1, 2, 3]
        finally:
            nl_client.api_key_ctx.reset(token)


# ── Tool-call error path (no key, no ALLOW_DEMO) ──────────────────────────────


class TestToolCallErrorPath:
    """When no API key is configured and ALLOW_DEMO is absent, tool calls must
    return a structured error — not silently use demo credentials."""

    async def test_list_products_returns_error_json(self, monkeypatch):
        """netlicensing_list_products should surface the 503 error as a JSON error."""
        from netlicensing_mcp import server as srv

        monkeypatch.delenv("NETLICENSING_ALLOW_DEMO", raising=False)
        token = nl_client.api_key_ctx.set("")
        try:
            import json

            result = await srv.netlicensing_list_products()
            parsed = json.loads(result)
            assert parsed.get("error") is True
            assert parsed.get("status") == 503
        finally:
            nl_client.api_key_ctx.reset(token)


# ── Existing tools still work with NETLICENSING_ALLOW_DEMO=true ───────────────


class TestDemoModeBackwardsCompatibility:
    """Existing tool wrappers must work normally when NETLICENSING_ALLOW_DEMO=true
    (demo mode uses demo:demo, API calls succeed, responses include demo_mode tag)."""

    async def test_list_products_succeeds_in_demo_mode(self, monkeypatch):
        from netlicensing_mcp import server as srv

        monkeypatch.setenv("NETLICENSING_ALLOW_DEMO", "true")
        token = nl_client.api_key_ctx.set("")
        mock_response = {"items": {"item": []}}
        try:
            with patch(
                "netlicensing_mcp.tools.products.nl_get",
                new=AsyncMock(return_value=mock_response),
            ):
                import json

                result = await srv.netlicensing_list_products()
                parsed = json.loads(result)
                # Must not be an error
                assert parsed.get("error") is not True
                # Must be tagged with demo_mode
                assert parsed.get("demo_mode") is True
        finally:
            nl_client.api_key_ctx.reset(token)
