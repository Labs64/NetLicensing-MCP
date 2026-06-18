"""Regression tests for GHSA-hxpf-9xvq-wph8 — REST path traversal.

A caller-controlled identifier interpolated into a REST path (e.g.
``f"/product/{product_number}"``) could contain ``../`` segments. httpx
normalizes those away, silently redirecting the request to an unintended
endpoint (e.g. ``/token``) and bypassing endpoint-specific redaction. The
``_validated_path`` guard in ``client.py`` rejects such inputs before any HTTP
request is built.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import netlicensing_mcp.client as client
from netlicensing_mcp.client import NetLicensingError, _validated_path


# ─── Unit: _validated_path ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/product/P001",
        "/product",
        "/token/APIKEY-123",
        "/bundle/B1/obtain",
        "/licensee/L1/validate",
        "/licensetemplate/LT-2024",
        "/transaction/TR_001",
        # A plain extra "/" yields valid sub-segments and is indistinguishable
        # from legitimate multi-segment paths (e.g. /bundle/B1/obtain) once the
        # path is assembled. It can only descend under the same root, never
        # climb to a sibling top-level endpoint, so it is not a traversal.
        "/product/x/y",
    ],
)
def test_legitimate_paths_pass(path):
    """Real REST paths (incl. multi-segment ones) are returned unchanged."""
    assert _validated_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "/product/../token",  # the GHSA PoC payload
        "/product/..%2ftoken",  # percent-encoded slash (httpx does NOT decode)
        "/product/%2e%2e/token",  # percent-encoded dot-dot
        "/product/..",
        "/product/.",
        "/product/x\\y",  # backslash separator
        "/product/a%2fb",  # encoded separator inside a segment
    ],
)
def test_traversal_and_separator_paths_rejected(path):
    with pytest.raises(NetLicensingError) as exc:
        _validated_path(path)
    assert exc.value.status_code == 400


def test_control_characters_rejected():
    with pytest.raises(NetLicensingError) as exc:
        _validated_path("/product/foo\nbar")
    assert exc.value.status_code == 400
    assert "control characters" in exc.value.detail


def test_non_rooted_path_rejected():
    with pytest.raises(NetLicensingError) as exc:
        _validated_path("product/P001")
    assert exc.value.status_code == 400


# ─── Integration: guard fires before any HTTP request ─────────────────────────


@pytest.fixture
def mock_http_client():
    """Patch the shared AsyncClient so we can assert whether a request was sent."""
    fake = AsyncMock()
    with patch("netlicensing_mcp.client._get_client", return_value=fake):
        token = client.api_key_ctx.set("dummy-key")
        try:
            yield fake
        finally:
            client.api_key_ctx.reset(token)


@pytest.mark.parametrize("helper", ["nl_get", "nl_post", "nl_put", "nl_delete"])
async def test_helpers_reject_traversal_before_request(helper, mock_http_client):
    fn = getattr(client, helper)
    args = ("/product/../token",)
    if helper in ("nl_post", "nl_put"):
        args = ("/product/../token", {"name": "x"})

    with pytest.raises(NetLicensingError) as exc:
        await fn(*args)

    assert exc.value.status_code == 400
    # No HTTP method was ever invoked on the client.
    mock_http_client.get.assert_not_called()
    mock_http_client.post.assert_not_called()
    mock_http_client.put.assert_not_called()
    mock_http_client.delete.assert_not_called()


async def test_get_product_traversal_does_not_leak_token(mock_http_client):
    """End-to-end replay of the GHSA PoC: the tool must raise, not leak."""
    from netlicensing_mcp.tools.products import get_product

    with pytest.raises(NetLicensingError):
        await get_product("../token")

    mock_http_client.get.assert_not_called()
