<p align="center"><img src="https://raw.githubusercontent.com/Labs64/NetLicensing-MCP/refs/heads/master/assets/banner.jpg"></p>

# NetLicensing MCP Server

<!-- mcp-name: io.github.Labs64/netlicensing-mcp -->

[![CI](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml/badge.svg)](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Labs64.IO Ecosystem](https://img.shields.io/badge/Labs64.IO-Ecosystem-E14817.svg?logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9Ii01IC01IDE1NSAxNTUiPjxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik0zIDNoMTM5djEzOUgzWk02OSAzdjEzOWg3VjNaTTQzIDQzdjU5aDI2VjQzWk03NiA0M3Y1OWgyNlY0M1oiLz48cGF0aCBmaWxsPSIjYmJiIiBkPSJNNDkgNDloNDd2NDdINDlaIi8%2BPC9zdmc%2B)](https://labs64.io)

[![PyPI](https://img.shields.io/pypi/v/netlicensing-mcp)](https://pypi.org/project/netlicensing-mcp/)
[![GHCR](https://img.shields.io/github/v/release/Labs64/NetLicensing-MCP?label=ghcr.io%2Flabs64%2Fnetlicensing-mcp&logo=docker&logoColor=white&style=flat-square)](https://github.com/Labs64/NetLicensing-MCP/pkgs/container/netlicensing-mcp)
[![Docker Hub](https://img.shields.io/docker/v/labs64/netlicensing-mcp?logo=docker&logoColor=white&label=Docker%20Hub&color=2496ED)](https://hub.docker.com/r/labs64/netlicensing-mcp)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-netlicensing--mcp-blue?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyek0xMSAxN3YtNkg5bDMtNCAzIDRoLTJ2NmgtMnoiLz48L3N2Zz4=&style=flat-square)](https://registry.modelcontextprotocol.io/?q=netlicensing-mcp)

**The official [Labs64 NetLicensing](https://netlicensing.io) MCP server.** Connect your AI assistant to NetLicensing and manage products, customers, licenses and entitlements by asking for what you need. It works with Claude Desktop, Claude Code, Cursor, GitHub Copilot (VS Code and JetBrains) and any other MCP client.

- **Support teams:** find out why a customer can't use the product, renew or transfer a license, without opening the console.
- **Admins:** audit an account, clean up unused licenses, run one shared server for a team.
- **Developers and vendors:** set up products, license templates and shop checkouts, and test a licensing model while you build it.

---

## Setup

The server runs on your machine, started by your AI client over stdio. Three steps:

**1. Get an API key.** Sign in at [ui.netlicensing.io](https://ui.netlicensing.io), open your API keys and create one. No account yet? Use [demo mode](#demo-mode).

**2. Add the server to your client.** You need [uv](https://docs.astral.sh/uv/) (for `uvx`) or Docker. Replace `YOUR_API_KEY` with your key.

**3. Check it** with [First run](#first-run).

### Claude Code

```bash
claude mcp add netlicensing -e NETLICENSING_API_KEY=YOUR_API_KEY -- uvx netlicensing-mcp
```

The default scope `local` loads the server in the current project, for you only. `--scope user` loads it everywhere; `--scope project` writes it to the project's `.mcp.json` for version control (then don't put a real key on the command line).

### VS Code / GitHub Copilot

```bash
code --add-mcp '{"name":"netlicensing","type":"stdio","command":"uvx","args":["netlicensing-mcp"],"env":{"NETLICENSING_API_KEY":"YOUR_API_KEY"}}'
```

On Windows `cmd.exe` and older PowerShell, single-quoted JSON doesn't work. And to keep the key out of the file in any case, create `.vscode/mcp.json` in your workspace; VS Code then asks for the key in a hidden input box:

```json
{
  "inputs": [
    { "type": "promptString", "id": "netlicensing-api-key", "description": "NetLicensing API key", "password": true }
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

### Cursor

Add this to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

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

To keep the key out of the file, write `"NETLICENSING_API_KEY": "${env:NETLICENSING_API_KEY}"` and set the variable in the environment Cursor starts from. Or paste this install link into your browser's address bar; Cursor asks before installing, and you replace `YOUR_API_KEY` afterwards:

```text
cursor://anysphere.cursor-deeplink/mcp/install?name=netlicensing&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJuZXRsaWNlbnNpbmctbWNwIl0sImVudiI6eyJORVRMSUNFTlNJTkdfQVBJX0tFWSI6IllPVVJfQVBJX0tFWSJ9fQ==
```

The `config` value is the Base64-encoded JSON `{"command":"uvx","args":["netlicensing-mcp"],"env":{"NETLICENSING_API_KEY":"YOUR_API_KEY"}}`.

### Claude Desktop

Open **Settings → Developer → Edit Config**. This opens `claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`, Linux `~/.config/Claude/`). Add the same `mcpServers` block as for Cursor, save, and restart the app.

### JetBrains IDEs (GitHub Copilot)

Click the Copilot icon (lower right), **Open Chat**, switch to **Agent** mode, click the tools icon (**Configure your MCP server**), then **Add MCP Tools**. In the `mcp.json` that opens:

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

### Other clients, Docker and pip

Anything that can start a stdio server works: command `uvx`, argument `netlicensing-mcp`, environment `NETLICENSING_API_KEY`. To use Docker instead of `uvx`, set the command to `docker` with the arguments from the JetBrains example. With pip: `pip install netlicensing-mcp`, then run `netlicensing-mcp`.

### Demo mode

No key? Demo mode uses the NetLicensing sandbox with demo credentials. It is for trying things out, stdio only, and must never be used in production. Every JSON result is tagged `"demo_mode": true`, and a warning is logged every 60 seconds.

```bash
claude mcp add netlicensing-demo -e NETLICENSING_ALLOW_DEMO=true -- uvx netlicensing-mcp
```

In a JSON config, put `"NETLICENSING_ALLOW_DEMO": "true"` in `env` instead of the key. Without a key and without this flag the server refuses to start; it never falls back to demo credentials silently.

### First run

Ask your assistant: *"Run netlicensing_server_info and tell me if the setup is OK."* It checks the setup and makes one small read-only call (it lists one product) to confirm that the API is reachable and accepts your key. The result never contains the key:

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

- `status` is `ok`, `warning` (demo mode; a valid key whose role may not list products, `403`; or an API error that says nothing about the key) or `error` (no key, key rejected with `401`, API unreachable).
- `auth.source` is `env`, `header` (HTTP mode), `demo` or `none`. `auth.valid` is `true` when NetLicensing accepted the key, `false` when it rejected it, `null` when that couldn't be checked.
- `next_steps` says in plain words what to fix. Pass `check_connection=false` to skip the API call (then `ok` only means a key is configured).

To share one server with a whole team instead, see [Run it as a shared server](#run-it-as-a-shared-server).

---

## What can you ask?

- *"List all products in my account."*
- *"Create a licensee for `customer@example.com` under product PTEST."*
- *"Does licensee L001 have a valid license? If not, tell me why."*
- *"Which licenses expire in the next 30 days?"*
- *"Find licensees with no active license so I can clean them up."*
- *"Generate a shop URL so L001 can renew on their own."*
- *"Move all licenses from L001 to L002."*
- *"Create a read-only API key for licensee L001."*

[docs/EXAMPLES.md](docs/EXAMPLES.md) walks through six vendor scenarios with the tool calls behind them. Licensing models (Try & Buy, Subscription, Rental, Floating, Multi-Feature, Pay-per-Use, Quota, Node-Locked and more) are described in the [NetLicensing docs](https://netlicensing.io/wiki/licensing-models); `netlicensing_list_licensing_models` shows what your account offers.

---

## Tools

<!-- count:tools -->61<!-- /count:tools --> tools cover products, modules, license templates, licensees, licenses, bundles, tokens, transactions and payment methods, grouped into toolsets (see [Reduce the tool list / read-only mode](#reduce-the-tool-list--read-only-mode)). Two read-only workflows, `get_customer_health` and `explain_validation`, return answers instead of raw data. `preview_*` tools show what a change will affect before you confirm it.

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
| [`netlicensing_list_countries`](docs/TOOLS.md#netlicensing_list_countries) | List countries | R | List countries available for VAT and localization settings (249 without filters). |
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

- **Lists** always return `{"type": "list", "count": ..., "items": [...]}`, even for zero or one result. They take `page` (0-based), `page_size` (1-100, default 25) and `compact=true` (only type, number, name, status, active). Results also carry `total`, `page`, `total_pages` and `has_more`; when more pages exist, `next_page_hint` holds the exact `filter` value for the next one. Payment methods, licensing models, license types and countries are not paged by NetLicensing. `netlicensing_list_countries` takes `search` and `eu_only` instead.
- **Filters:** `filter` takes NetLicensing's `key=value;key=value` syntax. NetLicensing ignores some filter fields on some endpoints, so the server re-applies `active`, `status` and `tokenType` itself.
- **Invalid input fails early.** Identifiers with `/ \ ? # %`, whitespace or control characters, empty identifiers, and values outside a known list (license type, transaction status, time-volume period, licensing model, VAT mode, secret mode, API key role) are rejected before any request, with the allowed values in the message.
- Get, create and update tools return one object. Every tool accepts `include_raw=true` to add the original NetLicensing response.
- Every result is JSON text plus the same object as `structuredContent`; failed calls are flagged `isError`, and every tool declares an `outputSchema`. Tools also declare whether they read, write or delete, so clients can ask for approval at the right moments.

---

## Prompt templates

<!-- count:prompts -->11<!-- /count:prompts --> ready-made prompts run an audit or walk you through a setup. Pick one in your client, fill in its arguments, and the assistant runs the whole workflow with the matching tools. They ask for confirmation before each write and never delete anything themselves.

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

**Examples** (prompt name and argument values; how you pick a prompt depends on your client):

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

All prompts are always available, but steps that need an unregistered tool (for instance `audit_expiry` creating shop tokens in read-only mode) can't run.

---

## Configuration

All variables are optional, but you need either `NETLICENSING_API_KEY` or demo mode in stdio.

| Variable | Default | Description |
|---|---|---|
| `NETLICENSING_API_KEY` | none | Your API key. Required in stdio unless demo mode is on. **Not used in HTTP mode**, where each request brings its own key. |
| `NETLICENSING_ALLOW_DEMO` | `false` | `true` enables sandbox demo mode (stdio only). Never in production. |
| `NETLICENSING_BASE_URL` | `https://go.netlicensing.io/core/v2/rest` | Override the REST API base URL (for example on-prem). |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`; also a positional CLI argument. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | HTTP bind address (HTTP mode only). |
| `MCP_TOOLSETS` | `all` | Toolsets to register, comma-separated. See below. |
| `MCP_READ_ONLY` | `false` | `true`, `1` or `yes` registers read-only tools only. See below. |
| `MCP_REDACT_FIELDS` | none | Extra field names to redact, e.g. `ssn,phone`. |
| `MCP_VERBOSE` | `false` | `true`, `1`, `yes` or `-v`: debug-log API traffic. Local debugging only: it also enables the MCP SDK's DEBUG output, which is not redacted, so don't keep those logs. |
| `MCP_CONSOLE_BASE_URL` | `https://ui.netlicensing.io/#` | Base for the `console_url` links in results. |

Invalid values in `MCP_TOOLSETS` or `MCP_READ_ONLY` are ignored with a warning on stderr. Logs always go to stderr.

### Reduce the tool list / read-only mode

Some clients handle long tool lists poorly, and some deployments should never change data. Two variables shrink the list at startup:

- `MCP_TOOLSETS` registers only the listed toolsets: `products`, `bundles`, `modules`, `templates`, `licensees`, `licenses`, `tokens`, `transactions`, `payments`, `system`, `workflows`, or `all`.
- `MCP_READ_ONLY=true` keeps only read-only tools: lists, gets, `preview_*`, workflows and reference data. Everything that creates, updates or deletes is left out, and so are `obtain_bundle`, `transfer_licenses` and `validate_licensee` (it can check out floating sessions or bind nodes).

The toolset filter applies first, then read-only. `netlicensing_server_info` is always there, and the server tells the client when a restriction is active. In read-only mode a `preview_*` result is impact analysis only, since the tool that would take its confirmation token isn't registered.

```bash
# Only customer and license tools, read-only
MCP_TOOLSETS=licensees,licenses MCP_READ_ONLY=true NETLICENSING_API_KEY=your_key uvx netlicensing-mcp
```

---

## Security

- **Deletes need confirmation.** A delete first returns a preview (with `requires_force_cascade` and `blocking_dependencies` when other items depend on it) and a single-use token that expires after 5 minutes. Nothing is deleted until you send the token back, with the same `force_cascade` value it was issued for. `force_cascade` removes dependent items too and is only used when you ask for it.
- **Sensitive updates need confirmation too:** product `vat_mode` and `licensee_auto_create`, license template price, currency and active state, and payment method active state. The token is bound to the exact values you previewed; different arguments are rejected. A preview that changes nothing returns `no_change` and no token.
- **Secrets are masked** in every response and log line: `apiKey`, `licenseeSecret`, `nodeSecret`, `password` and `secret` fields (long values keep their first 3 and last 4 characters, like `pk_****W3Od`; short ones become `****`). Payment method credentials are always `****`. Add fields with `MCP_REDACT_FIELDS`. Token numbers are masked in lists; you can pass a masked number from `list_tokens` to `get_token`, `preview_delete_token` or `delete_token` when it identifies exactly one token.
- **Credentials appear once.** `create_api_token` and `create_shop_token` mark their response `"shown_once": true`; later reads are masked.
- **Errors are short and safe:** no stack traces, internal class names or gateway HTML reach your assistant, and error hints never contain your key.
- **No silent demo credentials**, and in HTTP mode every request needs its own key in a header (never in the URL, since URLs get logged); a request without one gets `401` before any tool runs.

More in [SECURITY.md](SECURITY.md).

---

## Troubleshooting

**Start with `netlicensing_server_info`.** It reports whether a key is configured, whether NetLicensing accepts it and what to do next.

**Read the error result.** A failed call returns `{"error": true, "status": ..., "detail": ...}` (flagged `isError`), where `detail` is NetLicensing's own short message, plus `hint` (the next step), `suggested_actions` (tools to call next) and `retryable`. `retryable` means the failure is transient, not that repeating is safe: a write may already have been applied, so check the current state first.

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
| `400` | Validation or business rule. NetLicensing also reports a **missing entity** (`Requested … does not exist.`), a duplicate number and a delete blocked by dependents as `400`. | no |
| `401` / `403` | Missing or invalid key / key role too low. A `403` from a gateway (not NetLicensing) is described as blocked input, not a role problem. | no |
| `402` | Operation not in your pricing plan. | no |
| `429` | Over your plan's rate limit; wait `retry_after_seconds`. | yes |
| `500`, `502`, `504` | NetLicensing error, API unreachable or timed out. | yes |
| `503` | No API key configured. | no |

**Common issues**

| Symptom | Likely cause and fix |
|---|---|
| `401 Unauthorized` | Invalid or expired key. Create a new one at [ui.netlicensing.io](https://ui.netlicensing.io). |
| Server not listed in Claude | JSON syntax error in the config. Check it with `python -m json.tool claude_desktop_config.json`. |
| `uvx: command not found` | Install uv: `pip install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv). |
| Server exits immediately (stdio) | Neither `NETLICENSING_API_KEY` nor `NETLICENSING_ALLOW_DEMO=true` is set. |
| `401` on every request (HTTP mode) | The client sends no `X-NetLicensing-API-Key` or `Authorization: Bearer` header. |
| Demo data instead of live data | The key isn't reaching the server, and demo mode is on. Export the key in the shell that starts the client, and unset `NETLICENSING_ALLOW_DEMO`. |
| "Invalid identifier" | Identifiers can't be empty or contain `/ \ ? # %`, whitespace or control characters. |

**Logs.** Claude Desktop writes the server's stderr to `mcp-server-netlicensing.log` in its log folder (`~/Library/Logs/Claude` on macOS, `%APPDATA%\Claude\logs` on Windows, `~/.config/Claude/logs` on Linux); on macOS, `tail -f ~/Library/Logs/Claude/mcp-server-netlicensing.log`. To poke at the server in a browser UI (`http://localhost:5173`), run `mcp dev src/netlicensing_mcp/server.py` from a checkout.

---

## Run it as a shared server

HTTP mode serves many teams from one deployment, because each request brings its own key:

```bash
docker run -d -p 8000:8000 -e MCP_HOST=0.0.0.0 ghcr.io/labs64/netlicensing-mcp:latest http
# or, without Docker: python -m netlicensing_mcp.server http
```

Labs64 does not run a public hosted endpoint: a shared server is one you run yourself, for example on AWS Fargate (below). Clients send the key as `X-NetLicensing-API-Key: your_key` or `Authorization: Bearer your_key`. Don't set `NETLICENSING_API_KEY` on the server; it isn't used.

Point clients at your deployment's URL (`https://YOUR_DOMAIN/mcp`, or the load balancer's `http://ALB_DNS_NAME/mcp` for a quick test):

```bash
# Claude Code
claude mcp add --transport http netlicensing https://YOUR_DOMAIN/mcp --header "X-NetLicensing-API-Key: YOUR_API_KEY"
```

```jsonc
// Cursor: mcpServers.netlicensing
{ "url": "https://YOUR_DOMAIN/mcp", "headers": { "X-NetLicensing-API-Key": "YOUR_API_KEY" } }

// VS Code: servers.netlicensing (use the inputs block from Setup to avoid typing the key into the file)
{ "type": "http", "url": "https://YOUR_DOMAIN/mcp", "headers": { "X-NetLicensing-API-Key": "${input:netlicensing-api-key}" } }
```

Claude Desktop can't connect to it: its custom connectors can't send the API key header. Use the local setup there.

Two unauthenticated probes come with HTTP mode:

| Endpoint | Answers | Use it for |
|---|---|---|
| `GET /health` | Always `200` `{"status":"ok","server":"netlicensing-mcp"}` while the process serves HTTP. | Load balancer and container health checks (the Docker `HEALTHCHECK` uses it). |
| `GET /ready` | `200` `{"status":"ready",...}` when the MCP endpoint runs and the NetLicensing API answers, else `503` with `"status":"not_ready"` and a `reason`. | Monitoring and post-deploy checks. |

`/ready` sends one credential-less `GET` to `NETLICENSING_BASE_URL` (3 s timeout; any HTTP answer counts as reachable) and caches the result for 15 s (5 s after a failure). It reports only the API's host name.

### AWS

`deploy/aws/deploy.sh` deploys to **ECS Fargate** behind an Application Load Balancer (App Runner is kept only for accounts that already use it):

```bash
cd deploy/aws
./deploy.sh fargate                                   # quick test, plain HTTP, sandbox keys only
./deploy.sh fargate --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id   # production HTTPS
```

HTTPS needs a DNS CNAME from your domain to the load balancer. Step by step, including client setup: [deploy/aws/README.md](deploy/aws/README.md).

---

## Development

```bash
git clone https://github.com/Labs64/NetLicensing-MCP && cd NetLicensing-MCP
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" && pip install hatch hatch-vcs
cp .env.example .env                                  # add your API key
mcp dev src/netlicensing_mcp/server.py                # MCP Inspector
pytest tests/ -v                                      # tests
hatch build --target wheel                            # local wheel
docker build -t ghcr.io/labs64/netlicensing-mcp:latest .
```

Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) first and open an issue before anything big. Report security problems as described in [SECURITY.md](SECURITY.md). Release notes for each version are published on the [GitHub Releases page](https://github.com/Labs64/NetLicensing-MCP/releases).

## License

Apache 2.0, see [LICENSE](LICENSE).

---

[![NetLicensing-MCP MCP server](https://glama.ai/mcp/servers/Labs64/NetLicensing-MCP/badges/card.svg)](https://glama.ai/mcp/servers/Labs64/NetLicensing-MCP)
