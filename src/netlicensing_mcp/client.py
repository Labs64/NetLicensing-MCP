"""
NetLicensing REST API async client.
All methods raise httpx.HTTPStatusError on non-2xx responses.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL: str = os.getenv(
    "NETLICENSING_BASE_URL",
    "https://go.netlicensing.io/core/v2/rest",
)
API_KEY: str = os.getenv("NETLICENSING_API_KEY", "")


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    if API_KEY:
        # Use API key auth: username 'apiKey', password is the API key
        auth_str = f"apiKey:{API_KEY}"
    else:
        # Use demo credentials
        auth_str = "demo:demo"
    token = base64.b64encode(auth_str.encode()).decode()
    h = {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


async def nl_get(path: str, params: Optional[dict[str, str]] = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{path}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


async def nl_post(path: str, data: Optional[dict[str, str]] = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}{path}",
            headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
            data=data or {},
        )
        r.raise_for_status()
        return r.json()


async def nl_put(path: str, data: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(
            f"{BASE_URL}{path}",
            headers=_headers({"Content-Type": "application/x-www-form-urlencoded"}),
            data=data,
        )
        r.raise_for_status()
        return r.json()


async def nl_delete(path: str) -> int:
    """Returns HTTP status code (200 or 204)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}{path}", headers=_headers())
        r.raise_for_status()
        return r.status_code
