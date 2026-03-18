# NetLicensing MCP Server
 
<!-- mcp-name: io.github.Labs64/netlicensing-mcp -->
 
[![CI](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml/badge.svg)](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/netlicensing-mcp)](https://pypi.org/project/netlicensing-mcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**The official [Labs64 NetLicensing](https://netlicensing.io) MCP Server** — a natural language interface that lets AI agents manage software licenses, customers, and entitlements through conversational commands.
 
Works with Claude Desktop, GitHub Copilot (Agent mode), VS Code, JetBrains / IntelliJ IDEA, and any other MCP-compatible client.
 
---
 
## Why use this?
 
- **Natural Language Licensing** — Ask your AI assistant to create products, issue licenses, validate entitlements, and generate shop URLs without touching the NetLicensing UI or writing API calls.
- **Full API coverage** — Various tools spanning the entire NetLicensing REST API: products, modules, templates, licensees, licenses, bundles, tokens, transactions, and payment methods.
- **Built-in audit prompts** — Five ready-to-run prompt templates for account audits, expiry sweeps, anomaly detection, and cleanup workflows.
- **Safe by default** — All delete operations expose a `force_cascade` option; nothing is silently cascaded.
- **Zero-dependency quick start** — Run with `uvx` or Docker without a local Python install.
 
---
 
## What can you ask?
 
Once connected, you can talk to NetLicensing in plain language:
 
- *"List all products in my NetLicensing account."*
- *"Create a new licensee for customer@example.com under product PTEST."*
- *"Validate the license for licensee L001 — does it pass?"*
- *"Generate a shop URL for licensee L001 so they can self-serve their renewal."*
- *"Which licenses are expiring in the next 30 days?"*
- *"Find any licensees with no active licenses — flag them for cleanup."*
- *"Transfer all licenses from licensee L001 to L002."*
- *"Create an API key token scoped to read-only access."*
- *"Show me all transactions from the last month."*
 
---
 
## Features
 
| Area | Tools |
|---|---|
| **Products** | list, get, create, update, delete |
| **Product Modules** | list, get, create, update, delete |
| **License Templates** | list, get, create, update, delete |
| **Licensees** | list, get, create, update, delete, validate, transfer |
| **Licenses** | list, get, create, update (activate/deactivate), delete |
| **Bundles** | list, get, create, update, delete, obtain |
| **Tokens** | list, get, create shop URL, create API token, revoke |
| **Transactions** | list, get, create, update |
| **Payment Methods** | list, get, update |
| **Utilities** | list licensing models, list license types |
| **Audit Prompts** | full account, single customer, expiry sweep, cleanup, anomaly detection |
| **Delete Safety** | `force_cascade` option on all delete tools |
 
---
 
## Quick Start
 
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
 
```bash
docker run -i --rm \
  -e NETLICENSING_API_KEY=your_key \
  ghcr.io/labs64/netlicensing-mcp:latest
```
 
> **No API key?** Leave `NETLICENSING_API_KEY` empty to run against NetLicensing's built-in
> sandbox with demo credentials — no account required.
 
---
 
## Configuration
 
### Environment Variables
 
| Variable | Required | Default | Description |
|---|---|---|---|
| `NETLICENSING_API_KEY` | No* | *(demo mode)* | NetLicensing API key. Leave empty to use sandbox demo credentials. |
| `NETLICENSING_BASE_URL` | No | `https://go.netlicensing.io/core/v2/rest` | Override the NetLicensing REST API base URL (e.g. for on-prem deployments). |

---
 
### Claude Desktop
 
Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
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
 
### VS Code / GitHub Copilot
 
The repo ships a `.vscode/mcp.json` that auto-configures Copilot Agent mode.
Set `NETLICENSING_API_KEY` in your shell environment or a `.env` file, then click
**Start** in the editor banner that appears above `mcp.json`.
 
### JetBrains / IntelliJ IDEA
 
In Copilot Chat → Agent mode → Tools icon → **Add More Tools…** — paste the
same JSON block shown in the Claude Desktop section above.
 
---
 
## Audit Prompt Templates
 
Five built-in prompts accessible in Copilot Agent and Claude Desktop:
 
| Prompt | Purpose |
|---|---|
| `license_audit_full` | End-to-end account audit for a product |
| `license_audit_customer` | Deep-dive on a single licensee |
| `license_audit_expiry` | Find licenses expiring within N days and generate renewal URLs |
| `license_audit_cleanup` | Identify inactive / orphaned licenses for cleanup |
| `license_audit_anomaly` | Detect unusual usage patterns across all customers |
 
---
 
## Troubleshooting
 
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
 
**Common issues**
 
| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` responses | Invalid or expired API key | Regenerate your key at [ui.netlicensing.io](https://ui.netlicensing.io) |
| Server not listed in Claude | Config file JSON syntax error | Validate with `python -m json.tool claude_desktop_config.json` |
| `uvx: command not found` | `uv` not installed | `pip install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv) |
| Demo data instead of live data | `NETLICENSING_API_KEY` not set | Ensure the env var is exported in the shell that starts the client |
 
---
 
## Development
 
```bash
git clone https://github.com/Labs64/NetLicensing-MCP
cd NetLicensing-MCP
 
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
 
pip install -e ".[dev]"
cp .env.example .env            # add your API key
 
# Run the MCP Inspector
mcp dev src/netlicensing_mcp/server.py
 
# Run tests
pytest tests/ -v
```
 
### HTTP mode (for remote / shared deployments)
 
```bash
python -m netlicensing_mcp.server http
# Server listens on 0.0.0.0:8000
```
 
Use `ngrok` or a reverse proxy to expose the HTTP endpoint to remote MCP clients:
 
```bash
ngrok http 8000
# Then point your client at the generated HTTPS URL
```

---
 
## Contributing
 
Contributions are welcome! Please open an issue or pull request on [GitHub](https://github.com/Labs64/NetLicensing-MCP).
 
For significant changes, open an issue first to discuss the approach.
 
---
 
## License
 
Apache 2.0 — see [LICENSE](LICENSE).
