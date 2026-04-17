# Changelog

All notable changes to **NetLicensing MCP Server** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Version numbers are derived from Git tags via `hatch-vcs`.

## [Unreleased]

### Added
- Input validation for identifiers, emails, currency codes, ISO-8601 dates,
  license types, licensing models, and enum-style fields at the tool boundary.
- `NETLICENSING_HTTP_TIMEOUT` and `NETLICENSING_HTTP_CONNECT_TIMEOUT` environment
  variables to override HTTP client timeouts.
- `[tool.mypy]` baseline configuration in `pyproject.toml`.
- `.pre-commit-config.yaml` with ruff, mypy, and sanity hooks.
- `CHANGELOG.md`.

### Changed
- Tool arguments with known formats (emails, currency, dates, enums) are now
  rejected early with a user-friendly error rather than a raw HTTP 4xx.

## [0.x] — prior releases

See the Git history and GitHub releases:
https://github.com/Labs64/NetLicensing-MCP/releases
