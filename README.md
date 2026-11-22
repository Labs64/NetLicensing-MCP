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

It works with Claude Desktop, Claude Code, Cursor, GitHub Copilot (Agent mode) in VS Code and JetBrains IDEs, and any other MCP-compatible client.

**Who is it for?**

- **Customer service and support teams** who need a quick answer to "why can't this customer use the product?" or want to renew or transfer a license without opening the console.
- **IT and system administrators** who audit accounts, clean up unused licenses and run the server for a team.
- **Developers and vendors** who set up products, license templates and shop checkouts, or test their licensing model while they build.

---

## Connect in 30 seconds

You need a NetLicensing API key (create one at [ui.netlicensing.io](https://ui.netlicensing.io)) and either [uv](https://docs.astral.sh/uv/) (for `uvx`) or Docker. Replace `YOUR_API_KEY` with your key. No account yet? Use [demo mode](#no-account-yet-demo-mode).

**Claude Code**

```bash
claude mcp add netlicensing -e NETLICENSING_API_KEY=YOUR_API_KEY -- uvx netlicensing-mcp
```

**VS Code (GitHub Copilot)**

```bash
code --add-mcp '{"name":"netlicensing","type":"stdio","command":"uvx","args":["netlicensing-mcp"],"env":{"NETLICENSING_API_KEY":"YOUR_API_KEY"}}'
```

On Windows, single-quoted JSON doesn't work in `cmd.exe` or older PowerShell versions; use the [`.vscode/mcp.json`](#vs-code--github-copilot) form instead.

**Cursor**: add this to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "uvx",
      "args": ["netlicensing-mcp"],
      "env": { "NETLICENSING_API_KEY": "YOUR_API_KEY" }
    }
  }
}
```

**Claude Desktop**: open **Settings → Developer → Edit Config** and add the same `mcpServers` block as for Cursor to `claude_desktop_config.json`, then quit and restart Claude Desktop.

**Docker** instead of `uvx` (Cursor, Claude Desktop and other clients with an `mcpServers` file):

```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "NETLICENSING_API_KEY=YOUR_API_KEY", "ghcr.io/labs64/netlicensing-mcp:latest"]
    }
  }
}
```

### No account yet? Demo mode

Demo mode runs against the NetLicensing sandbox with demo credentials, so you need no key. Every result is tagged `"demo_mode": true`. Never use it in production.

```bash
claude mcp add netlicensing-demo -e NETLICENSING_ALLOW_DEMO=true -- uvx netlicensing-mcp
```

In a JSON config, use `"env": { "NETLICENSING_ALLOW_DEMO": "true" }` instead of the API key.

Then ask your assistant: *"Run netlicensing_server_info and tell me if the setup is OK."* (see [First run](#first-run)). More options per client (a `.vscode/mcp.json` that asks for the key, a Cursor install link, JetBrains, remote HTTP servers) are in [Client setup](#client-setup). For what to ask next, see the example sessions in [docs/EXAMPLES.md](docs/EXAMPLES.md).

---

## Why use it?

- **Ask in plain language.** Create products, issue licenses, validate a customer and generate shop links without clicking through the console or writing API calls.
- **The whole NetLicensing API.** <!-- count:tools -->61<!-- /count:tools --> tools cover products, modules, license templates, licensees, licenses, bundles, tokens, transactions and payment methods. See the [NetLicensing REST API](https://netlicensing.io/wiki/restful-api) for the details behind them.
- **Answers, not just data.** Two ready-made workflows check a customer's health and explain, in plain words, why a validation passed or failed.
- **Built-in audits and guided workflows.** <!-- count:prompts -->11<!-- /count:prompts --> prompt templates run account audits, expiry sweeps, cleanups and anomaly checks, and walk you through setting up a subscription or a trial, onboarding or migrating a customer, troubleshooting a validation and issuing an API key.
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

[docs/EXAMPLES.md](docs/EXAMPLES.md) walks through six vendor scenarios with the tool calls behind them.

NetLicensing supports several licensing models, such as Try & Buy, Subscription, Rental, Floating, Multi-Feature, Pay-per-Use and Quota. Use `netlicensing_list_licensing_models` to see what your account offers, or read about them in the [NetLicensing documentation](https://netlicensing.io/wiki/licensing-models).

---

## What it can do

Tools are grouped into toolsets (see [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode)). `preview_delete_*` and `preview_update_*` show what a change will affect before you confirm it. Two read-only workflows, `get_customer_health` and `explain_validation`, return answers instead of raw data. Audit, setup and troubleshooting prompts are listed under [Prompt Templates](#prompt-templates).

<!-- tools:start -->
<!-- Generated by scripts/gen_tools_doc.py from the tool registry. Do not edit by hand; run `python scripts/gen_tools_doc.py`. -->

61 tools in 11 toolsets, plus 11 prompts. **R** = read-only, **W** = writes data, **D** = destructive (deletes data). Parameters for every tool: [docs/TOOLS.md](docs/TOOLS.md).

<details>
<summary>Toolset <code>products</code> (7 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_products`](docs/TOOLS.md#netlicensing_list_products) | List products | R | List all products in the NetLicensing account. |
| [`netlicensing_get_product`](docs/TOOLS.md#netlicensing_get_product) | Get product | R | Get details of a specific product. |
| [`netlicensing_create_product`](docs/TOOLS.md#netlicensing_create_product) | Create product | W | Create a new product. |
| [`netlicensing_preview_update_product`](docs/TOOLS.md#netlicensing_preview_update_product) | Preview update of product | R | Preview a sensitive product update (licenseeAutoCreate or vatMode change). |
| [`netlicensing_update_product`](docs/TOOLS.md#netlicensing_update_product) | Update product | W | Update an existing product's fields. |
| [`netlicensing_preview_delete_product`](docs/TOOLS.md#netlicensing_preview_delete_product) | Preview deletion of product | R | Preview what would be deleted when deleting a product. |
| [`netlicensing_delete_product`](docs/TOOLS.md#netlicensing_delete_product) | Delete product | D | Delete a product permanently. |

</details>

<details>
<summary>Toolset <code>bundles</code> (7 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_bundles`](docs/TOOLS.md#netlicensing_list_bundles) | List bundles | R | List all bundles in the NetLicensing account. |
| [`netlicensing_get_bundle`](docs/TOOLS.md#netlicensing_get_bundle) | Get bundle | R | Get details of a specific bundle. |
| [`netlicensing_create_bundle`](docs/TOOLS.md#netlicensing_create_bundle) | Create bundle | W | Create a new bundle grouping one or more license templates. |
| [`netlicensing_update_bundle`](docs/TOOLS.md#netlicensing_update_bundle) | Update bundle | W | Update an existing bundle's fields. |
| [`netlicensing_preview_delete_bundle`](docs/TOOLS.md#netlicensing_preview_delete_bundle) | Preview deletion of bundle | R | Preview what would be deleted when deleting a bundle. |
| [`netlicensing_delete_bundle`](docs/TOOLS.md#netlicensing_delete_bundle) | Delete bundle | D | Delete a bundle permanently. |
| [`netlicensing_obtain_bundle`](docs/TOOLS.md#netlicensing_obtain_bundle) | Obtain bundle | W | Obtain a bundle for a customer — creates licenses from all license templates included in the bundle for the specified licensee. |

</details>

<details>
<summary>Toolset <code>modules</code> (6 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_product_modules`](docs/TOOLS.md#netlicensing_list_product_modules) | List product modules | R | List all modules (feature groups) for a product. |
| [`netlicensing_get_product_module`](docs/TOOLS.md#netlicensing_get_product_module) | Get product module | R | Get a specific product module. |
| [`netlicensing_create_product_module`](docs/TOOLS.md#netlicensing_create_product_module) | Create product module | W | Create a product module with a licensing model. |
| [`netlicensing_update_product_module`](docs/TOOLS.md#netlicensing_update_product_module) | Update product module | W | Update a product module's properties. |
| [`netlicensing_preview_delete_product_module`](docs/TOOLS.md#netlicensing_preview_delete_product_module) | Preview deletion of product module | R | Preview what would be deleted when deleting a product module. |
| [`netlicensing_delete_product_module`](docs/TOOLS.md#netlicensing_delete_product_module) | Delete product module | D | Delete a product module. |

</details>

<details>
<summary>Toolset <code>templates</code> (7 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_license_templates`](docs/TOOLS.md#netlicensing_list_license_templates) | List license templates | R | List all license templates for a product module. |
| [`netlicensing_get_license_template`](docs/TOOLS.md#netlicensing_get_license_template) | Get license template | R | Get a specific license template. |
| [`netlicensing_create_license_template`](docs/TOOLS.md#netlicensing_create_license_template) | Create license template | W | Create a license template. |
| [`netlicensing_preview_update_license_template`](docs/TOOLS.md#netlicensing_preview_update_license_template) | Preview update of license template | R | Preview a sensitive license template update (price, currency, or active state). |
| [`netlicensing_update_license_template`](docs/TOOLS.md#netlicensing_update_license_template) | Update license template | W | Update a license template's properties. |
| [`netlicensing_preview_delete_license_template`](docs/TOOLS.md#netlicensing_preview_delete_license_template) | Preview deletion of license template | R | Preview what would be deleted when deleting a license template. |
| [`netlicensing_delete_license_template`](docs/TOOLS.md#netlicensing_delete_license_template) | Delete license template | D | Delete a license template. |

</details>

<details>
<summary>Toolset <code>licensees</code> (8 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_licensees`](docs/TOOLS.md#netlicensing_list_licensees) | List licensees | R | List all customers (licensees) for a product. |
| [`netlicensing_get_licensee`](docs/TOOLS.md#netlicensing_get_licensee) | Get licensee | R | Get a specific licensee (customer). |
| [`netlicensing_create_licensee`](docs/TOOLS.md#netlicensing_create_licensee) | Create licensee | W | Create a new customer (licensee) under a product. |
| [`netlicensing_update_licensee`](docs/TOOLS.md#netlicensing_update_licensee) | Update licensee | W | Update a licensee's properties. |
| [`netlicensing_preview_delete_licensee`](docs/TOOLS.md#netlicensing_preview_delete_licensee) | Preview deletion of licensee | R | Preview what would be deleted when deleting a licensee. |
| [`netlicensing_delete_licensee`](docs/TOOLS.md#netlicensing_delete_licensee) | Delete licensee | D | Delete a licensee and all their licenses permanently. |
| [`netlicensing_validate_licensee`](docs/TOOLS.md#netlicensing_validate_licensee) | Validate licensee | W | Validate a customer's licenses across all product modules. |
| [`netlicensing_transfer_licenses`](docs/TOOLS.md#netlicensing_transfer_licenses) | Transfer licenses | W | Transfer all licenses from one licensee to another. |

</details>

<details>
<summary>Toolset <code>licenses</code> (6 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_licenses`](docs/TOOLS.md#netlicensing_list_licenses) | List licenses | R | List all licenses for a specific customer. |
| [`netlicensing_get_license`](docs/TOOLS.md#netlicensing_get_license) | Get license | R | Get details of a specific license. |
| [`netlicensing_create_license`](docs/TOOLS.md#netlicensing_create_license) | Create license | W | Assign a new license to a customer from a license template. |
| [`netlicensing_update_license`](docs/TOOLS.md#netlicensing_update_license) | Update license | W | Update a license's properties. |
| [`netlicensing_preview_delete_license`](docs/TOOLS.md#netlicensing_preview_delete_license) | Preview deletion of license | R | Preview what would be deleted when deleting a license. |
| [`netlicensing_delete_license`](docs/TOOLS.md#netlicensing_delete_license) | Delete license | D | Delete a license permanently. |

</details>

<details>
<summary>Toolset <code>tokens</code> (6 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_tokens`](docs/TOOLS.md#netlicensing_list_tokens) | List tokens | R | List all active tokens in the account. |
| [`netlicensing_get_token`](docs/TOOLS.md#netlicensing_get_token) | Get token | R | Get details of a specific token. |
| [`netlicensing_create_shop_token`](docs/TOOLS.md#netlicensing_create_shop_token) | Create shop token | W | Generate a NetLicensing Shop one-time checkout URL for a customer. |
| [`netlicensing_create_api_token`](docs/TOOLS.md#netlicensing_create_api_token) | Create API token | W | Create a scoped API token. |
| [`netlicensing_preview_delete_token`](docs/TOOLS.md#netlicensing_preview_delete_token) | Preview deletion of token | R | Preview what would be revoked when deleting a token. |
| [`netlicensing_delete_token`](docs/TOOLS.md#netlicensing_delete_token) | Delete token | D | Revoke an API or shop token. |

</details>

<details>
<summary>Toolset <code>transactions</code> (4 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_transactions`](docs/TOOLS.md#netlicensing_list_transactions) | List transactions | R | List all transactions in the account. |
| [`netlicensing_get_transaction`](docs/TOOLS.md#netlicensing_get_transaction) | Get transaction | R | Get details of a specific transaction. |
| [`netlicensing_create_transaction`](docs/TOOLS.md#netlicensing_create_transaction) | Create transaction | W | Create a new transaction. |
| [`netlicensing_update_transaction`](docs/TOOLS.md#netlicensing_update_transaction) | Update transaction | W | Update a transaction's status or properties. |

</details>

<details>
<summary>Toolset <code>payments</code> (4 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_payment_methods`](docs/TOOLS.md#netlicensing_list_payment_methods) | List payment methods | R | List all payment methods configured for the account. |
| [`netlicensing_get_payment_method`](docs/TOOLS.md#netlicensing_get_payment_method) | Get payment method | R | Get details of a specific payment method. |
| [`netlicensing_preview_update_payment_method`](docs/TOOLS.md#netlicensing_preview_update_payment_method) | Preview update of payment method | R | Preview a sensitive payment method update (active state change). |
| [`netlicensing_update_payment_method`](docs/TOOLS.md#netlicensing_update_payment_method) | Update payment method | W | Update a payment method's configuration. |

</details>

<details>
<summary>Toolset <code>system</code> (4 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_list_licensing_models`](docs/TOOLS.md#netlicensing_list_licensing_models) | List licensing models | R | List all licensing models supported by the NetLicensing service. |
| [`netlicensing_list_license_types`](docs/TOOLS.md#netlicensing_list_license_types) | List license types | R | List all license types supported by the NetLicensing service. |
| [`netlicensing_list_countries`](docs/TOOLS.md#netlicensing_list_countries) | List countries | R | List all countries available for VAT and localization settings. |
| [`netlicensing_server_info`](docs/TOOLS.md#netlicensing_server_info) | Get server info | R | Check this MCP server's setup and its NetLicensing connection. |

</details>

<details>
<summary>Toolset <code>workflows</code> (2 tools)</summary>

| Tool | Title | Access | Description |
|---|---|---|---|
| [`netlicensing_get_customer_health`](docs/TOOLS.md#netlicensing_get_customer_health) | Get customer health | R | Return a normalized health summary for one licensee. |
| [`netlicensing_explain_validation`](docs/TOOLS.md#netlicensing_explain_validation) | Explain validation | R | Run a dry-run validation and return a plain-language explanation. |

</details>

<!-- tools:end -->

**Good to know**

- List tools and `validate_licensee` always return `{"type": "list", "count": ..., "items": [...]}`, even for zero or one result. Get, create and update tools return a single object.
- **Paging:** `count` is the number of items in this response. NetLicensing returns at most 100 items per page, so list results also carry what the API reports about paging: `total` (all matching items), `page` (0-based), `total_pages` and `has_more`. When `has_more` is `true` they also carry `page_size` and a `next_page_hint` with the exact `filter` value for the next page, JSON-quoted (e.g. `filter="active=true;page=1;items=100"`); pass it as `filter` with the other arguments unchanged. `netlicensing_list_bundles` takes an optional `filter` like the other list tools. Payment methods, licensing models, license types and countries are not paged by NetLicensing, so they get no paging hint.
- Every tool accepts `include_raw=true` if you also want the original NetLicensing response.
- **Response format:** every result is the JSON as text, plus the same object as `structuredContent` for clients that read structured output. A result that is not a JSON object (for example the message of a confirmed delete) comes as `{"result": ...}`. Failed calls are flagged with `isError`, and every tool declares an `outputSchema`.
- Tools tell your client whether they only read data, write data, or are destructive, so clients can ask for approval at the right moments.

---

## Security defaults

- **No silent demo credentials.** If `NETLICENSING_API_KEY` is missing and `NETLICENSING_ALLOW_DEMO` isn't enabled, the server refuses to start (stdio) or answers `503` (HTTP).
- **Secrets are masked.** Every response, and every log line this server writes, passes through a redaction filter for `apiKey`, `licenseeSecret`, `nodeSecret`, `password` and `secret`. Short values become `****`. Longer ones keep the first 3 and last 4 characters (for example `pk_****W3Od`). Add your own fields with `MCP_REDACT_FIELDS`. Request logs show token paths as `/token/****`; the HTTP libraries' own request and response logging (`httpx`, `httpcore`, `sse_starlette`) is held at `WARNING`, also in verbose mode, because it would write full token numbers and new keys. Verbose mode (`-v` / `MCP_VERBOSE`) also turns on the MCP SDK's own DEBUG output, which this filter does not cover: use it for local debugging only and don't ship or keep its logs.
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
  -e MCP_HOST=0.0.0.0 \
  -e NETLICENSING_API_KEY=your_key \
  ghcr.io/labs64/netlicensing-mcp:latest http
```

#### Verbose logging (any mode)
For local debugging only: besides this server's own (redacted) request lines it turns on the MCP SDK's own DEBUG output, which is not filtered. Don't ship or keep these logs.
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

## Client setup

Each client below starts the server locally over stdio with `uvx netlicensing-mcp`. To use Docker instead, use `docker` as the command with the arguments shown under [Claude Desktop](#claude-desktop). The remote examples assume you run the server in HTTP mode yourself (see [HTTP mode](#http-mode-for-remote--shared-deployments) and [Cloud Deployment (AWS)](#cloud-deployment-aws)); `https://mcp.example.com/mcp` stands for your deployment's URL. A remote server takes the API key from the `X-NetLicensing-API-Key` header or `Authorization: Bearer`.

### Claude Code

```bash
claude mcp add netlicensing -e NETLICENSING_API_KEY=YOUR_API_KEY -- uvx netlicensing-mcp
```

The default scope `local` loads the server in the current project only, for you only. Add `--scope user` to load it in all your projects, or `--scope project` to store it in the project's `.mcp.json` and share it through version control (then don't put a real key on the command line; it would end up in that file).

Remote server in HTTP mode:

```bash
claude mcp add --transport http netlicensing https://mcp.example.com/mcp --header "X-NetLicensing-API-Key: YOUR_API_KEY"
```

### VS Code / GitHub Copilot

`code --add-mcp` (see [Connect in 30 seconds](#connect-in-30-seconds)) adds the server in one line. To keep the key out of the configuration file, create `.vscode/mcp.json` in your workspace instead. VS Code then asks for the key in an input box (`password: true` hides what you type):

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "netlicensing-api-key",
      "description": "NetLicensing API key",
      "password": true
    }
  ],
  "servers": {
    "netlicensing": {
      "type": "stdio",
      "command": "uvx",
      "args": ["netlicensing-mcp"],
      "env": { "NETLICENSING_API_KEY": "${input:netlicensing-api-key}" }
    }
  }
}
```

Remote server in HTTP mode (same `inputs` block):

```json
{
  "servers": {
    "netlicensing": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": { "X-NetLicensing-API-Key": "${input:netlicensing-api-key}" }
    }
  }
}
```

### Cursor

Use the `mcpServers` block from [Connect in 30 seconds](#connect-in-30-seconds) in `~/.cursor/mcp.json` or `.cursor/mcp.json`. To keep the key out of the file, write `"NETLICENSING_API_KEY": "${env:NETLICENSING_API_KEY}"` and set the variable in the environment Cursor starts from.

Or paste this install link into your browser's address bar; Cursor asks before it installs the server. Afterwards replace `YOUR_API_KEY` with your key in the installed server's configuration:

```text
cursor://anysphere.cursor-deeplink/mcp/install?name=netlicensing&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJuZXRsaWNlbnNpbmctbWNwIl0sImVudiI6eyJORVRMSUNFTlNJTkdfQVBJX0tFWSI6IllPVVJfQVBJX0tFWSJ9fQ==
```

The `config` value is the Base64-encoded JSON `{"command":"uvx","args":["netlicensing-mcp"],"env":{"NETLICENSING_API_KEY":"YOUR_API_KEY"}}`.

Remote server in HTTP mode:

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

### Claude Desktop

In Claude Desktop open **Settings → Developer → Edit Config**. This opens (and creates, if needed) `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "uvx",
      "args": ["netlicensing-mcp"],
      "env": {
        "NETLICENSING_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Or use the official Docker image (stdio):

```json
{
  "mcpServers": {
    "netlicensing": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "NETLICENSING_API_KEY=YOUR_API_KEY",
        "ghcr.io/labs64/netlicensing-mcp:latest"
      ]
    }
  }
}
```

Quit and restart Claude Desktop after saving the file.

Claude Desktop adds remote servers as custom connectors (**Settings → Connectors → Add custom connector**): you enter the server URL and then authenticate with the server, for example with OAuth. Sending a custom request header is not part of that documented flow, and a shared deployment of this server expects each client to send its own API key in a header, so use the local setup above with Claude Desktop.

### JetBrains IDEs (GitHub Copilot)

Click the Copilot icon in the lower right corner, choose **Open Chat**, switch to **Agent** mode, click the tools icon (**Configure your MCP server**) and then **Add MCP Tools**. In the `mcp.json` that opens, add the server under `servers`:

```json
{
  "servers": {
    "netlicensing": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "NETLICENSING_API_KEY=YOUR_API_KEY", "ghcr.io/labs64/netlicensing-mcp:latest"]
    }
  }
}
```

### Other MCP clients

Any client that can start a stdio server works: command `uvx`, arguments `netlicensing-mcp`, and the environment variable `NETLICENSING_API_KEY` (or `NETLICENSING_ALLOW_DEMO=true`). Clients that connect to remote servers with custom headers can use an HTTP deployment with the `X-NetLicensing-API-Key` header.

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
| `MCP_VERBOSE` | No | `false` | Enable verbose debug logging (`true`, `1`, or `yes`). Logs API requests/responses **with sensitive fields automatically redacted** (token paths as `/token/****`). Also turns on the MCP SDK's own DEBUG output, which is not redacted: local debugging only. Can also be set via `-v` CLI flag. |
| `MCP_REDACT_FIELDS` | No | — | Comma-separated list of additional field names to redact from all tool responses and log output (e.g. `MCP_REDACT_FIELDS=ssn,phone`). Extends the built-in default set: `apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`. |
| `MCP_TOOLSETS` | No | `all` | Comma-separated list of toolsets to register (e.g. `licensees,licenses`). Unknown names are ignored with a warning on stderr (also when `all` is given). See [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode). |
| `MCP_READ_ONLY` | No | `false` | Register only read-only tools (`true`, `1`, or `yes`): list, get, `preview_*`, workflows and reference data. Any other value except `false`, `0` or `no` leaves read-only mode off and logs a warning on stderr. See [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode). |

> **\* `NETLICENSING_API_KEY` and demo mode:** If neither `NETLICENSING_API_KEY` nor `NETLICENSING_ALLOW_DEMO=true` is set, the server will **refuse to start** (stdio mode) or return `503 Service Unavailable` for all tool calls (HTTP mode). This prevents accidental use of demo credentials in production.

> **Note on HTTP deployments (e.g. AWS):** When running in HTTP mode over a network, you can skip setting `NETLICENSING_API_KEY` on the server. The MCP server will automatically extract the key per-request if the connecting client provides it via the `X-NetLicensing-API-Key` HTTP header, `Authorization: Bearer <key>` header. Query-parameter keys are not supported, because URLs are logged by proxies and load balancers.

### Reduce the tool list / read-only mode

The server registers <!-- count:tools -->61<!-- /count:tools --> tools by default. Some clients handle long tool lists poorly, and some deployments should never change data. Two environment variables shrink the list when the server starts:

- `MCP_TOOLSETS` registers only the listed toolsets. `all` (the default) registers everything.
- `MCP_READ_ONLY=true` registers only tools annotated as read-only (`readOnlyHint`). Previews (`preview_*`) stay; every create, update, delete, `obtain_bundle`, `transfer_licenses` and `validate_licensee` (it can check out floating sessions or bind nodes) is left out.

When both are set, the toolset filter applies first, then the read-only filter. `netlicensing_server_info` is always registered. When a restriction is active, the server instructions sent to the client say so.

The <!-- count:toolsets -->11<!-- /count:toolsets --> toolsets and their tools are listed in [What it can do](#what-it-can-do) and, with parameters, in [docs/TOOLS.md](docs/TOOLS.md).

```bash
# Only customer and license tools, read-only
MCP_TOOLSETS=licensees,licenses MCP_READ_ONLY=true NETLICENSING_API_KEY=your_key uvx netlicensing-mcp
```

All prompts are always available. Some of their steps call tools that may not be registered (for example `audit_expiry` calls `netlicensing_create_shop_token`, which is not available in read-only mode or without the `tokens` toolset, and the setup prompts create entities, which read-only mode does not allow); the assistant then cannot run those steps. The same goes for tools named in the `suggested_actions` of the two workflows and in the instructions of a preview: in read-only mode a `preview_*` result is impact analysis only, since the update or delete tool that would take its confirmation token is not registered. The `suggested_actions` of error results name only registered tools.

---

## Prompt Templates

The server ships <!-- count:prompts -->11<!-- /count:prompts --> prompt templates. Pick one in Copilot Agent or Claude Desktop, fill in its arguments, and the assistant runs the whole workflow for you with the matching tools.

<!-- prompts:start -->
<!-- Generated by scripts/gen_tools_doc.py from the tool registry. Do not edit by hand; run `python scripts/gen_tools_doc.py`. -->

**Audits:**

| Prompt | Purpose | Arguments |
|---|---|---|
| [`audit_full`](docs/TOOLS.md#audit_full) | Run a full entitlement audit across all customers of a product. | `product_number` |
| [`audit_customer`](docs/TOOLS.md#audit_customer) | Deep-dive audit of a single customer's license health. | `licensee_number` |
| [`audit_expiry`](docs/TOOLS.md#audit_expiry) | Find customers whose licenses expired or expire within N days, with renewal URLs. | `product_number`, `days_threshold` (optional) |
| [`audit_cleanup`](docs/TOOLS.md#audit_cleanup) | Identify inactive, unused, or orphaned licenses for cleanup. | `product_number` |
| [`audit_anomaly`](docs/TOOLS.md#audit_anomaly) | Detect anomalous usage patterns across all customers. | `product_number` |

**Setup and troubleshooting:**

| Prompt | Purpose | Arguments |
|---|---|---|
| [`setup_subscription_product`](docs/TOOLS.md#setup_subscription_product) | Create a product with a Subscription module and one TIMEVOLUME template per plan. | `product_name`, `plans` |
| [`setup_trial`](docs/TOOLS.md#setup_trial) | Add a Try & Buy module to a product: a free, automatic TIMEVOLUME trial template and a FEATURE full-version template. | `product_number`, `trial_days` (optional) |
| [`onboard_customer`](docs/TOOLS.md#onboard_customer) | Create a licensee, assign a license from a template (or a bundle) and validate it with a dry run. | `customer_name`, `product_number`, `licensee_number` (optional), `module_number` (optional), `license_template_number` (optional) |
| [`migrate_customer`](docs/TOOLS.md#migrate_customer) | Preview both licensees and their licenses, then move all licenses from one licensee to another with `netlicensing_transfer_licenses`. | `from_licensee_number`, `to_licensee_number` |
| [`troubleshoot_validation`](docs/TOOLS.md#troubleshoot_validation) | Find out why a licensee's validation fails and how to fix it, without side effects: setup check, dry-run validation, plain-language explanation, customer health. | `licensee_number`, `product_number` (optional), `product_module_number` (optional) |
| [`issue_api_key`](docs/TOOLS.md#issue_api_key) | Pick the least-privilege API key role for a purpose and create the key, which is shown once. | `purpose` |

Argument details (formats, defaults): [docs/TOOLS.md](docs/TOOLS.md#prompts).

<!-- prompts:end -->

**Examples** (prompt name and argument values; how you pick a prompt and fill in its arguments depends on your client):

- `audit_full` product_number="P001"
- `audit_customer` licensee_number="I001"
- `audit_expiry` product_number="P001" days_threshold="30"
- `audit_cleanup` product_number="P001"
- `audit_anomaly` product_number="P001"
- `setup_subscription_product` product_name="Acme Cloud" plans="1 MONTH 9.99 EUR; 1 YEAR 99.00 EUR"
- `setup_trial` product_number="P001" trial_days="14"
- `onboard_customer` customer_name="Acme Corp" product_number="P001" (optional: licensee_number, module_number, license_template_number)
- `migrate_customer` from_licensee_number="I001" to_licensee_number="I002"
- `troubleshoot_validation` licensee_number="I001" (optional: product_number, product_module_number)
- `issue_api_key` purpose="license validation in our desktop app"

The setup prompts follow the server's safety rules: they show the plan and ask for confirmation before each write, never delete anything themselves (a removal goes through the `preview_delete_*` tool and never uses `force_cascade` unless you ask for it), prefer deactivating to deleting, and do not repeat secrets such as a new API key after showing it once.

---

## Troubleshooting

**Run the first-run check**

Ask your assistant to run `netlicensing_server_info` (see [First run](#first-run)): it reports whether a key is configured, whether NetLicensing accepts it and what to do next.

**Check MCP server logs**

Claude Desktop writes this server's stderr to `mcp-server-netlicensing.log` (and general MCP connection messages to `mcp.log`) in its log folder: `~/Library/Logs/Claude` (macOS), `%APPDATA%\Claude\logs` (Windows), `~/.config/Claude/logs` (Linux).

```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp-server-netlicensing.log

# Linux
tail -f ~/.config/Claude/logs/mcp-server-netlicensing.log
```

```powershell
# Windows (PowerShell)
Get-Content "$env:APPDATA\Claude\logs\mcp-server-netlicensing.log" -Wait
```

**Run the MCP Inspector** (browser UI at `http://localhost:5173`)

```bash
mcp dev src/netlicensing_mcp/server.py
```

**Read the error result**

A failed tool call returns `{"error": true, "status": ..., "detail": ...}` (flagged `isError`), where `detail` is NetLicensing's own message. It also carries `hint` (the next step), `suggested_actions` (tools to call next) and `retryable` (whether the same call may succeed later; `retry_after_seconds` on a `429`). `retryable` means the failure is transient, not that repeating the call is safe: a create or update may already have been applied before the error, so check the current state first (for a write that failed with a server error, the hint names a tool to check with). A rejected confirmation token (`confirm_token`) gives an error without `status`: its `hint` points at the matching `preview_*` tool. For example:

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

The hints never contain your API key. A hint about a delete blocked by dependents points at the `preview_delete` tool; it mentions `force_cascade` (for an explicit user request only) and deactivating with `active=false` only when that delete or an update tool for the entity offers them, so not for tokens.

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

`/ready` sends one unauthenticated `GET` to `NETLICENSING_BASE_URL` (3-second timeout); any HTTP answer, even `401` or `404`, counts as reachable; timeouts, connection and other transport/protocol errors, and a malformed URL count as unreachable. The result is cached for 15 seconds (a failure for 5 seconds). An API key is not checked, since in HTTP mode each request brings its own. The reply never contains a key or the upstream response, only the API's host name. If the check itself fails unexpectedly, `/ready` answers `503` with `"reason": "readiness check failed (probe_error)"` (not a statement about NetLicensing; the log names the exception type).

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

For example, in Cursor's `mcp.json` (the commands for Claude Code and VS Code are under [Client setup](#client-setup); Claude Desktop's custom connectors can't send this header):

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
