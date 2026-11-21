# Changelog

Release notes for each version are published on the [GitHub Releases page](https://github.com/Labs64/NetLicensing-MCP/releases).

## Unreleased

### Added

- Structured tool output: every tool result now carries `structuredContent` (the same JSON object as the text content; non-object results as `{"result": ...}`), every tool declares an `outputSchema`, and error results set `isError`. The text content is unchanged.

### Changed

- `structuredContent` used to be the JSON *string* wrapped as `{"result": "..."}` (the MCP SDK default for tools that return `str`); it is now the parsed object. Error results (`{"error": true, ...}`) used to be sent with `isError: false`.
