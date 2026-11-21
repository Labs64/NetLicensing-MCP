# Docker MCP Registry submission

Artifacts for https://github.com/docker/mcp-registry (see its CONTRIBUTING.md, "Adding a Local MCP Server").
Image: `labs64/netlicensing-mcp` (published to Docker Hub by `netlicensing-release.yml`).

## Steps
1. Fork `docker/mcp-registry`, then copy `netlicensing-mcp/` to `servers/netlicensing-mcp/` in the fork.
2. Set `source.commit` in `server.yaml` to the commit of the release being submitted.
3. Test locally: `task catalog -- netlicensing-mcp` then
   `docker mcp catalog import $PWD/catalogs/netlicensing-mcp/catalog.yaml`; enable it in Docker Desktop's MCP Toolkit
   with a sandbox API key; `docker mcp catalog reset` afterwards.
4. Open the PR and share test credentials via the form linked in CONTRIBUTING.md.

`tools.json` is generated from the server (so the build does not need a live API key); regenerate it when tools change.
