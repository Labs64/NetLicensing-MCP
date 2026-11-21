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

1. **MCP layer** — split across three places:
   - **`app.py`** — the single `FastMCP` instance (`mcp`, with the `instructions=` block and `stateless_http=True`), logging setup, the `/health` route, the annotation presets (`_READONLY`, `_WRITE`, `_UPDATE`, `_DELETE`), the response helpers (`_json`, `_json_token_read`, `_wrap_json`, `_wrap_json_token_read`, `_error`, …) and `tool(title=..., annotations=...)`, the decorator every tool module registers with (change registration there, in one place). It registers a wrapper (same signature, so the same `inputSchema`) that turns the tool's JSON string into a `CallToolResult`: the string unchanged as text content, `structuredContent` = the parsed object (`{"result": ...}` for lists, scalars and plain text), `isError=True` for `{"error": true, ...}` blobs, and the shared `outputSchema` of the `ToolResult` model (no `properties`, to keep `tools/list` small; the common fields are documented in the server instructions). It returns the original function, so direct calls still return the string.
   - **`mcp_tools/<entity>.py`** — the `@tool(...)` wrappers, one module per entity (`products`, `bundles`, `product_modules`, `license_templates`, `licensees`, `licenses`, `tokens`, `transactions`, `payment_methods`, `utilities` incl. `netlicensing_server_info`, `workflows` for customer health / explain validation). Importing a module registers its tools.
   - **`server.py`** — thin entry point (`main()`, console script `netlicensing-mcp`, `python -m netlicensing_mcp.server`, `mcp dev src/netlicensing_mcp/server.py`). It imports the `mcp_tools` modules in a fixed order (that order is the `tools/list` order), registers the audit prompts, defines `ApiKeyMiddleware`, and re-exports every tool function, `mcp`, the helpers and the `tools/<entity>` modules (see `__all__`), so `from netlicensing_mcp.server import …` and patches such as `netlicensing_mcp.server.tokens.get_token` keep working.

   `tests/test_tool_registry_snapshot.py` compares every tool's name, title, description, input schema and annotations, the tool order and the prompts against `tests/fixtures/tools_snapshot.json`. After an intentional change, regenerate it with `UPDATE_SNAPSHOT=1 pytest tests/test_tool_registry_snapshot.py --no-cov` and review the diff.

   Each NetLicensing operation is a thin wrapper named `netlicensing_<action>_<entity>` (e.g. `netlicensing_create_license`). The wrapper's only jobs are: (a) translate empty strings / `None` defaults into "leave unchanged" semantics, (b) call the matching function in `tools/<entity>.py`, (c) wrap `NetLicensingError` into a JSON error blob via `_error(exc, "<own tool name>")` (a rejected `confirm_token` `ValueError` via `_confirm_error(exc, "<own tool name>")`; `tests/test_error_hints.py` checks every call site passes its own function name). Tool functions return JSON strings, not dicts (the `tool` decorator adds `structuredContent` at the protocol layer only) — `_json()` serializes the result **and applies the redaction layer**. Token create operations additionally call `tag_one_time_display()` before `_json()`; token read operations use `_json_token_read()` which applies `redact_token_read()` to also mask APIKEY `number` and SHOP `shopURL` fields.

2. **`tools/<entity>.py`** — one module per NetLicensing entity (`products`, `product_modules`, `license_templates`, `licensees`, `licenses`, `bundles`, `tokens`, `transactions`, `payment_methods`, `utilities`). Each builds the form-encoded payload, calls `nl_get/post/put/delete`, and runs the response through `strip_output_fields` from `tools/helpers.py`.

3. **`client.py`** — shared async `httpx.AsyncClient` (lazy singleton), Basic-auth header construction, and `nl_get/post/put/delete` helpers. Non-2xx responses raise `NetLicensingError` carrying the unwrapped NetLicensing `infos.info[].value` messages as `detail`, the `infos.info[].id` values as `info_ids` (e.g. `NotFoundException`) and a numeric `Retry-After` header as `retry_after`. Transport failures become `502` / `504`, a missing API key `503`. POST/PUT debug logs pass request data through `redact()` so sensitive fields are never logged in plaintext.

4. **`errors.py`** — next-step hints for error blobs. `error_hint(exc, tool_name, available=...)` is a pure function returning `hint`, `suggested_actions`, `retryable` (and `retry_after_seconds` for 429); `confirmation_hint(tool_name)` does the same for a rejected confirmation token. `app._error()` / `app._confirm_error()` add these keys after `error` / `status` / `detail`, restricted to the registered tools. The mapping follows what NetLicensing actually returns (checked against the sandbox and the API Conventions page): a **missing entity is `400` with info id `NotFoundException`** (`Requested licensee does not exist.`), not `404`; a duplicate number `400` `DuplicateEntityException`; a delete blocked by dependents `400` `IllegalOperationException` (`This product has Licensees.`); `401` bad credentials, `402` not in plan, `403` key role too low, `429` rate limit. Hints are fixed text plus tool names and the base URL **host** only — never the `detail`, a key or the full URL; keep it that way (tests assert it). Suggestions must be real tool names from `toolsets.TOOLSETS`.

5. **`responses.py`** — normalized response envelope (P0.6). Exposes `wrap(entity, kind, summary=None, suggested_actions=None, raw=None)` and `console_url(kind, number)`. Single-item upstream responses become a flat dict with all properties promoted to top level, `active` coerced to a JSON bool, and a `console_url` deep link derived from `MCP_CONSOLE_BASE_URL` (default `https://ui.netlicensing.io/#`). List responses become `{"type": "list", "kind", "count", "items": [...]}` with `console_url` on each item; `count` is the number of items in that response. The list envelope also maps the upstream `items` paging attributes (`totalitems`, `pagenumber`, `totalpages`, `hasnext`, `itemsnumber`; strings, sometimes `null`) to `total`, `page`, `total_pages`, `has_more` and, only when `hasnext` is true, `page_size` (= `itemsnumber`, since only the last page can be short). Each field appears only when upstream sends a parseable value. List tools that page through `filter` (all `netlicensing_list_*` with a `filter` parameter except payment methods, which upstream does not page) pass `paging_filter=filter` to `_wrap_json()` / `_wrap_json_token_read()`, which adds `next_page_hint` (the caller's filter minus `page`/`items`, plus `page=<next>;items=<page_size>`, built by `responses.next_page_filter()` and JSON-quoted in the hint). Every `@mcp.tool()` accepts `include_raw: bool = False`; when true the original NetLicensing payload is attached under `raw`. Server-layer helpers `_wrap_json()` / `_wrap_json_token_read()` apply the envelope before `_json()` redaction; for APIKEY tokens `_wrap_json_token_read()` drops `console_url` because the token `number` (used as the URL path) is itself the API key.

6. **`redaction.py`** — redaction layer (P0.3). Exposes `redact(payload, fields, mode)`, `tag_one_time_display(response)`, and `redact_token_read(response)`. Default redact set: `apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`. Extendable via `MCP_REDACT_FIELDS`. Handles both plain dict keys and NetLicensing property arrays (`{"property": [{"name": "licenseeSecret", "value": "..."}]}`). `mode="mask"` (default) produces a partial mask (`s3c****ecret`); `mode="remove"` drops the field. `redact_payment_method()` is an **allowlist**: every PaymentMethod property except `number`/`active` is masked, because providers store credentials (Stripe tokens, PayPal e-mails) as arbitrary custom properties. It is applied in `tools/payment_methods.py`, so every payment-method path is covered.

### Toolsets and read-only mode (`toolsets.py`)

`toolsets.TOOLSETS` is the single table that puts every tool into exactly one toolset; the `tool` decorator in `app.py` raises if a tool is missing from it, so **add every new tool to that table**. `ToolFilter.from_env()` parses `MCP_TOOLSETS` / `MCP_READ_ONLY` once, when `app.py` is imported; the decorator records every tool and adds it to `mcp` only if the filter allows it, but always returns the original function, so direct imports keep working. A restriction appends a short note to the server `instructions`. Tests build a fresh server under another filter with `app.new_server(filter)` + `app.register_tools(server, filter)`; `app.active_tool_settings()` reports the active toolsets, read-only flag and tool count.

### API key resolution (`api_key_ctx`)

API key is held in a **`contextvars.ContextVar`** (`client.api_key_ctx`), defaulted from `NETLICENSING_API_KEY`. In HTTP mode, `ApiKeyMiddleware` in `server.py` reads the key per-request from (in priority order) `X-NetLicensing-API-Key` header → `Authorization: Bearer …` (no query-parameter form: URLs get logged), then `.set()`s the ContextVar for the duration of the request and resets it after. The server runs FastMCP with `stateless_http=True`; in stateful mode the SDK pins the session-creating request's key to every later call. This means a single shared HTTP deployment can serve many tenants without baking a key into the server. Falls back to `demo:demo` credentials (sandbox) if no key is present.

### Response shape conventions

NetLicensing returns properties as `{"property": [{"name": "...", "value": "..."}, ...]}` arrays. The client does not flatten these — tool outputs preserve the upstream shape. `strip_output_fields` (in `tools/helpers.py`) recursively removes bulky fields (`logo`) from both plain-dict keys AND `property` arrays — keep this in sync if more bulky fields show up. Importantly, **create/update calls deliberately omit `logo`**, since omission preserves the existing server-side value; never add it back to write paths.

### List scoping

NetLicensing list endpoints **ignore** a bare `?productNumber=X` query parameter and return the whole vendor account. Parent scope (and paging) must go inside the single `filter` parameter: `filter=productNumber=X;page=0;items=100`. Always build it with `scoped_filter()` from `tools/helpers.py`, which also rejects `;`/`=` in the scope value and a user `filter` that tries to override the scope key. Max page size is 100 (also the default); use `licenses.list_all_licenses()` when every item is needed.

### Booleans and "leave unchanged" semantics

NetLicensing expects booleans as lowercase strings (`"true"`/`"false"`). The tools layer handles the conversion. MCP-level signatures use:
- `bool = True/False` for required booleans
- `bool | None = None` for optional booleans where `None` = "leave current value alone" on updates
- `str = ""` for optional strings; the server-layer wrapper converts `""` → `None` before passing down

Preserve this pattern when adding tools — clients (LLMs) will frequently pass empty strings when a field is unspecified.

### Prompts

`prompts/audit.py` registers five `@mcp.prompt()` templates (`audit_full`, `audit_customer`, `audit_expiry`, `audit_cleanup`, `audit_anomaly`) on the FastMCP instance. They return `PromptMessage` lists that orchestrate multi-tool audit workflows. New prompts go here and are wired up via `register_audit_prompts(mcp)`.

### Server instructions

The long `instructions=` string passed to `FastMCP(...)` in `app.py` documents the NetLicensing **entity hierarchy** (Product → ProductModule → LicenseTemplate; Product → Licensee → License; Bundles; Transactions; Tokens; PaymentMethods), licensing models, and **safety rules** (never delete without confirmation; `force_cascade` only on explicit user request; prefer deactivation over deletion). This is what guides LLM clients — when changing tool behaviour that affects those rules, update the instructions block too.

## Configuration

Environment variables (all optional):
- `NETLICENSING_API_KEY` — **required** unless `NETLICENSING_ALLOW_DEMO=true`; empty without demo flag = fatal error (stdio) or 503 (HTTP)
- `NETLICENSING_ALLOW_DEMO` — `true` opts in to sandbox demo mode; every tool response is tagged `"demo_mode": true` and a warning logs every 60 s; **never set in production**
- `NETLICENSING_BASE_URL` — defaults to `https://go.netlicensing.io/core/v2/rest`
- `MCP_TRANSPORT` — `stdio` (default) or `http`; also via positional CLI arg
- `MCP_HOST` / `MCP_PORT` — HTTP bind (default `127.0.0.1:8000`)
- `MCP_VERBOSE` — `true|1|yes` enables debug logging of API requests/responses (sensitive fields automatically redacted); also via `-v` flag
- `MCP_REDACT_FIELDS` — comma-separated extra field names to add to the redaction set (e.g. `ssn,phone`); default set: `apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`
- `MCP_CONSOLE_BASE_URL` — Console UI base for `console_url` deep links emitted by the normalized response envelope; default `https://ui.netlicensing.io/#`
- `MCP_TOOLSETS` — comma-separated toolsets to register (`products`, `bundles`, `modules`, `templates`, `licensees`, `licenses`, `tokens`, `transactions`, `payments`, `system`, `workflows`, or `all` = default). Unknown names log a warning and are ignored; if none is valid, all are registered
- `MCP_READ_ONLY` — `true|1|yes` registers only tools annotated `readOnlyHint=True` (lists, gets, `preview_*`, workflows, reference data). Applied after `MCP_TOOLSETS`. `netlicensing_server_info` is always registered under any filter

Logs go to **stderr** (stdio mode must keep stdout clean for the MCP protocol).

## Deployment

`deploy/aws/` contains a `deploy.sh` helper supporting **ECS Fargate** (production, ALB-fronted) and **App Runner** (scale-to-zero, dev). HTTP mode exposes `/health` (returns `{"status":"ok"}`) for load balancer probes — defined in `app.py` (`health_check`).
