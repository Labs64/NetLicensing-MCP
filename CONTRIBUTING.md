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
mypy src/ scripts/
python scripts/gen_tools_doc.py --check
```

The tool reference in [docs/TOOLS.md](docs/TOOLS.md) and the tool and prompt tables in the README are generated from the server's registry. After adding or changing a tool, a prompt, a docstring or an annotation, run `python scripts/gen_tools_doc.py` and commit the updated files; don't edit the generated parts by hand.

`tests/test_http_e2e.py` drives the real HTTP app (`build_http_app()`, what `netlicensing-mcp http` serves) end to end against a fake NetLicensing API, so it needs no network and no API key.

### Deploy files

Changes to `deploy/**`, `Dockerfile` or `healthcheck.py` also run the deploy lint workflow (`.github/workflows/netlicensing-deploy-lint.yml`). To run its checks locally (needs [ShellCheck](https://www.shellcheck.net/); keep cfn-lint out of the project environment):

```bash
python -m venv /tmp/cfn-lint-venv
/tmp/cfn-lint-venv/bin/pip install "cfn-lint==1.61.0"   # the version CI pins
/tmp/cfn-lint-venv/bin/cfn-lint deploy/aws/*.yaml
shellcheck deploy/aws/deploy.sh
bash deploy/aws/deploy.sh help                           # must work without AWS credentials
```

The App Runner template ignores cfn-lint rule `W3697` (App Runner is in maintenance mode) in the `Metadata` of its two App Runner resources; any other finding fails the check.

The workflow also builds the Docker image the way the release does (from a `hatch build --target wheel` wheel), starts it in HTTP mode without an API key and checks that the container turns healthy, `/health` answers and `POST /mcp` answers `401`. Locally:

```bash
pip install hatch hatch-vcs && rm -rf dist/ && hatch build --target wheel
docker build -t netlicensing-mcp:ci .
docker run --rm -p 8000:8000 -e MCP_HOST=0.0.0.0 netlicensing-mcp:ci http
curl http://127.0.0.1:8000/health
```

## Guidelines

- New tools follow the `netlicensing_<action>_<entity>` naming and live as thin wrappers in `mcp_tools/<entity>.py` (registered with `@tool` from `app.py`), with the logic in `tools/<entity>.py`.
- Give every tool the right annotation (`_READONLY`, `_WRITE`, `_UPDATE` or `_DELETE`).
- Delete and update operations that change data must go through the preview and confirmation flow.
- Never log or return secrets unredacted.
- Add or update tests for what you change, and add a line to `CHANGELOG.md`.

By contributing you agree that your work is released under the [Apache 2.0 license](LICENSE).
