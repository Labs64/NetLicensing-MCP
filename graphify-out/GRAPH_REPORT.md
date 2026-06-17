# Graph Report - .  (2026-06-17)

## Corpus Check
- 61 files · ~59,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 742 nodes · 1285 edges · 60 communities (41 shown, 19 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 143 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_MCP Create Tool Wrappers|MCP Create Tool Wrappers]]
- [[_COMMUNITY_HTTP Client & Demo Mode|HTTP Client & Demo Mode]]
- [[_COMMUNITY_Customer Health Tests|Customer Health Tests]]
- [[_COMMUNITY_Tool Integration Tests|Tool Integration Tests]]
- [[_COMMUNITY_Validation Explain Workflow|Validation Explain Workflow]]
- [[_COMMUNITY_MCP Delete & Preview Tools|MCP Delete & Preview Tools]]
- [[_COMMUNITY_Normalized Response Envelope|Normalized Response Envelope]]
- [[_COMMUNITY_Test Response Fixtures|Test Response Fixtures]]
- [[_COMMUNITY_Multi-Tenant API Key Auth|Multi-Tenant API Key Auth]]
- [[_COMMUNITY_MCP Server Entry Point|MCP Server Entry Point]]
- [[_COMMUNITY_Redaction Test Suite|Redaction Test Suite]]
- [[_COMMUNITY_License Template Tests|License Template Tests]]
- [[_COMMUNITY_Licensee CRUD Tests|Licensee CRUD Tests]]
- [[_COMMUNITY_Product Module Tests|Product Module Tests]]
- [[_COMMUNITY_Transaction Tools|Transaction Tools]]
- [[_COMMUNITY_Async HTTP Client|Async HTTP Client]]
- [[_COMMUNITY_Destructive Op Safety|Destructive Op Safety]]
- [[_COMMUNITY_Delete Preview Guards|Delete Preview Guards]]
- [[_COMMUNITY_License CRUD Tools|License CRUD Tools]]
- [[_COMMUNITY_Redaction Core Logic|Redaction Core Logic]]
- [[_COMMUNITY_Payment Method Tools|Payment Method Tools]]
- [[_COMMUNITY_AWS Deploy Scripts|AWS Deploy Scripts]]
- [[_COMMUNITY_Utility Lookups|Utility Lookups]]
- [[_COMMUNITY_One-Time Token Display|One-Time Token Display]]
- [[_COMMUNITY_Customer Health Server|Customer Health Server]]
- [[_COMMUNITY_MCP Server Manifest|MCP Server Manifest]]
- [[_COMMUNITY_FastMCP & Audit Prompts|FastMCP & Audit Prompts]]
- [[_COMMUNITY_Token Management Tools|Token Management Tools]]
- [[_COMMUNITY_AWS Deployment Docs|AWS Deployment Docs]]
- [[_COMMUNITY_Audit Prompt Templates|Audit Prompt Templates]]
- [[_COMMUNITY_Token Read Redaction|Token Read Redaction]]
- [[_COMMUNITY_API Token Creation|API Token Creation]]
- [[_COMMUNITY_PR Labels & Changelog|PR Labels & Changelog]]
- [[_COMMUNITY_CodeQL Security Analysis|CodeQL Security Analysis]]
- [[_COMMUNITY_AWS Deploy Commands|AWS Deploy Commands]]
- [[_COMMUNITY_Product Banner Assets|Product Banner Assets]]
- [[_COMMUNITY_CI Workflow|CI Workflow]]
- [[_COMMUNITY_Release Pipeline|Release Pipeline]]
- [[_COMMUNITY_Glama Server Manifest|Glama Server Manifest]]
- [[_COMMUNITY_Dry Run Enforcement|Dry Run Enforcement]]
- [[_COMMUNITY_Validation Status Precedence|Validation Status Precedence]]
- [[_COMMUNITY_Redaction Layer Concept|Redaction Layer Concept]]
- [[_COMMUNITY_Package Init|Package Init]]
- [[_COMMUNITY_Explain Validation Tool|Explain Validation Tool]]
- [[_COMMUNITY_List Product Modules|List Product Modules]]
- [[_COMMUNITY_Prompts Init|Prompts Init]]
- [[_COMMUNITY_Redaction Fixtures|Redaction Fixtures]]
- [[_COMMUNITY_Licensee Secret Test|Licensee Secret Test]]
- [[_COMMUNITY_Tools Init|Tools Init]]
- [[_COMMUNITY_Workflow Thresholds|Workflow Thresholds]]
- [[_COMMUNITY_Glama Manifest|Glama Manifest]]
- [[_COMMUNITY_Version Constant|Version Constant]]
- [[_COMMUNITY_MCP Instance|MCP Instance]]
- [[_COMMUNITY_Server Manifest|Server Manifest]]
- [[_COMMUNITY_Response Test|Response Test]]
- [[_COMMUNITY_Strip Output Fields|Strip Output Fields]]
- [[_COMMUNITY_VS Code MCP Config|VS Code MCP Config]]

## God Nodes (most connected - your core abstractions)
1. `_error()` - 63 edges
2. `_wrap_json()` - 41 edges
3. `_json()` - 33 edges
4. `build_health()` - 28 edges
5. `explain_validation()` - 26 edges
6. `nl_get()` - 24 edges
7. `nl_post()` - 23 edges
8. `redact()` - 21 edges
9. `NetLicensingError` - 16 edges
10. `wrap()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `TestJsonDemoModeTag` --uses--> `NetLicensingError`  [INFERRED]
  tests/test_demo_credential_fallback.py → src/netlicensing_mcp/client.py
- `test_audit_full_prompt_content()` --calls--> `register_audit_prompts()`  [INFERRED]
  tests/test_tools.py → src/netlicensing_mcp/prompts/audit.py
- `test_mask_exactly_8_chars()` --calls--> `_mask()`  [EXTRACTED]
  tests/test_redaction.py → src/netlicensing_mcp/redaction.py
- `test_create_licensee_never_echoes_plaintext_secret()` --calls--> `netlicensing_create_licensee()`  [INFERRED]
  tests/test_redaction.py → src/netlicensing_mcp/server.py
- `test_list_tokens_masks_apikey_number()` --calls--> `netlicensing_list_tokens()`  [INFERRED]
  tests/test_redaction.py → src/netlicensing_mcp/server.py

## Import Cycles
- 1-file cycle: `src/netlicensing_mcp/workflows/customer_health.py -> src/netlicensing_mcp/workflows/customer_health.py`
- 1-file cycle: `src/netlicensing_mcp/safety.py -> src/netlicensing_mcp/safety.py`
- 1-file cycle: `src/netlicensing_mcp/workflows/validation_explain.py -> src/netlicensing_mcp/workflows/validation_explain.py`

## Hyperedges (group relationships)
- **Server Tool Request Pipeline** — netlicensing_mcp_server_wrap_json, netlicensing_mcp_responses_wrap, netlicensing_mcp_redaction_redact, netlicensing_mcp_server_json [EXTRACTED 1.00]
- **Destructive Operation Safety Flow** — netlicensing_mcp_safety_make_delete_preview, netlicensing_mcp_safety_issue_token, netlicensing_mcp_safety_validate_and_consume, netlicensing_mcp_safety_token_store [EXTRACTED 1.00]
- **Token Credential Protection Flow** — netlicensing_mcp_redaction_tag_one_time_display, netlicensing_mcp_redaction_redact_token_read, netlicensing_mcp_server_scrub_apikey_console_url, netlicensing_mcp_server_wrap_json_token_read [EXTRACTED 1.00]
- **Shared Thresholds Consumed by Both Workflow Synthesisers** — workflows_thresholds_warn_days, workflows_thresholds_critical_days, workflows_thresholds_warn_quota_pct, workflows_customer_health_build_health, workflows_validation_explain_explain_validation [EXTRACTED 1.00]
- **CustomerHealth Build Pipeline** — workflows_customer_health_build_health, workflows_customer_health_module_row, workflows_customer_health_overall_status_from_validation, workflows_customer_health_overall_status_from_heuristics, workflows_customer_health_build_warnings, workflows_customer_health_build_suggested_actions, workflows_customer_health_summary_line [EXTRACTED 1.00]
- **ValidationExplanation Build Pipeline** — workflows_validation_explain_explain_validation, workflows_validation_explain_classify_module, workflows_validation_explain_explanation_for, workflows_validation_explain_actions_for, workflows_validation_explain_overall_status [EXTRACTED 1.00]
- **Release Pipeline: PyPI + Docker + MCP Registry → GitHub Release** — workflows_netlicensing_release_publish_pypi_job, workflows_netlicensing_release_publish_docker_job, workflows_netlicensing_release_publish_mcp_registry_job, workflows_netlicensing_release_create_release_job [EXTRACTED 1.00]
- **CodeQL Security Analysis Stack (workflow + config + model pack + sanitizer)** — workflows_netlicensing_codeql_codeql_workflow, codeql_codeql_config_security_config, python_models_codeql_pack_python_models_pack, python_models_redact_sanitizer_neutral_model [EXTRACTED 1.00]
- **Validation Explain Test Coverage (fixture sets + synthesiser tests + tool layer tests)** — tests_test_validation_explain_fixtures_customer_health, tests_test_validation_explain_fixtures_validation_explain, concept_validation_explain_synthesiser, tests_test_validation_explain_explain_validation_tests [INFERRED 0.95]

## Communities (60 total, 19 thin omitted)

### Community 0 - "MCP Create Tool Wrappers"
Cohesion: 0.05
Nodes (53): _error(), netlicensing_create_bundle(), netlicensing_create_license_template(), netlicensing_create_licensee(), netlicensing_create_product(), netlicensing_create_product_module(), netlicensing_create_transaction(), netlicensing_get_bundle() (+45 more)

### Community 1 - "HTTP Client & Demo Mode"
Cohesion: 0.06
Nodes (27): Exception, JSONResponse, _allow_demo(), _headers(), is_demo_mode(), NetLicensingError, Return True when ``NETLICENSING_ALLOW_DEMO`` is explicitly opted-in., Return True when the current request will use demo sandbox credentials.      Dem (+19 more)

### Community 2 - "Customer Health Tests"
Cohesion: 0.09
Nodes (42): Pure Synthesiser Pattern (no I/O in workflow modules), Shared Warning Thresholds (P1.8/P1.9), licensee_acme.json fixture, Any, datetime, TestAuthenticated/TestUnauthenticated, licensee(), licensee_inactive() (+34 more)

### Community 3 - "Tool Integration Tests"
Cohesion: 0.05
Nodes (42): Any, Verify that NetLicensingError is raised on non-2xx responses., test_create_bundle(), test_create_product(), test_create_product_all_fields(), test_delete_product(), test_delete_product_force_cascade(), test_error_handling() (+34 more)

### Community 4 - "Validation Explain Workflow"
Cohesion: 0.10
Nodes (39): Validation Explain Synthesiser (P1.9), validate_acme_node_mismatch.json fixture, Any, datetime, explain_validation Test Suite, Fixtures: customer_health, Fixtures: validation_explain, load_ch() (+31 more)

### Community 5 - "MCP Delete & Preview Tools"
Cohesion: 0.08
Nodes (34): _extract_props(), _json(), netlicensing_delete_bundle(), netlicensing_delete_license(), netlicensing_delete_license_template(), netlicensing_delete_token(), netlicensing_preview_delete_bundle(), netlicensing_preview_delete_license() (+26 more)

### Community 6 - "Normalized Response Envelope"
Cohesion: 0.10
Nodes (34): Normalized Response Envelope, _console_base(), console_url(), ENTITY_PATH Mapping, _props_to_dict(), Normalized response envelope for NetLicensing MCP tools (P0.6).  Every entity-re, Normalise a NetLicensing API response into a flat envelope with console_url., Return the Console base URL, stripped of trailing slashes. (+26 more)

### Community 7 - "Test Response Fixtures"
Cohesion: 0.07
Nodes (11): Test suite for netlicensing-mcp. Run with: pytest tests/ -v, test_delete_bundle(), test_delete_bundle_force_cascade(), test_validate_licensee(), test_validate_licensee_all_params(), test_validate_licensee_dry_run(), test_validate_licensee_no_dry_run_by_default(), delete_bundle() (+3 more)

### Community 8 - "Multi-Tenant API Key Auth"
Cohesion: 0.09
Nodes (15): BaseHTTPMiddleware, Per-Request API Key via ContextVar, api_key_ctx ContextVar, ApiKeyMiddleware, Starlette, client(), _make_app(), Regression test for GHSA-x9vc-9ffq-p3gj.  Verifies that the HTTP transport rejec (+7 more)

### Community 9 - "MCP Server Entry Point"
Cohesion: 0.09
Nodes (21): _count_items(), netlicensing_create_license(), netlicensing_get_transaction(), netlicensing_list_licensees(), netlicensing_list_licensing_models(), netlicensing_list_payment_methods(), netlicensing_list_transactions(), netlicensing_update_product_module() (+13 more)

### Community 10 - "Redaction Test Suite"
Cohesion: 0.14
Nodes (15): Recursively redact sensitive fields from *payload*.      Handles two common patt, redact(), Tests for P0.3: Redaction layer.  Covers: - redact() with plain dict keys - reda, test_mask_exactly_8_chars(), test_mcp_redact_fields_empty_does_not_affect(), test_mcp_redact_fields_extends_set(), test_mcp_redact_fields_with_spaces(), test_redact_does_not_touch_non_sensitive_keys() (+7 more)

### Community 11 - "License Template Tests"
Cohesion: 0.10
Nodes (20): test_create_license_template(), test_create_license_template_all_fields(), test_delete_license_template(), test_delete_license_template_force_cascade(), test_get_license_template(), test_list_license_templates(), test_list_license_templates_with_filter(), test_update_license_template() (+12 more)

### Community 12 - "Licensee CRUD Tests"
Cohesion: 0.10
Nodes (20): test_create_licensee(), test_create_licensee_all_fields(), test_delete_licensee(), test_delete_licensee_force_cascade(), test_list_licensees(), test_list_licensees_with_filter(), test_transfer_licenses(), test_update_licensee() (+12 more)

### Community 13 - "Product Module Tests"
Cohesion: 0.10
Nodes (20): test_create_product_module(), test_create_product_module_all_fields(), test_delete_product_module(), test_delete_product_module_force_cascade(), test_get_product_module(), test_list_product_modules(), test_list_product_modules_with_filter(), test_update_product_module() (+12 more)

### Community 14 - "Transaction Tools"
Cohesion: 0.13
Nodes (16): test_create_transaction(), test_create_transaction_all_fields(), test_get_transaction(), test_list_transactions(), test_list_transactions_with_filter(), test_update_transaction(), test_update_transaction_all_fields(), create_transaction() (+8 more)

### Community 15 - "Async HTTP Client"
Cohesion: 0.21
Nodes (15): AsyncClient, close_client(), _get_client(), nl_delete(), nl_get(), nl_post(), nl_put(), _raise_on_error() (+7 more)

### Community 16 - "Destructive Op Safety"
Cohesion: 0.18
Nodes (15): Leave Unchanged Semantics for Optional Fields, Two-Step Confirmation Pattern, issue_token(), make_delete_preview(), make_update_preview(), _purge_expired(), Safety layer: confirmation tokens for destructive and sensitive operations.  Pat, Build a preview response for a sensitive-field update and issue a token. (+7 more)

### Community 17 - "Delete Preview Guards"
Cohesion: 0.17
Nodes (16): netlicensing_delete_licensee(), netlicensing_delete_product(), netlicensing_delete_product_module(), netlicensing_preview_delete_licensee(), netlicensing_preview_delete_product(), netlicensing_preview_delete_product_module(), Preview what would be deleted when deleting a licensee.      Returns the count o, Delete a licensee and all their licenses permanently.      Always requires a two (+8 more)

### Community 18 - "License CRUD Tools"
Cohesion: 0.12
Nodes (15): test_create_license(), test_create_license_all_fields(), test_delete_license(), test_delete_license_force_cascade(), test_get_license(), test_update_license_all_fields(), test_update_license_deactivate(), create_license() (+7 more)

### Community 19 - "Redaction Core Logic"
Cohesion: 0.18
Nodes (14): _effective_fields(), _extra_fields(), _mask(), Redaction layer for NetLicensing MCP (P0.3).  Masks sensitive field values in AP, Redact a single ``{"name": ..., "value": ...}`` property entry., Return additional redact fields from the ``MCP_REDACT_FIELDS`` env var.      The, Merge caller-supplied fields with runtime extensions., Partially mask *value*, keeping the first 3 and last 4 characters.      Examples (+6 more)

### Community 20 - "Payment Method Tools"
Cohesion: 0.15
Nodes (12): test_get_payment_method(), test_list_payment_methods(), test_list_payment_methods_with_filter(), test_update_payment_method(), test_update_payment_method_all_fields(), get_payment_method(), list_payment_methods(), Tools: Payment Methods — vendor payment configuration. (+4 more)

### Community 21 - "AWS Deploy Scripts"
Cohesion: 0.50
Nodes (11): blue(), check_prereqs(), deploy_apprunner(), deploy_fargate(), die(), green(), main(), mirror_to_ecr() (+3 more)

### Community 22 - "Utility Lookups"
Cohesion: 0.18
Nodes (10): test_list_countries(), test_list_license_types(), test_list_licensing_models(), list_countries(), list_license_types(), list_licensing_models(), Tools: Utilities — reference data from the NetLicensing API., Return all license types supported by the service. (+2 more)

### Community 23 - "One-Time Token Display"
Cohesion: 0.22
Nodes (9): One-Time Display for Credentials, Tag a *create* token response as one-time-display.      Adds ``"shown_once": tru, tag_one_time_display(), netlicensing_create_shop_token(), Generate a NetLicensing Shop one-time checkout URL for a customer.      Args:, test_create_shop_token_tagged_shown_once(), test_tag_one_time_display_adds_fields(), test_tag_one_time_display_non_dict_passthrough() (+1 more)

### Community 24 - "Customer Health Server"
Cohesion: 0.22
Nodes (9): netlicensing_get_customer_health(), Return a normalized health summary for one licensee.      Combines licensee deta, test_get_licensee(), test_list_licenses(), test_list_licenses_with_filter(), get_licensee(), Get a specific licensee by number., list_licenses() (+1 more)

### Community 25 - "MCP Server Manifest"
Cohesion: 0.22
Nodes (8): description, homepage, license, name, packages, $schema, title, version

### Community 26 - "FastMCP & Audit Prompts"
Cohesion: 0.29
Nodes (7): FastMCP, Prompt templates for NetLicensing license and entitlements audits., Register NetLicensing license and entitlement audit prompts on the MCP server., register_audit_prompts(), Verify all five audit prompts register without error., test_audit_full_prompt_content(), test_audit_prompts_register()

### Community 27 - "Token Management Tools"
Cohesion: 0.25
Nodes (8): netlicensing_get_token(), netlicensing_list_tokens(), List all active tokens in the account.      Args:         filter: Optional serve, Get details of a specific token.      Args:         token_number: Token identifi, Normalize a token *read* response with extra credential masking.      Applies :f, _wrap_json_token_read(), test_get_token_masks_apikey_number(), test_list_tokens_masks_apikey_number()

### Community 28 - "AWS Deployment Docs"
Cohesion: 0.43
Nodes (7): AGENTS.md Project Documentation, App Runner CloudFormation Template, ECS Fargate CloudFormation Template, AWS Deployment README, Per-Request API Key Multi-Tenancy (HTTP mode), AWS Deployment Options (ECS Fargate vs App Runner), README Project Documentation

### Community 29 - "Audit Prompt Templates"
Cohesion: 0.29
Nodes (7): audit_anomaly Prompt, audit_cleanup Prompt, audit_customer Prompt, audit_expiry Prompt, audit_full Prompt, register_audit_prompts Function, main()

### Community 30 - "Token Read Redaction"
Cohesion: 0.29
Nodes (7): Apply extra masking for the *get_token* / *list_tokens* read paths.      For **A, redact_token_read(), test_redact_token_read_also_applies_default_redact(), test_redact_token_read_masks_apikey_number(), test_redact_token_read_masks_shop_url(), test_redact_token_read_mixed_list(), test_redact_token_read_passthrough_for_unknown_type()

### Community 31 - "API Token Creation"
Cohesion: 0.29
Nodes (7): netlicensing_create_api_token(), Create a scoped API token.      Args:         api_key_role: ROLE_APIKEY_LICENSEE, Strip ``console_url`` from APIKEY token envelopes (single or list).      For API, _scrub_apikey_console_url(), The API key number is visible in the one-time create response., test_create_api_token_shows_full_key_once(), test_create_api_token_tagged_shown_once()

### Community 32 - "PR Labels & Changelog"
Cohesion: 0.40
Nodes (6): Conventional Commits PR Labeling, Release Pipeline (PyPI → Docker → MCP Registry → GitHub Release), PR Labeler Configuration, Release Changelog Configuration, PR Labeler Workflow, Release Workflow

### Community 34 - "CodeQL Security Analysis"
Cohesion: 0.40
Nodes (5): CodeQL Configuration, CodeQL False-Positive Elimination via Neutral Model, CodeQL Python Models Pack, redact() CodeQL Neutral Sanitizer Model, CodeQL Analysis Workflow

### Community 35 - "AWS Deploy Commands"
Cohesion: 0.50
Nodes (5): deploy_apprunner Function, deploy_fargate Function, main Entrypoint, mirror_to_ecr Function, teardown Function

### Community 36 - "Product Banner Assets"
Cohesion: 0.67
Nodes (4): AI-Powered Licensing, Labs64 NetLicensing, MCP Integration, NetLicensing MCP Banner Image

### Community 37 - "CI Workflow"
Cohesion: 0.50
Nodes (4): CI Workflow, CI Lint & Format Job, CI Security Audit Job, CI Test Matrix Job (Python 3.12/3.13/3.14)

### Community 38 - "Release Pipeline"
Cohesion: 0.83
Nodes (4): Release: Create GitHub Release Job, Release: Publish Docker Image Job, Release: Publish to MCP Registry Job, Release: Publish to PyPI Job

## Ambiguous Edges - Review These
- `TestAuthenticated/TestUnauthenticated` → `Shared Warning Thresholds (P1.8/P1.9)`  [AMBIGUOUS]
  tests/test_auth_middleware.py · relation: conceptually_related_to

## Knowledge Gaps
- **43 isolated node(s):** `$schema`, `maintainers`, `$schema`, `name`, `title` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `TestAuthenticated/TestUnauthenticated` and `Shared Warning Thresholds (P1.8/P1.9)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `netlicensing_explain_validation()` connect `Explain Validation Tool` to `MCP Create Tool Wrappers`, `Validation Explain Workflow`, `MCP Delete & Preview Tools`, `Test Response Fixtures`, `MCP Server Entry Point`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `nl_post()` connect `Async HTTP Client` to `HTTP Client & Demo Mode`, `Tool Integration Tests`, `Test Response Fixtures`, `License Template Tests`, `Licensee CRUD Tests`, `Product Module Tests`, `Transaction Tools`, `License CRUD Tools`, `Payment Method Tools`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `test_tool_sends_dry_run_true()` connect `Validation Explain Workflow` to `Explain Validation Tool`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `_json()` (e.g. with `.test_injects_demo_mode_when_active()` and `.test_no_demo_mode_tag_when_key_present()`) actually correct?**
  _`_json()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `build_health()` (e.g. with `test_envelope_has_console_url()` and `test_heuristic_critical_expiry()`) actually correct?**
  _`build_health()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `explain_validation()` (e.g. with `validate_acme_node_mismatch.json fixture` and `test_all_valid()`) actually correct?**
  _`explain_validation()` has 13 INFERRED edges - model-reasoned connections that need verification._