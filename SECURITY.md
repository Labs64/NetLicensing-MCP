# Security Policy

NetLicensing MCP Server handles API keys and license data, so we take security reports seriously.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub:
[Report a vulnerability](https://github.com/Labs64/NetLicensing-MCP/security/advisories/new).

If you cannot use GitHub, contact Labs64 through [netlicensing.io](https://netlicensing.io).

Please include:

- what you found and which version is affected,
- steps to reproduce it,
- what an attacker could do with it.

We aim to acknowledge reports within 3 business days and to keep you updated until a fix ships.

## Supported versions

Only the latest release receives security fixes.

## What the server does to protect you

- No silent fallback to demo credentials. Without an API key the server refuses to start unless `NETLICENSING_ALLOW_DEMO=true`.
- Secrets (`apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`) are masked in tool responses and logs. Request log lines show token paths as `/token/****`, and the HTTP libraries' own request/response logging (`httpx`, `httpcore`, `sse_starlette`), which would write full token numbers and newly created keys, is held at `WARNING` in every mode.
- Credentials such as API tokens and shop URLs are shown in full once, when created; later reads (`get_token` / `list_tokens`), delete previews, delete messages and confirmation errors show them only masked.
- Destructive operations need a two-step confirmation (preview, then a single-use token that expires after 5 minutes).
- In HTTP mode, each request uses its own API key and keys are never accepted in URLs.

## Hardening tips

- Use the least powerful API key role that does the job (licensee, analytics, operation, maintenance or admin).
- Never set `NETLICENSING_ALLOW_DEMO` in production.
- Use verbose logging (`-v` / `MCP_VERBOSE`) for local debugging only. It also turns on the MCP SDK's own DEBUG output (for example a line per incoming message), which this server does not redact. Don't ship or keep verbose logs.
- Serve HTTP mode behind HTTPS only.
