# Changelog

Release notes for each version are published on the [GitHub Releases page](https://github.com/Labs64/NetLicensing-MCP/releases).

## Unreleased

### Added

- Paging hints on list results: besides `count` (items in this response) a list result now carries the paging data NetLicensing reports — `total`, `page` (0-based), `total_pages`, `has_more` and, when there is a next page, `page_size`. Paged list tools add `next_page_hint`, the JSON-quoted `filter` value that fetches the next page. Fields the API does not send are left out; payment methods, licensing models, license types and countries are not paged.
- `netlicensing_list_bundles` accepts an optional `filter` (e.g. `active=true`, or `page=1;items=100` for the next page), like the other list tools.
- Error results now say what to do next: besides `error`, `status` and `detail` they carry `hint` (one actionable sentence), `suggested_actions` (names of registered tools, e.g. `netlicensing_list_licensees` when a licensee was not found) and `retryable` (`true` for 429, 5xx, timeouts and unreachable API; `retry_after_seconds` from `Retry-After` on 429). A missing entity (NetLicensing answers `400` `NotFoundException`), a duplicate number, a delete blocked by dependents, bad credentials, a too-low key role and a feature outside the pricing plan each get their own hint. Rejected confirmation tokens point at the matching `preview_*` tool. Hints never contain the API key, the `detail` text or more of the base URL than its host.
- `MCP_TOOLSETS` (comma list of toolsets: `products`, `bundles`, `modules`, `templates`, `licensees`, `licenses`, `tokens`, `transactions`, `payments`, `system`, `workflows`; default `all`) and `MCP_READ_ONLY=true` (only tools annotated read-only) shrink the registered tool list. `netlicensing_server_info` is always registered, and the server instructions mention an active restriction. Without these variables all 61 tools are registered as before.
- Structured tool output: every tool result now carries `structuredContent` (the same JSON object as the text content; non-object results as `{"result": ...}`), every tool declares an `outputSchema`, and error results set `isError`. The text content is unchanged.

### Changed

- `structuredContent` used to be the JSON *string* wrapped as `{"result": "..."}` (the MCP SDK default for tools that return `str`); it is now the parsed object. Error results (`{"error": true, ...}`) used to be sent with `isError: false`.
