"""
NetLicensing MCP Server
=======================
Entry point for both stdio (Claude Desktop / Copilot) and HTTP (remote) modes.

Usage:
  stdio (default):  python -m netlicensing_mcp.server
  HTTP mode:        python -m netlicensing_mcp.server http
  Dev / inspector:  mcp dev src/netlicensing_mcp/server.py

The FastMCP instance and shared helpers live in ``netlicensing_mcp.app``; the
tool wrappers live in ``netlicensing_mcp.mcp_tools.<entity>``. Importing this
module registers every tool (in the order below), the audit prompts and the
setup / troubleshooting prompts, and
re-exports the public names so ``from netlicensing_mcp.server import ...``
keeps working.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from netlicensing_mcp import client as _client
from netlicensing_mcp import safety
from netlicensing_mcp.app import (
    mcp,
    health_check,
    tool,
    _READONLY,
    _WRITE,
    _UPDATE,
    _DELETE,
    _json,
    _json_token_read,
    _wrap_json,
    _scrub_apikey_console_url,
    _wrap_json_token_read,
    _error,
    _count_items,
    _total_items,
    _sample_numbers,
    _extract_props,
    _fmt_price,
    _price_active_diff,
    set_transport,
)
from netlicensing_mcp.client import NetLicensingError, api_key_ctx, is_demo_mode
from netlicensing_mcp.prompts.audit import register_audit_prompts
from netlicensing_mcp.prompts.setup import register_setup_prompts
from netlicensing_mcp.readiness import register_ready_route
from netlicensing_mcp.redaction import redact, redact_token_read, tag_one_time_display
from netlicensing_mcp.responses import DEFAULT_WARN_INFO_TYPES, wrap
from netlicensing_mcp.tools import (
    bundles,
    license_templates,
    licensees,
    licenses,
    payment_methods,
    product_modules,
    products,
    tokens,
    transactions,
    utilities,
)
from netlicensing_mcp.tools.helpers import CustomPropertyValue

# Tool registration happens on import; the import order below is the order in
# which tools are listed to MCP clients.
from netlicensing_mcp.mcp_tools.products import (
    netlicensing_list_products,
    netlicensing_get_product,
    netlicensing_create_product,
    netlicensing_preview_update_product,
    netlicensing_update_product,
    netlicensing_preview_delete_product,
    netlicensing_delete_product,
)
from netlicensing_mcp.mcp_tools.bundles import (
    netlicensing_list_bundles,
    netlicensing_get_bundle,
    netlicensing_create_bundle,
    netlicensing_update_bundle,
    netlicensing_preview_delete_bundle,
    netlicensing_delete_bundle,
    netlicensing_obtain_bundle,
)
from netlicensing_mcp.mcp_tools.product_modules import (
    netlicensing_list_product_modules,
    netlicensing_get_product_module,
    netlicensing_create_product_module,
    netlicensing_update_product_module,
    netlicensing_preview_delete_product_module,
    netlicensing_delete_product_module,
)
from netlicensing_mcp.mcp_tools.license_templates import (
    netlicensing_list_license_templates,
    netlicensing_get_license_template,
    netlicensing_create_license_template,
    netlicensing_preview_update_license_template,
    netlicensing_update_license_template,
    netlicensing_preview_delete_license_template,
    netlicensing_delete_license_template,
)
from netlicensing_mcp.mcp_tools.licensees import (
    netlicensing_list_licensees,
    netlicensing_get_licensee,
    netlicensing_create_licensee,
    netlicensing_update_licensee,
    netlicensing_preview_delete_licensee,
    netlicensing_delete_licensee,
    netlicensing_validate_licensee,
    netlicensing_transfer_licenses,
)
from netlicensing_mcp.mcp_tools.licenses import (
    netlicensing_list_licenses,
    netlicensing_get_license,
    netlicensing_create_license,
    netlicensing_update_license,
    netlicensing_preview_delete_license,
    netlicensing_delete_license,
)
from netlicensing_mcp.mcp_tools.tokens import (
    netlicensing_list_tokens,
    netlicensing_get_token,
    netlicensing_create_shop_token,
    netlicensing_create_api_token,
    netlicensing_preview_delete_token,
    netlicensing_delete_token,
)
from netlicensing_mcp.mcp_tools.transactions import (
    netlicensing_list_transactions,
    netlicensing_get_transaction,
    netlicensing_create_transaction,
    netlicensing_update_transaction,
)
from netlicensing_mcp.mcp_tools.payment_methods import (
    netlicensing_list_payment_methods,
    netlicensing_get_payment_method,
    netlicensing_preview_update_payment_method,
    netlicensing_update_payment_method,
)
from netlicensing_mcp.mcp_tools.utilities import (
    netlicensing_list_licensing_models,
    netlicensing_list_license_types,
    netlicensing_list_countries,
    netlicensing_server_info,
)
from netlicensing_mcp.mcp_tools.workflows import (
    netlicensing_get_customer_health,
    netlicensing_explain_validation,
)
from netlicensing_mcp.mcp_tools.utilities import _server_version
from netlicensing_mcp.mcp_tools.workflows import _customer_health

logger = logging.getLogger(__name__)

# Names importable from ``netlicensing_mcp.server`` before the split into
# app.py / mcp_tools/, kept for tests and downstream imports. The entity
# modules (``products``, ``tokens``, ...) are the same module objects the tool
# wrappers call, so patching e.g. ``netlicensing_mcp.server.tokens.get_token``
# still affects the tools.
__all__ = [
    "mcp",
    "health_check",
    "tool",
    "ApiKeyMiddleware",
    "build_http_app",
    "main",
    "logger",
    "netlicensing_list_products",
    "netlicensing_get_product",
    "netlicensing_create_product",
    "netlicensing_preview_update_product",
    "netlicensing_update_product",
    "netlicensing_preview_delete_product",
    "netlicensing_delete_product",
    "netlicensing_list_bundles",
    "netlicensing_get_bundle",
    "netlicensing_create_bundle",
    "netlicensing_update_bundle",
    "netlicensing_preview_delete_bundle",
    "netlicensing_delete_bundle",
    "netlicensing_obtain_bundle",
    "netlicensing_list_product_modules",
    "netlicensing_get_product_module",
    "netlicensing_create_product_module",
    "netlicensing_update_product_module",
    "netlicensing_preview_delete_product_module",
    "netlicensing_delete_product_module",
    "netlicensing_list_license_templates",
    "netlicensing_get_license_template",
    "netlicensing_create_license_template",
    "netlicensing_preview_update_license_template",
    "netlicensing_update_license_template",
    "netlicensing_preview_delete_license_template",
    "netlicensing_delete_license_template",
    "netlicensing_list_licensees",
    "netlicensing_get_licensee",
    "netlicensing_create_licensee",
    "netlicensing_update_licensee",
    "netlicensing_preview_delete_licensee",
    "netlicensing_delete_licensee",
    "netlicensing_validate_licensee",
    "netlicensing_transfer_licenses",
    "netlicensing_list_licenses",
    "netlicensing_get_license",
    "netlicensing_create_license",
    "netlicensing_update_license",
    "netlicensing_preview_delete_license",
    "netlicensing_delete_license",
    "netlicensing_list_tokens",
    "netlicensing_get_token",
    "netlicensing_create_shop_token",
    "netlicensing_create_api_token",
    "netlicensing_preview_delete_token",
    "netlicensing_delete_token",
    "netlicensing_list_transactions",
    "netlicensing_get_transaction",
    "netlicensing_create_transaction",
    "netlicensing_update_transaction",
    "netlicensing_list_payment_methods",
    "netlicensing_get_payment_method",
    "netlicensing_preview_update_payment_method",
    "netlicensing_update_payment_method",
    "netlicensing_list_licensing_models",
    "netlicensing_list_license_types",
    "netlicensing_list_countries",
    "netlicensing_server_info",
    "netlicensing_get_customer_health",
    "netlicensing_explain_validation",
    "_READONLY",
    "_WRITE",
    "_UPDATE",
    "_DELETE",
    "_json",
    "_json_token_read",
    "_wrap_json",
    "_scrub_apikey_console_url",
    "_wrap_json_token_read",
    "_error",
    "_count_items",
    "_total_items",
    "_sample_numbers",
    "_extract_props",
    "_fmt_price",
    "_price_active_diff",
    "_server_version",
    "_customer_health",
    "_client",
    "safety",
    "NetLicensingError",
    "api_key_ctx",
    "is_demo_mode",
    "register_audit_prompts",
    "register_setup_prompts",
    "redact",
    "redact_token_read",
    "tag_one_time_display",
    "DEFAULT_WARN_INFO_TYPES",
    "wrap",
    "bundles",
    "license_templates",
    "licensees",
    "licenses",
    "payment_methods",
    "product_modules",
    "products",
    "tokens",
    "transactions",
    "utilities",
    "CustomPropertyValue",
]


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

register_audit_prompts(mcp)
register_setup_prompts(mcp)

# GET /ready (readiness); GET /health (liveness) is registered in app.py.
register_ready_route(mcp, version=_server_version)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Liveness / readiness probes must remain unauthenticated for load balancers
        if request.url.path in ("/health", "/ready"):
            return await call_next(request)

        # Extract key: prefer dedicated header, fall back to Bearer token
        key = request.headers.get("x-netlicensing-api-key", "").strip()
        if not key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()

        if key:
            token = api_key_ctx.set(key)
            try:
                return await call_next(request)
            finally:
                api_key_ctx.reset(token)

        # Reject unauthenticated requests with a standard 401 + WWW-Authenticate header
        return JSONResponse(
            {
                "error": "NetLicensing API key is required for HTTP transport. "
                "Supply it via the x-netlicensing-api-key header or "
                "Authorization: Bearer <key>."
            },
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="netlicensing-mcp"'},
        )


def build_http_app() -> Starlette:
    """The ASGI app HTTP mode serves: FastMCP's streamable-HTTP app + ``ApiKeyMiddleware``."""
    app = mcp.streamable_http_app()
    app.add_middleware(ApiKeyMiddleware)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="NetLicensing MCP Server")
    parser.add_argument(
        "transport",
        nargs="?",
        choices=["http", "stdio"],
        default=None,
        help="Transport mode: 'stdio' (default) or 'http'. "
        "Can also be set via MCP_TRANSPORT env var.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="Enable verbose debug logging (request/response details). "
        "Can also be set via MCP_VERBOSE=true env var.",
    )
    args = parser.parse_args()

    # Resolve transport: CLI arg → env var → default
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio").lower()
    set_transport(transport)  # for netlicensing_server_info

    # Resolve verbose: CLI flag → env var → default
    verbose = args.verbose or os.getenv("MCP_VERBOSE", "").lower() in ("1", "true", "yes")

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled — API requests/responses will be logged")

    logger.info("Starting NetLicensing MCP server (transport=%s, verbose=%s)", transport, verbose)

    if transport == "stdio":
        _startup_api_key = os.getenv("NETLICENSING_API_KEY", "")
        _startup_allow_demo = os.getenv("NETLICENSING_ALLOW_DEMO", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if not _startup_api_key and not _startup_allow_demo:
            logger.error(
                "FATAL: No NetLicensing API key configured. "
                "Set NETLICENSING_API_KEY or NETLICENSING_ALLOW_DEMO=true for sandbox access."
            )
            sys.exit(1)
        if _startup_allow_demo and not _startup_api_key:
            logger.warning(
                "⚠️  DEMO MODE ACTIVE — using sandbox demo:demo credentials. "
                "Not suitable for production. "
                "Set NETLICENSING_API_KEY to use real credentials."
            )
        mcp.run(transport="stdio")
    elif transport == "http":
        print(f"Starting MCP server on http://{mcp.settings.host}:{mcp.settings.port}")

        import anyio
        import uvicorn

        async def run_server() -> None:
            app = build_http_app()
            config = uvicorn.Config(
                app,
                host=mcp.settings.host,
                port=mcp.settings.port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()

        anyio.run(run_server)
    else:
        print(f"Unknown transport: {transport}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
