<p align="center"><img src="https://raw.githubusercontent.com/Labs64/NetLicensing-MCP/refs/heads/master/assets/banner.jpg"></p>

# NetLicensing MCP Server

<!-- mcp-name: io.github.Labs64/netlicensing-mcp -->

[![CI](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml/badge.svg)](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/netlicensing-mcp)](https://pypi.org/project/netlicensing-mcp/)
[![GHCR](https://img.shields.io/github/v/release/Labs64/NetLicensing-MCP?label=ghcr.io%2Flabs64%2Fnetlicensing-mcp&logo=docker&logoColor=white&style=flat-square)](https://github.com/Labs64/NetLicensing-MCP/pkgs/container/netlicensing-mcp)
[![Docker Hub](https://img.shields.io/docker/v/labs64/netlicensing-mcp?logo=docker&logoColor=white&label=Docker%20Hub&color=2496ED)](https://hub.docker.com/r/labs64/netlicensing-mcp)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-netlicensing--mcp-blue?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyek0xMSAxN3YtNkg5bDMtNCAzIDRoLTJ2NmgtMnoiLz48L3N2Zz4=&style=flat-square)](https://registry.modelcontextprotocol.io/?q=netlicensing-mcp)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**The official [Labs64 NetLicensing](https://netlicensing.io) MCP server.** Connect your AI assistant to NetLicensing and manage products, customers, licenses and entitlements by simply asking.

It works with Claude Desktop, Claude Code, GitHub Copilot (Agent mode), VS Code, JetBrains IDEs, and any other MCP-compatible client.

**Who is it for?**

- **Customer service and support teams** who need a quick answer to "why can't this customer use the product?" or want to renew or transfer a license without opening the console.
- **IT and system administrators** who audit accounts, clean up unused licenses and run the server for a team.
- **Developers and vendors** who set up products, license templates and shop checkouts, or test their licensing model while they build.

---

## Why use it?

- **Ask in plain language.** Create products, issue licenses, validate a customer and generate shop links without clicking through the console or writing API calls.
- **The whole NetLicensing API.** 61 tools cover products, modules, license templates, licensees, licenses, bundles, tokens, transactions and payment methods. See the [NetLicensing REST API](https://netlicensing.io/wiki/restful-api) for the details behind them.
- **Answers, not just data.** Two ready-made workflows check a customer's health and explain, in plain words, why a validation passed or failed.
- **Built-in audits and guided workflows.** Eleven prompt templates run account audits, expiry sweeps, cleanups and anomaly checks, and walk you through setting up a subscription or a trial, onboarding or migrating a customer, troubleshooting a validation and issuing an API key.
- **Safe by default.** Deleting requires a preview and a confirmation. Secrets are masked. There is no silent fallback to demo credentials.
- **Quick to start.** Run it with `uvx` or Docker. You don't need a local Python setup.

---

## What can you ask?

- *"List all products in my NetLicensing account."*
- *"Create a licensee for `customer@example.com` under product PTEST."*
- *"Does licensee L001 have a valid license? If not, tell me why."*
- *"How is customer L001 doing?"*
- *"Generate a shop URL so L001 can renew on their own."*
- *"Which licenses expire in the next 30 days?"*
- *"Find licensees with no active license so I can clean them up."*
- *"Move all licenses from L001 to L002."*
- *"Create a read-only API key for licensee L001."*
- *"Show me last month's transactions."*

NetLicensing supports several licensing models, such as Try & Buy, Subscription, Rental, Floating, Multi-Feature, Pay-per-Use and Quota. Use `netlicensing_list_licensing_models` to see what your account offers, or read about them in the [NetLicensing documentation](https://netlicensing.io/wiki/licensing-models).

---

## What it can do

| Area | Tools |
|---|---|
| **Products** | list, get, create, update, delete |
| **Product modules** | list, get, create, update, delete |
| **License templates** | list, get, create, update, delete |
| **Licensees (customers)** | list, get, create, update, delete, validate, transfer licenses |
| **Licenses** | list, get, create, update (activate or deactivate), delete |
| **Bundles** | list, get, create, update, delete, obtain |
| **Tokens** | list, get, create shop URL, create API key, delete |
| **Transactions** | list, get, create, update |
| **Payment methods** | list, get, update |
| **Reference data** | licensing models, license types, countries, server info (version, API host, demo mode) |
| **Workflows** | `get_customer_health`, `explain_validation` (read-only) |
| **Previews** | `preview_delete_*` and `preview_update_*` show what a change will affect before you confirm it |
| **Audit prompts** | full account, single customer, expiry sweep, cleanup, anomaly detection |
| **Setup and troubleshooting prompts** | subscription product, free trial, customer onboarding, customer migration, validation troubleshooting, API key |

**Good to know**

- List tools and `validate_licensee` always return `{"type": "list", "count": ..., "items": [...]}`, even for zero or one result. Get, create and update tools return a single object.
- **Paging:** `count` is the number of items in this response. NetLicensing returns at most 100 items per page, so list results also carry what the API reports about paging: `total` (all matching items), `page` (0-based), `total_pages` and `has_more`. When `has_more` is `true` they also carry `page_size` and a `next_page_hint` with the exact `filter` value for the next page, JSON-quoted (e.g. `filter="active=true;page=1;items=100"`); pass it as `filter` with the other arguments unchanged. `netlicensing_list_bundles` now takes an optional `filter` like the other list tools. Payment methods, licensing models, license types and countries are not paged by NetLicensing, so they get no paging hint.
- Every tool accepts `include_raw=true` if you also want the original NetLicensing response.
- **Response format:** every result is the JSON as text, plus the same object as `structuredContent` for clients that read structured output. A result that is not a JSON object (for example the message of a confirmed delete) comes as `{"result": ...}`. Failed calls are flagged with `isError`, and every tool declares an `outputSchema`.
- Tools tell your client whether they only read data, write data, or are destructive, so clients can ask for approval at the right moments.

---

## Security defaults

- **No silent demo credentials.** If `NETLICENSING_API_KEY` is missing and `NETLICENSING_ALLOW_DEMO` isn't enabled, the server refuses to start (stdio) or answers `503` (HTTP).
- **Secrets are masked.** Every response and log line passes through a redaction filter for `apiKey`, `licenseeSecret`, `nodeSecret`, `password` and `secret`. Short values become `****`. Longer ones keep the first 3 and last 4 characters (for example `pk_****W3Od`). Add your own fields with `MCP_REDACT_FIELDS`.
- **Credentials appear once.** `create_api_token` and `create_shop_token` mark their response `"shown_once": true`. Later `get_token` and `list_tokens` calls return masked values, and deleting a token shows its number only masked (in the preview, the delete message and confirmation errors).
- **Deletes need confirmation.** Each delete first returns a preview and a single-use token that expires after 5 minutes. Nothing is deleted until you send that token back. `force_cascade` is a separate option that also removes dependent items, and it's only used when you ask for it.
- **One key per request in HTTP mode.** Keys come from request headers, never from URLs, so one server can serve several teams safely.

More detail in [SECURITY.md](SECURITY.md).

---

## Quick Start

You need a NetLicensing API key. Sign in at [ui.netlicensing.io](https://ui.netlicensing.io), open your API keys and create one. Not ready for that yet? Try the sandbox with [demo mode](#demo--sandbox-mode-no-api-key).

### Option A — uvx (no install required)

```bash
NETLICENSING_API_KEY=your_key uvx netlicensing-mcp
```

### Option B — pip

```bash
pip install netlicensing-mcp
NETLICENSING_API_KEY=your_key netlicensing-mcp
```

### Option C — Docker

#### stdio (default) — for Claude Desktop / VS Code
```bash
docker run -i --rm \
  -e NETLICENSING_API_KEY=your_key \
  ghcr.io/labs64/netlicensing-mcp:latest
```

#### HTTP mode — for remote/shared deployments
```bash
docker run -d -p 8000:8000 \
  -e NETLICENSING_API_KEY=your_key \
  ghcr.io/labs64/netlicensing-mcp:latest http
```

#### Verbose logging (any mode)
```bash
# CLI flag
docker run -i --rm \
  -e NETLICENSING_API_KEY=your_key \
  ghcr.io/labs64/netlicensing-mcp:latest -v

# Or via env var
docker run -i --rm \
  -e NETLICENSING_API_KEY=your_key \
  -e MCP_VERBOSE=true \
  ghcr.io/labs64/netlicensing-mcp:latest
```

#### Demo / sandbox mode (no API key)
```bash
docker run -i --rm \
  -e NETLICENSING_ALLOW_DEMO=true \
  ghcr.io/labs64/netlicensing-mcp:latest
```

> **No API key?** Set `NETLICENSING_ALLOW_DEMO=true` to run against NetLicensing's built-in
> sandbox with demo credentials — no account required.
> The server will tag every response with `"demo_mode": true` and emit a periodic warning
> so it is always clear you are not using a real account.

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `NETLICENSING_API_KEY` | **Yes*** | — | NetLicensing API key. Required unless `NETLICENSING_ALLOW_DEMO=true` is set. |
| `NETLICENSING_ALLOW_DEMO` | No | `false` | Set to `true` to explicitly opt in to sandbox demo mode when no API key is configured. Every tool response is tagged with `"demo_mode": true` and a warning is logged every 60 seconds. **Never set this in production.** |
| `NETLICENSING_BASE_URL` | No | `https://go.netlicensing.io/core/v2/rest` | Override the NetLicensing REST API base URL (e.g. for on-prem deployments). |
| `MCP_TRANSPORT` | No | `stdio` | Transport mode: `stdio` (default) or `http`. Can also be passed as a CLI argument. |
| `MCP_HOST` | No | `127.0.0.1` | Host address to bind the HTTP server (HTTP mode only). |
| `MCP_PORT` | No | `8000` | Port to bind the HTTP server (HTTP mode only). |
| `MCP_VERBOSE` | No | `false` | Enable verbose debug logging (`true`, `1`, or `yes`). Logs raw API requests/responses **with sensitive fields automatically redacted**. Can also be set via `-v` CLI flag. |
| `MCP_REDACT_FIELDS` | No | — | Comma-separated list of additional field names to redact from all tool responses and log output (e.g. `MCP_REDACT_FIELDS=ssn,phone`). Extends the built-in default set: `apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`. |
| `MCP_TOOLSETS` | No | `all` | Comma-separated list of toolsets to register (e.g. `licensees,licenses`). Unknown names are ignored with a warning on stderr. See [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode). |
| `MCP_READ_ONLY` | No | `false` | Register only read-only tools (`true`, `1`, or `yes`): list, get, `preview_*`, workflows and reference data. See [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode). |

> **\* `NETLICENSING_API_KEY` and demo mode:** If neither `NETLICENSING_API_KEY` nor `NETLICENSING_ALLOW_DEMO=true` is set, the server will **refuse to start** (stdio mode) or return `503 Service Unavailable` for all tool calls (HTTP mode). This prevents accidental use of demo credentials in production.

> **Note on HTTP deployments (e.g. AWS):** When running in HTTP mode over a network, you can skip setting `NETLICENSING_API_KEY` on the server. The MCP server will automatically extract the key per-request if the connecting client provides it via the `X-NetLicensing-API-Key` HTTP header, `Authorization: Bearer <key>` header. Query-parameter keys are not supported, because URLs are logged by proxies and load balancers.


### Reduce the tool list / read-only mode

The server registers 61 tools by default. Some clients handle long tool lists poorly, and some deployments should never change data. Two environment variables shrink the list when the server starts:

- `MCP_TOOLSETS` registers only the listed toolsets. `all` (the default) registers everything.
- `MCP_READ_ONLY=true` registers only tools annotated as read-only (`readOnlyHint`). Previews (`preview_*`) stay; every create, update, delete, `obtain_bundle`, `transfer_licenses` and `validate_licensee` (it can check out floating sessions or bind nodes) is left out.

When both are set, the toolset filter applies first, then the read-only filter. `netlicensing_server_info` is always registered. When a restriction is active, the server instructions sent to the client say so.

| Toolset | Tools |
|---|---|
| `products` | list, get, create, update, delete products, with previews |
| `bundles` | list, get, create, update, delete, obtain bundles, with delete preview |
| `modules` | list, get, create, update, delete product modules, with delete preview |
| `templates` | list, get, create, update, delete license templates, with previews |
| `licensees` | list, get, create, update, delete, validate licensees, transfer licenses, with delete preview |
| `licenses` | list, get, create, update, delete licenses, with delete preview |
| `tokens` | list, get tokens, create shop and API tokens, delete, with delete preview |
| `transactions` | list, get, create, update transactions |
| `payments` | list, get, update payment methods, with update preview |
| `system` | `list_licensing_models`, `list_license_types`, `list_countries`, `server_info` |
| `workflows` | `get_customer_health`, `explain_validation` |

```bash
# Only customer and license tools, read-only
MCP_TOOLSETS=licensees,licenses MCP_READ_ONLY=true NETLICENSING_API_KEY=your_key uvx netlicensing-mcp
```

All prompts are always available. Some of their steps call tools that may not be registered (for example `audit_expiry` calls `netlicensing_create_shop_token`, which is not available in read-only mode or without the `tokens` toolset, and the setup prompts create entities, which read-only mode does not allow); the assistant then cannot run those steps.

---

### Claude Desktop

Open `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "uvx",
      "args": ["netlicensing-mcp"],
      "env": {
        "NETLICENSING_API_KEY": "your_key_here"
      }
    }
  }
}
```

Or use the official Docker image:

#### stdio (default) — for Claude Desktop / VS Code
```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "NETLICENSING_API_KEY=your_key_here",
        "ghcr.io/labs64/netlicensing-mcp:latest"
      ]
    }
  }
}
```

#### HTTP mode — for remote/shared deployments
```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "docker",
      "args": [
        "run", "-d",
        "-p", "8000:8000",
        "-e", "NETLICENSING_API_KEY=your_key_here",
        "ghcr.io/labs64/netlicensing-mcp:latest",
        "http"
      ]
    }
  }
}
```

### Claude Code

```bash
claude mcp add netlicensing --env NETLICENSING_API_KEY=your_key_here -- uvx netlicensing-mcp
```

### Cursor and other MCP clients

Any client that can start a stdio server works. Use the same `command`, `args` and `env` values as in the Claude Desktop example above.

### VS Code / GitHub Copilot

The repo ships a `.vscode/mcp.json` that auto-configures Copilot Agent mode.
Set `NETLICENSING_API_KEY` in your shell environment or a `.env` file, then click
**Start** in the editor banner that appears above `mcp.json`.

### JetBrains / IntelliJ IDEA

In Copilot Chat → Agent mode → Tools icon → **Add More Tools…** — paste the
same JSON block shown in the Claude Desktop section above.

### First run

Once the server is configured, ask your assistant to **run `netlicensing_server_info`** (for example: "Run netlicensing_server_info and tell me if the setup is OK"). It checks the setup and makes one small read-only API call (it lists one product) to confirm that the NetLicensing API is reachable and accepts your key. The result never contains the key:

```json
{
  "version": "<installed version>",
  "base_url": "go.netlicensing.io",
  "demo_mode": false,
  "status": "ok",
  "transport": "stdio",
  "auth": {"configured": true, "source": "env", "valid": true},
  "checks": [
    {"name": "credentials", "ok": true, "detail": "API key from the NETLICENSING_API_KEY environment variable (or .env file)."},
    {"name": "reachable", "ok": true, "detail": "The NetLicensing API at go.netlicensing.io answered."},
    {"name": "authentication", "ok": true, "detail": "The credentials were accepted (test read: list products, 1 item)."}
  ],
  "warnings": [],
  "next_steps": [],
  "toolsets": ["all"],
  "read_only": false,
  "tool_count": 61
}
```

- `status` is `ok`, `warning` (demo mode; a valid key whose role does not allow listing products, `403`; or the API answered with an error that says nothing about the key) or `error` (no key, key rejected with `401`, API not reachable). With `check_connection=false`, `ok` only means that a key is configured: it has not been checked.
- `auth.source` says where the credentials come from: `env` (`NETLICENSING_API_KEY`), `header` (HTTP mode: `X-NetLicensing-API-Key` or `Authorization: Bearer`), `demo` (`NETLICENSING_ALLOW_DEMO=true`) or `none`. `auth.valid` is `true` when NetLicensing accepted the key (the test call succeeded, or it answered `403`: authenticated, but the key's role does not allow listing products; the `permission` check then fails and a warning explains it), `false` when NetLicensing rejected the key (`401`), and `null` when it could not be checked.
- `next_steps` says in plain language what to fix, e.g. how to set the key.
- Pass `check_connection=false` to skip the API call.

---

## Prompt Templates

The server ships eleven prompt templates. Pick one in Copilot Agent or Claude Desktop, fill in its arguments, and the assistant runs the whole workflow for you with the matching tools.

**Audits:**

| Prompt | Purpose | Example arguments |
|---|---|---|
| `audit_full` | End-to-end account audit for a product | `product_number=P001` |
| `audit_customer` | Deep-dive on a single licensee | `licensee_number=I001` |
| `audit_expiry` | Find licenses expiring within N days and generate renewal URLs | `product_number=P001`, `days_threshold=30` |
| `audit_cleanup` | Identify inactive / orphaned licenses for cleanup | `product_number=P001` |
| `audit_anomaly` | Detect unusual usage patterns across all customers | `product_number=P001` |

**Setup and troubleshooting:**

| Prompt | Purpose | Example arguments |
|---|---|---|
| `setup_subscription_product` | Create a product with a Subscription module and one TIMEVOLUME license template per plan | `product_name=Acme Cloud`, `plans=1 MONTH 9.99 EUR; 1 YEAR 99.00 EUR` |
| `setup_trial` | Add a Try & Buy module to a product: a free, automatic TIMEVOLUME trial template and a FEATURE full-version template | `product_number=P001`, `trial_days=14` (default 14) |
| `onboard_customer` | Create a licensee, assign a license from a template (or a bundle) and validate it with a dry run | `customer_name=Acme Corp`, `product_number=P001`; optional `licensee_number`, `module_number`, `license_template_number` |
| `migrate_customer` | Preview both licensees and their licenses, then move all licenses with `netlicensing_transfer_licenses` | `from_licensee_number=I001`, `to_licensee_number=I002` |
| `troubleshoot_validation` | Find out why a validation fails, without side effects: setup check, dry-run validation, plain-language explanation, customer health | `licensee_number=I001`; optional `product_number`, `product_module_number` |
| `issue_api_key` | Pick the least-privilege API key role for a purpose and create the key, which is shown once | `purpose=license validation in our desktop app` |

The setup prompts follow the server's safety rules: they show the plan and ask for confirmation before each write, never delete anything themselves (a removal goes through the `preview_delete_*` tool and never uses `force_cascade` unless you ask for it), prefer deactivating to deleting, and do not repeat secrets such as a new API key after showing it once.

---

## Troubleshooting

**Run the first-run check**

Ask your assistant to run `netlicensing_server_info` (see [First run](#first-run)): it reports whether a key is configured, whether NetLicensing accepts it and what to do next.

**Check MCP server logs**

```bash
# macOS / Claude Desktop
tail -f ~/Library/Logs/Claude/mcp-server-netlicensing.log

# Windows
Get-Content "$env:APPDATA\Claude\Logs\mcp-server-netlicensing.log" -Wait
```

**Run the MCP Inspector** (browser UI at `http://localhost:5173`)

```bash
mcp dev src/netlicensing_mcp/server.py
```

**Read the error result**

A failed tool call returns `{"error": true, "status": ..., "detail": ...}` (flagged `isError`), where `detail` is NetLicensing's own message. It also carries `hint` (the next step), `suggested_actions` (tools to call next) and `retryable` (whether the same call may succeed later; `retry_after_seconds` on a `429`). For example:

```json
{
  "error": true,
  "status": 400,
  "detail": "Requested licensee does not exist.",
  "hint": "The licensee was not found. Identifiers are case-sensitive: check the number, or look it up with netlicensing_list_licensees.",
  "suggested_actions": ["netlicensing_list_licensees"],
  "retryable": false
}
```

| `status` | Meaning | `retryable` |
|---|---|---|
| `400` | Validation or business rule; NetLicensing also reports a **missing entity as `400`** (`Requested … does not exist.`), a duplicate number and a delete blocked by dependents this way | no |
| `401` / `403` | Missing or invalid API key / key role too low for the operation | no |
| `402` | Operation not included in your pricing plan | no |
| `429` | Above your plan's API rate limit while NetLicensing is busy; wait `retry_after_seconds` | yes |
| `500`, `502`, `504` | NetLicensing error, API unreachable or timed out (the hint names the API host only) | yes |
| `503` | No API key configured (see below); any other `503` counts as a server error like `500` | no |

The hints never contain your API key. A hint about a delete blocked by dependents points at the `preview_delete` tool; `force_cascade` is for an explicit user request only.

**Common issues**

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` responses | Invalid or expired API key | Regenerate your key at [ui.netlicensing.io](https://ui.netlicensing.io) |
| Server not listed in Claude | Config file JSON syntax error | Validate with `python -m json.tool claude_desktop_config.json` |
| `uvx: command not found` | `uv` not installed | `pip install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv) |
| Server exits immediately / `503` on all calls | `NETLICENSING_API_KEY` not set and demo mode not enabled | Set `NETLICENSING_API_KEY`, or set `NETLICENSING_ALLOW_DEMO=true` for sandbox testing |
| Demo data instead of live data | `NETLICENSING_API_KEY` not set; `NETLICENSING_ALLOW_DEMO=true` active | Ensure `NETLICENSING_API_KEY` is exported in the shell that starts the client and unset `NETLICENSING_ALLOW_DEMO` |

---

## Development

```bash
git clone https://github.com/Labs64/NetLicensing-MCP
cd NetLicensing-MCP

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# ... and install dependencies
pip install -e ".[dev]"
pip install hatch hatch-vcs

# Add your API key to a .env file (or export it in your shell)
cp .env.example .env

# Run the MCP Inspector
mcp dev src/netlicensing_mcp/server.py

# Run tests
pytest tests/ -v

# Clean previous builds
rm -rf dist/

# Build a wheel for local testing
hatch build --target wheel

# Build the Docker image locally
docker build -t ghcr.io/labs64/netlicensing-mcp:latest .
```

### HTTP mode (for remote / shared deployments)

```bash
python -m netlicensing_mcp.server http
# Server listens on MCP_HOST:MCP_PORT (default: 127.0.0.1:8000)
```

Two unauthenticated probe endpoints come with HTTP mode (no API key needed):

| Endpoint | Answers | Use it for |
|---|---|---|
| `GET /health` | Liveness: always `200` `{"status":"ok","server":"netlicensing-mcp"}` while the process serves HTTP. | Load balancer and container health checks (the Docker image's `HEALTHCHECK` uses it). |
| `GET /ready` | Readiness: `200` `{"status":"ready","server":...,"version":...,"checks":{"app":...,"upstream":...}}` when the MCP endpoint is running and the NetLicensing API answers, else `503` with `"status":"not_ready"` and a `reason`. | Monitoring and post-deploy checks, e.g. `curl http://127.0.0.1:8000/ready`. |

`/ready` sends one unauthenticated `GET` to `NETLICENSING_BASE_URL` (3-second timeout); any HTTP answer, even `401` or `404`, counts as reachable; timeouts, connection and other transport/protocol errors, and a malformed URL count as unreachable. The result is cached for 15 seconds (a failure for 5 seconds). An API key is not checked, since in HTTP mode each request brings its own. The reply never contains a key or the upstream response, only the API's host name.

Use `ngrok` or a reverse proxy to expose the HTTP endpoint to remote MCP clients:

```bash
ngrok http 8000
# Then point your client at the generated HTTPS URL
```

### Cloud Deployment (AWS)

Deploy the MCP server to AWS for a **public HTTPS endpoint** that remote AI agents can connect to:

The recommended path is **ECS Fargate** behind an Application Load Balancer. App Runner is closed to new AWS customers, so its template is kept only for accounts that already use it.

```bash
cd deploy/aws

# Quick test (plain HTTP, sandbox keys only)
./deploy.sh fargate

# Production: HTTPS with your own domain and an ACM certificate
./deploy.sh fargate --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id
```

HTTPS only works for a hostname covered by your certificate, so point a DNS CNAME for your domain at the load balancer. The guide walks through certificate, DNS, verification and client setup step by step.

#### Connect MCP clients to the public URL

To use a shared, remote deployment, do not bake the `NETLICENSING_API_KEY` into the remote server settings. Instead, pass the API key from the client side in an HTTP header.

For example, in your MCP client configuration:

```json
{
  "mcpServers": {
    "netlicensing": {
      "url": "https://mcp.example.com/mcp",
      "headers": { "X-NetLicensing-API-Key": "YOUR_API_KEY" }
    }
  }
}
```

You can alternatively send `Authorization: Bearer YOUR_API_KEY`.

📖 Full step-by-step instructions: **[deploy/aws/README.md](deploy/aws/README.md)**

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, and open an issue before starting anything big. To report a security problem, follow [SECURITY.md](SECURITY.md). Release notes are in [CHANGELOG.md](CHANGELOG.md).

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

[![NetLicensing-MCP MCP server](https://glama.ai/mcp/servers/Labs64/NetLicensing-MCP/badges/card.svg)](https://glama.ai/mcp/servers/Labs64/NetLicensing-MCP)
