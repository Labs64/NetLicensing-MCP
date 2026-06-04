# AGENTS.md

This file provides guidance to AI Agents when working with code in this repository.

## Overview

`netlicensing-mcp` is a [FastMCP](https://github.com/modelcontextprotocol/python-sdk) server that exposes the [Labs64 NetLicensing](https://netlicensing.io) REST API as MCP tools and prompts. It runs over **stdio** (Claude Desktop / Copilot) or **streamable HTTP** (remote deployments). Python ≥ 3.12, async throughout.

## Development commands

```bash
# Install dev environment (editable + dev extras)
pip install -e ".[dev]"
pip install hatch hatch-vcs

# Run the server locally
python -m netlicensing_mcp.server          # stdio (default)
python -m netlicensing_mcp.server http     # HTTP on $MCP_HOST:$MCP_PORT (127.0.0.1:8000)
mcp dev src/netlicensing_mcp/server.py     # MCP Inspector UI at http://localhost:5173

# Tests (pyproject sets asyncio_mode=auto and turns on coverage automatically)
pytest tests/ -v
pytest tests/test_tools.py::test_name -v   # run a single test
pytest tests/ -v --no-cov                  # disable coverage for faster iteration

# Lint / format / type-check (these are the exact CI checks)
ruff check .
ruff format --check .       # use `ruff format .` to apply
mypy src/

# Security
pip-audit --ignore-vuln CVE-2026-4539 --ignore-vuln CVE-2026-3219

# Build & Docker
hatch build --target wheel  # version comes from git tag via hatch-vcs
docker build -t ghcr.io/labs64/netlicensing-mcp:latest .
```

CI matrix runs tests on Python 3.12, 3.13, 3.14. Lint/format/mypy run on 3.14 only.

## Architecture

Three layers, top-down:

1. **`server.py`** — single FastMCP entry point. Each NetLicensing operation is a thin `@mcp.tool()` wrapper named `netlicensing_<action>_<entity>` (e.g. `netlicensing_create_license`). The wrapper's only jobs are: (a) translate empty strings / `None` defaults into "leave unchanged" semantics, (b) call the matching function in `tools/<entity>.py`, (c) wrap `NetLicensingError` into a JSON error blob via `_error()`. Tools return JSON strings, not dicts — `_json()` serializes the result.

2. **`tools/<entity>.py`** — one module per NetLicensing entity (`products`, `product_modules`, `license_templates`, `licensees`, `licenses`, `bundles`, `tokens`, `transactions`, `payment_methods`, `utilities`). Each builds the form-encoded payload, calls `nl_get/post/put/delete`, and runs the response through `strip_output_fields` from `tools/helpers.py`.

3. **`client.py`** — shared async `httpx.AsyncClient` (lazy singleton), Basic-auth header construction, and `nl_get/post/put/delete` helpers. Non-2xx responses raise `NetLicensingError` carrying the unwrapped NetLicensing `infos.info[].value` messages.

### API key resolution (`api_key_ctx`)

API key is held in a **`contextvars.ContextVar`** (`client.api_key_ctx`), defaulted from `NETLICENSING_API_KEY`. In HTTP mode, `ApiKeyMiddleware` in `server.py` reads the key per-request from (in priority order) `X-NetLicensing-API-Key` header → `Authorization: Bearer …` → `?apikey=` query param, then `.set()`s the ContextVar for the duration of the request and resets it after. This means a single shared HTTP deployment can serve many tenants without baking a key into the server. Falls back to `demo:demo` credentials (sandbox) if no key is present.

### Response shape conventions

NetLicensing returns properties as `{"property": [{"name": "...", "value": "..."}, ...]}` arrays. The client does not flatten these — tool outputs preserve the upstream shape. `strip_output_fields` (in `tools/helpers.py`) recursively removes bulky fields (`logo`) from both plain-dict keys AND `property` arrays — keep this in sync if more bulky fields show up. Importantly, **create/update calls deliberately omit `logo`**, since omission preserves the existing server-side value; never add it back to write paths.

### Booleans and "leave unchanged" semantics

NetLicensing expects booleans as lowercase strings (`"true"`/`"false"`). The tools layer handles the conversion. MCP-level signatures use:
- `bool = True/False` for required booleans
- `bool | None = None` for optional booleans where `None` = "leave current value alone" on updates
- `str = ""` for optional strings; the server-layer wrapper converts `""` → `None` before passing down

Preserve this pattern when adding tools — clients (LLMs) will frequently pass empty strings when a field is unspecified.

### Prompts

`prompts/audit.py` registers five `@mcp.prompt()` templates (`audit_full`, `audit_customer`, `audit_expiry`, `audit_cleanup`, `audit_anomaly`) on the FastMCP instance. They return `PromptMessage` lists that orchestrate multi-tool audit workflows. New prompts go here and are wired up via `register_audit_prompts(mcp)`.

### Server instructions

The long `instructions=` string passed to `FastMCP(...)` in `server.py` documents the NetLicensing **entity hierarchy** (Product → ProductModule → LicenseTemplate; Product → Licensee → License; Bundles; Transactions; Tokens; PaymentMethods), licensing models, and **safety rules** (never delete without confirmation; `force_cascade` only on explicit user request; prefer deactivation over deletion). This is what guides LLM clients — when changing tool behaviour that affects those rules, update the instructions block too.

## Configuration

Environment variables (all optional):
- `NETLICENSING_API_KEY` — **required** unless `NETLICENSING_ALLOW_DEMO=true`; empty without demo flag = fatal error (stdio) or 503 (HTTP)
- `NETLICENSING_ALLOW_DEMO` — `true` opts in to sandbox demo mode; every tool response is tagged `"demo_mode": true` and a warning logs every 60 s; **never set in production**
- `NETLICENSING_BASE_URL` — defaults to `https://go.netlicensing.io/core/v2/rest`
- `MCP_TRANSPORT` — `stdio` (default) or `http`; also via positional CLI arg
- `MCP_HOST` / `MCP_PORT` — HTTP bind (default `127.0.0.1:8000`)
- `MCP_VERBOSE` — `true|1|yes` enables debug logging of API requests/responses; also via `-v` flag

Logs go to **stderr** (stdio mode must keep stdout clean for the MCP protocol).

## Deployment

`deploy/aws/` contains a `deploy.sh` helper supporting **ECS Fargate** (production, ALB-fronted) and **App Runner** (scale-to-zero, dev). HTTP mode exposes `/health` (returns `{"status":"ok"}`) for load balancer probes — defined at `server.py:130`.
