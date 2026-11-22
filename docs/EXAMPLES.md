# Examples: what vendors ask, and which tools run

Six everyday scenarios for a software vendor using NetLicensing, each with a prompt you can type and the tool calls an assistant typically makes to answer it.

> **Illustrative, not recorded.** These are sketches of a typical session, not captured output. The exact calls depend on your client, the model and your data: an assistant may call fewer tools, more tools or the same tools in a different order. Tool names and argument names are the real ones (see [TOOLS.md](TOOLS.md)); the numbers (`P001`, `I001`, `M01`, ...) are placeholders. Try these against the NetLicensing sandbox with [demo mode](../README.md#demo--sandbox-mode-no-api-key) or a test account before you use them on live data.

Writes (create, update, transfer) are shown as they run *after* you confirm them: the server instructions tell the assistant to ask first. Deletes always go through a preview and a confirmation token.

## 1. Try it without an account

> "Is the NetLicensing connection working? Then show me what's in the account and which licensing models I can use."

Start the server with `NETLICENSING_ALLOW_DEMO=true` (no API key needed):

```text
netlicensing_server_info()
netlicensing_list_products()
netlicensing_list_licensing_models()
```

`netlicensing_server_info` reports `status` (`ok`, `warning` or `error`), where the credentials come from (`auth.source`: `demo` here) and `next_steps` if something needs fixing. In demo mode every result carries `"demo_mode": true` and the status is `warning`, so you can't mistake the sandbox for your real account.

## 2. Launch a subscription product and sign up the first customer

> "Create a product 'Acme Cloud' (P001) with a Subscription module and two plans, monthly for 9.99 EUR and yearly for 99 EUR. Then add Acme Corp as a customer on the yearly plan, starting today."

You can also pick the `setup_subscription_product` prompt (`product_name="Acme Cloud"`, `plans="1 MONTH 9.99 EUR; 1 YEAR 99.00 EUR"`) and then `onboard_customer`; they walk through the same steps.

```text
netlicensing_list_licensing_models()
netlicensing_list_license_types()
netlicensing_create_product(number="P001", name="Acme Cloud")
netlicensing_create_product_module(product_number="P001", number="M01", name="Acme Cloud Subscription", licensing_model="Subscription")
netlicensing_create_license_template(module_number="M01", number="LT-MONTH", name="Monthly", license_type="TIMEVOLUME", time_volume=1, time_volume_period="MONTH", price=9.99, currency="EUR")
netlicensing_create_license_template(module_number="M01", number="LT-YEAR", name="Yearly", license_type="TIMEVOLUME", time_volume=1, time_volume_period="YEAR", price=99.0, currency="EUR")
netlicensing_create_licensee(product_number="P001", number="I001", name="Acme Corp")
netlicensing_create_license(licensee_number="I001", license_template_number="LT-YEAR", start_date="2026-01-15T00:00:00Z", time_volume="1", time_volume_period="YEAR")
netlicensing_validate_licensee(licensee_number="I001", product_number="P001", dry_run=true)
```

The first two calls check that the account offers the Subscription model and the TIMEVOLUME license type. A TIMEVOLUME license needs `start_date` and `time_volume`. The last call is a dry run: it shows whether Acme Corp's license validates without checking anything out or consuming anything.

## 3. Support ticket: "the app says my license is invalid"

> "Customer I001 says the app rejects their license. Find out why and tell me how to fix it."

The `troubleshoot_validation` prompt (`licensee_number="I001"`) runs the same checks.

```text
netlicensing_explain_validation(licensee_number="I001")
netlicensing_get_customer_health(licensee_number="I001", refresh_warning_level=true)
netlicensing_list_licenses(licensee_number="I001")
```

`netlicensing_explain_validation` does a dry-run validation and returns an `overall_status`, a one-line `summary` and, per module, a plain-language `explanation` and `suggested_actions`. `netlicensing_get_customer_health` adds license counts and warnings for the customer as a whole. If the cause is, say, a deactivated license, the fix after you confirm is:

```text
netlicensing_update_license(license_number="L001", active=true)
```

## 4. Renewal sweep with self-service checkout links

> "Which customers of product P001 have expired or will expire in the next 30 days? Give each of them a renewal link."

The `audit_expiry` prompt (`product_number="P001"`, `days_threshold="30"`) does this end to end.

```text
netlicensing_list_licensees(product_number="P001")
netlicensing_validate_licensee(licensee_number="I001", product_number="P001", dry_run=true)
netlicensing_validate_licensee(licensee_number="I002", product_number="P001", dry_run=true)
...
netlicensing_create_shop_token(licensee_number="I002", success_url="https://example.com/thanks", success_url_title="Back to Acme")
```

The list result carries paging data; when `has_more` is `true`, the assistant fetches the next page with the `next_page_hint` filter. `netlicensing_create_shop_token` returns a one-time NetLicensing Shop checkout URL, marked `"shown_once": true`: copy it to the customer right away, because later reads of the token show it masked.

## 5. A customer moves to a new account

> "Acme Corp is moving everything from licensee I001 to their new licensee I002. Move all licenses."

The `migrate_customer` prompt (`from_licensee_number="I001"`, `to_licensee_number="I002"`) walks through it.

```text
netlicensing_get_licensee(licensee_number="I001")
netlicensing_get_licensee(licensee_number="I002")
netlicensing_list_licenses(licensee_number="I001")
netlicensing_update_licensee(licensee_number="I001", marked_for_transfer=true)
netlicensing_transfer_licenses(from_licensee_number="I001", to_licensee_number="I002")
netlicensing_list_licenses(licensee_number="I002")
```

NetLicensing only transfers from a licensee that is marked for transfer, both licensees must be active, and the transfer moves **all** licenses at once with no undo. That is why the assistant reads both licensees first and confirms before the last two writes.

## 6. Offboard a customer safely

> "Customer I003 cancelled. Turn off their access. If nothing else depends on them, delete the licensee."

```text
netlicensing_list_licenses(licensee_number="I003")
netlicensing_update_license(license_number="L007", active=false)
netlicensing_preview_delete_licensee(licensee_number="I003")
netlicensing_delete_licensee(licensee_number="I003", confirm_token="<token from the preview>")
```

Deactivating keeps the history and can be undone, so the assistant prefers it. A delete needs a preview first: `netlicensing_preview_delete_licensee` lists what would be removed and returns a single-use `confirmation_token` that expires after 5 minutes. Nothing is deleted until that token comes back in `confirm_token`. `force_cascade=true` (which also deletes dependent licenses) is only used when you ask for it.

---

More: all tools and their parameters in [TOOLS.md](TOOLS.md); the prompt templates in the [README](../README.md#prompt-templates).
