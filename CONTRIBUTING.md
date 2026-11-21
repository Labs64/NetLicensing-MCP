# Contributing

Thanks for helping improve the NetLicensing MCP Server. Bug reports, ideas and pull requests are all welcome.

## Before you start

- For anything bigger than a small fix, open an issue first so we can agree on the approach.
- Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## Set up

```bash
git clone https://github.com/Labs64/NetLicensing-MCP
cd NetLicensing-MCP
pip install -e ".[dev]"
```

## Check your work

These are the same checks CI runs:

```bash
pytest tests/ -v
ruff check .
ruff format --check .
mypy src/
```

## Guidelines

- New tools follow the `netlicensing_<action>_<entity>` naming and live as thin wrappers in `mcp_tools/<entity>.py` (registered with `@tool` from `app.py`), with the logic in `tools/<entity>.py`.
- Give every tool the right annotation (`_READONLY`, `_WRITE`, `_UPDATE` or `_DELETE`).
- Delete and update operations that change data must go through the preview and confirmation flow.
- Never log or return secrets unredacted.
- Add or update tests for what you change, and add a line to `CHANGELOG.md`.

By contributing you agree that your work is released under the [Apache 2.0 license](LICENSE).
