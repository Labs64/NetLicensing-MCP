# netlicensing-mcp

<!-- mcp-name: io.github.yourusername/netlicensing-mcp -->

[![NetLicensing MCP - CI](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml/badge.svg)](https://github.com/Labs64/NetLicensing-MCP/actions/workflows/netlicensing-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/netlicensing-mcp)](https://pypi.org/project/netlicensing-mcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

MCP (Model Context Protocol) server for the [Labs64 NetLicensing](https://netlicensing.io) REST API.  
Lets Claude, GitHub Copilot, and any MCP-compatible AI agent manage your software licenses conversationally.

---

## Features

| Area | Tools |
|---|---|
| **Products** | list, get, create, update, delete |
| **Product Modules** | list, get, create, update, delete |
| **License Templates** | list, get, create, update, delete |
| **Licensees** | list, get, create, update, delete, validate, transfer |
| **Licenses** | list, get, create, update (activate/deactivate), delete |
| **Tokens** | list, create shop URL, create API token, revoke |
| **Audit Prompts** | full account, single customer, expiry sweep, cleanup, anomaly detection |

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
  ghcr.io/yourusername/netlicensing-mcp:latest
```

> **No API key?** Leave `NETLICENSING_API_KEY` empty to use NetLicensing's built-in demo
> credentials against sandbox data.

---

## Configuration

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

### VS Code / GitHub Copilot

The repo ships a `.vscode/mcp.json` that auto-configures Copilot Agent mode.
Set `NETLICENSING_API_KEY` in your shell environment or a `.env` file and click
**Start** in the editor banner that appears above `mcp.json`.

### JetBrains / IntelliJ IDEA

In Copilot Chat → Agent mode → Tools icon → **Add More Tools…** — paste the
same JSON block as the Claude Desktop config above.

---

## Development

```bash
git clone https://github.com/yourusername/netlicensing-mcp
cd netlicensing-mcp

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
cp .env.example .env            # add your API key

# Run the MCP Inspector (browser UI at http://localhost:5173)
mcp dev src/netlicensing_mcp/server.py

# Run tests
pytest tests/ -v
```

### HTTP mode (for remote / shared deployments)

```bash
python -m netlicensing_mcp.server http
# Server listens on 0.0.0.0:8000
```

---

## Audit Prompt Templates

Five built-in prompts accessible in Copilot Agent and Claude Desktop:

| Prompt | Purpose |
|---|---|
| `license_audit_full` | End-to-end account audit for a product |
| `license_audit_customer` | Deep-dive on a single licensee |
| `license_audit_expiry` | Find licenses expiring within N days + generate renewal URLs |
| `license_audit_cleanup` | Identify inactive / orphaned licenses for cleanup |
| `license_audit_anomaly` | Detect unusual usage patterns across all customers |

---

## Deployment

### Publish a release to PyPI + GHCR + MCP Registry

```bash
git tag v1.0.0
git push origin v1.0.0
```

The `publish.yml` GitHub Actions workflow automatically:
1. Runs the full test suite
2. Publishes to PyPI (via OIDC trusted publishing — no token needed)
3. Builds and pushes a Docker image to `ghcr.io`
4. Registers the server in the MCP Registry
5. Creates a GitHub Release with install instructions

#### One-time setup required
- **PyPI**: configure trusted publishing for this repo at [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)
- **MCP Registry**: add `MCP_PUBLISHER_TOKEN` to your repo secrets (Settings → Secrets → Actions)

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
