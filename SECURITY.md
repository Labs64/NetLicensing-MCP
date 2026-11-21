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
- Secrets (`apiKey`, `licenseeSecret`, `nodeSecret`, `password`, `secret`) are masked in tool responses and logs.
- Credentials such as API tokens and shop URLs are shown in full once, when created.
- Destructive operations need a two-step confirmation (preview, then a single-use token that expires after 5 minutes).
- In HTTP mode, each request uses its own API key and keys are never accepted in URLs.

## Hardening tips

- Use the least powerful API key role that does the job (licensee, analytics, operation, maintenance or admin).
- Never set `NETLICENSING_ALLOW_DEMO` in production.
- Serve HTTP mode behind HTTPS only.
