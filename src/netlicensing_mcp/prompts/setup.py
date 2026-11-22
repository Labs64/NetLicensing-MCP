"""Prompt templates for NetLicensing setup and troubleshooting workflows.

Each prompt walks the assistant through one task with the registered tools,
named exactly as registered and with their real argument names (see
``tests/test_setup_prompts.py``, which checks both). Licensing-model facts come
from the server instructions, the tool docs and the NetLicensing wiki
(Subscription, Try & Buy, API key roles); nothing else is assumed.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage
from mcp.types import TextContent
from pydantic import Field

from netlicensing_mcp.prompts import clean_doc

_ROLE = """You are a Labs64 NetLicensing assistant for an online license and
entitlements management system."""

_HOW = """Work through the steps in order: call each tool and wait for its result
before you continue. If a tool returns an error, stop, show its `detail` and
`hint` to the user, and ask how to proceed, unless the step says how to
handle that error (several steps expect a not-found). Identifiers are
case-sensitive.
When a list result has `has_more=true`, fetch the next page by passing its
`next_page_hint` as `filter` before you conclude that something does not exist.
Render entity numbers as Markdown links to their `console_url`."""

_SAFETY = """## Safety rules
- Ask for explicit confirmation before every create, update or transfer step,
  unless the user has already approved this exact plan.
- This workflow never deletes anything. If the user asks to remove something,
  call the matching `netlicensing_preview_delete_*` tool first, show what would
  be affected and wait for approval. Never pass force_cascade=true unless the
  user explicitly asks for recursive deletion.
- Prefer deactivating (active=false) over deleting when the intent is to
  disable something.
- If a step fails half-way, report what was already created; do not try to
  undo it on your own.
- Never repeat secrets (API keys, licensee or node secrets, shop URLs) in
  summaries, and never put them into any tool call except the one a step
  names for them."""


def _messages(text: str) -> list[UserMessage]:
    # FastMCP's own message type: the server sends it as a PromptMessage with
    # this text. (An mcp.types.PromptMessage returned here would not be
    # recognised and would reach the client as a JSON dump of the object.)
    return [UserMessage(content=TextContent(type="text", text=text.strip()))]


def register_setup_prompts(mcp: FastMCP) -> None:
    """Register NetLicensing setup and troubleshooting prompts on the MCP server."""

    # ── 1. Subscription product ──────────────────────────────────────────────

    @mcp.prompt(title="Set up a subscription product")
    @clean_doc
    def setup_subscription_product(
        product_name: Annotated[
            str, Field(description="Name of the new product, e.g. 'Acme Cloud'")
        ],
        plans: Annotated[
            str,
            Field(
                description=(
                    "Subscription plans as period and price, e.g. "
                    "'1 MONTH 9.99 EUR; 1 YEAR 99.00 EUR' (periods: DAY, WEEK, MONTH, YEAR)"
                )
            ),
        ],
    ) -> list[UserMessage]:
        """Create a product with a Subscription module and one TIMEVOLUME template per plan.

        Checks that the Subscription model and the TIMEVOLUME type are available,
        plans the product, module and one license template per plan (period and
        price), optionally with a grace period or a free evaluation template,
        and creates them after confirmation.
        """
        return _messages(f"""
{_ROLE} Set up the new subscription product **{product_name}** with these
plans: **{plans}**.

{_HOW}

In NetLicensing a module with the **Subscription** licensing model sells
time-limited access through license templates of type **TIMEVOLUME**: each
plan is one template with a time volume (`time_volume` units of
`time_volume_period`: DAY, WEEK, MONTH or YEAR) and a price. Purchased time
adds up: a renewal bought before expiry extends the current end date.

## Step 1 — Check the connection
Call `netlicensing_server_info()`. If `status` is "error", show `next_steps`
to the user and stop.

## Step 2 — Confirm the licensing model
Call `netlicensing_list_licensing_models()` and check that **Subscription** is
listed, then `netlicensing_list_license_types()` and check that **TIMEVOLUME**
is listed. If either is missing, tell the user and stop.

## Step 3 — Plan the entities
Turn the plans into a table:
| Plan name | time_volume | time_volume_period | price | currency |
|---|---|---|---|---|
Use an ISO 4217 currency code (EUR when none is given). If a plan has no
period, no price or a period other than DAY, WEEK, MONTH or YEAR, ask the user
instead of guessing.
Propose a product number, a module number and one license template number
per plan. Call `netlicensing_get_product(product_number="<proposed product number>")`:
a not-found error means the number is free; if a product is returned, propose
another number.
Ask two optional questions (default: no):
- Grace period after expiry? (grace_period=true on the plan templates)
- Free evaluation period for new customers? (an extra TIMEVOLUME template
  with price=0 and automatic=true; NetLicensing assigns it to every new
  licensee and the period starts with the first validation)

## Step 4 — Confirm
Show the full plan (product, module, every template with all values) and wait
for the user's explicit confirmation. Do not create anything before that.

## Step 5 — Create
1. `netlicensing_create_product(number="<product number>", name="{product_name}")`
2. `netlicensing_create_product_module(product_number="<product number>", number="<module number>", name="<module name>", licensing_model="Subscription")`
3. For each plan:
   `netlicensing_create_license_template(module_number="<module number>", number="<template number>", name="<plan name>", license_type="TIMEVOLUME", time_volume=<n>, time_volume_period="<DAY|WEEK|MONTH|YEAR>", price=<price>, currency="<currency>")`
   Add grace_period=true only if the user asked for a grace period.
4. Only if the user asked for an evaluation period:
   `netlicensing_create_license_template(module_number="<module number>", number="<template number>", name="<e.g. 14-day evaluation>", license_type="TIMEVOLUME", time_volume=<days>, time_volume_period="DAY", price=0, automatic=true)`

## Step 6 — Verify
Call `netlicensing_list_license_templates(module_number="<module number>")`
and check that every plan is there, active, with the right period and price.

## Step 7 — Report
| Entity | Number | Name | Details |
|---|---|---|---|
One row for the product, the module and each template. Then suggest the next
steps: add customers with the `onboard_customer` prompt, and let a customer
buy or renew a plan through a checkout link from
`netlicensing_create_shop_token(licensee_number="<licensee number>")`.

{_SAFETY}
""")

    # ── 2. Try & Buy trial ───────────────────────────────────────────────────

    @mcp.prompt(title="Add a free trial to a product")
    @clean_doc
    def setup_trial(
        product_number: Annotated[str, Field(description="Existing product to add the trial to")],
        trial_days: Annotated[
            int, Field(ge=1, description="Length of the free trial in days (default 14)")
        ] = 14,
    ) -> list[UserMessage]:
        """Add a Try & Buy module to a product: a free, automatic TIMEVOLUME trial
        template and a FEATURE full-version template.

        The trial template is hidden in the Shop; the full version carries the
        purchase price. An existing automatic trial is reused instead of
        creating a second one, and licenseeAutoCreate can be turned on after a
        preview.
        """
        return _messages(f"""
{_ROLE} Add a free **{trial_days}-day trial** to product **{product_number}**
using the Try & Buy licensing model.

{_HOW}

In NetLicensing a module with the **TryAndBuy** licensing model uses two
license templates:
- a **TIMEVOLUME** template for the trial: price 0, automatic=true (every new
  licensee gets it, and the trial starts with the first use), hidden=true (it
  cannot be bought in the Shop) and `time_volume` = trial length in days;
- a **FEATURE** template for the full version: the purchase price,
  automatic=false, hidden=false.
Validation then reports `valid=true` while the trial runs and after a
purchase; `evaluation=true` while the product is in trial, with the trial's
end in `evaluationExpires`.

## Step 1 — Check the product
Call `netlicensing_get_product(product_number="{product_number}")`. If it is not
found, stop and suggest creating it first (`netlicensing_create_product` or
the `setup_subscription_product` prompt). Note whether it is active and its
`licenseeAutoCreate` setting.

## Step 2 — Confirm the licensing model
Call `netlicensing_list_licensing_models()` and check that **TryAndBuy** is
listed. If not, tell the user and stop.

## Step 3 — Look for an existing trial
Call `netlicensing_list_product_modules(product_number="{product_number}")`. For
each module with the TryAndBuy licensing model call
`netlicensing_list_license_templates(module_number="<module number>")`.
If a TIMEVOLUME template with automatic=true already exists, show it and ask
whether to change its length with
`netlicensing_update_license_template(template_number="<template number>", time_volume={trial_days})`
instead of creating a second trial. Never create a duplicate trial.

## Step 4 — Plan and confirm
Ask the user for anything you do not know: module number and name, and the
full version's template number, name, price and currency. Propose a template
number for the trial. Show the full plan and wait for explicit confirmation.

## Step 5 — Create
1. `netlicensing_create_product_module(product_number="{product_number}", number="<module number>", name="<module name>", licensing_model="TryAndBuy")`
2. Trial template:
   `netlicensing_create_license_template(module_number="<module number>", number="<trial template number>", name="{trial_days}-day trial", license_type="TIMEVOLUME", time_volume={trial_days}, time_volume_period="DAY", price=0, currency="EUR", automatic=true, hidden=true)`
3. Full version template:
   `netlicensing_create_license_template(module_number="<module number>", number="<full template number>", name="<full version name>", license_type="FEATURE", price=<price>, currency="<currency>", automatic=false, hidden=false)`

## Step 6 — Licensee auto-create
With licenseeAutoCreate=true the first validation of an unknown licensee
creates it (and so starts its trial); with false, every licensee must be
created first (`netlicensing_create_licensee` or the `onboard_customer`
prompt). If it is false, explain this and ask whether to enable it. Only if
the user agrees:
1. `netlicensing_preview_update_product(product_number="{product_number}", licensee_auto_create=true)`
   and show the returned diff;
2. after confirmation,
   `netlicensing_update_product(product_number="{product_number}", licensee_auto_create=true, confirm_token="<token from the preview>")`.

## Step 7 — Verify and report
Call `netlicensing_list_license_templates(module_number="<module number>")` and
check both templates. Report the module, both templates (type, price,
automatic, hidden, time volume) and the licenseeAutoCreate setting. Suggest
selling the full version with
`netlicensing_create_shop_token(licensee_number="<licensee number>")`.

{_SAFETY}
""")

    # ── 3. Customer onboarding ───────────────────────────────────────────────

    @mcp.prompt(title="Onboard a customer")
    @clean_doc
    def onboard_customer(
        customer_name: Annotated[str, Field(description="Customer (licensee) display name")],
        product_number: Annotated[str, Field(description="Product the customer licenses")],
        licensee_number: Annotated[
            str,
            Field(description="Licensee number to use (empty: auto-generated by NetLicensing)"),
        ] = "",
        module_number: Annotated[
            str, Field(description="Product module to pick the license template from (optional)")
        ] = "",
        license_template_number: Annotated[
            str, Field(description="License template to assign (optional; asked when empty)")
        ] = "",
    ) -> list[UserMessage]:
        """Create a licensee, assign a license from a template (or a bundle) and
        validate it with a dry run.

        Reuses a matching existing licensee if the user agrees, assigns the
        license after confirmation, explains a failed validation, and can create
        a one-time Shop checkout URL.
        """
        if licensee_number:
            existing = f"""Call `netlicensing_get_licensee(licensee_number="{licensee_number}")`.
- Not found: create it in Step 5 with this number.
- Found under product {product_number}: show it and ask whether to reuse it
  (skip Step 5).
- Found under another product: stop and ask the user."""
            create_call = (
                f'`netlicensing_create_licensee(product_number="{product_number}", '
                f'number="{licensee_number}", name="{customer_name}")`'
            )
        else:
            existing = f"""Call `netlicensing_list_licensees(product_number="{product_number}")` and look
for a licensee named like "{customer_name}". If there is one, show it and ask
whether to reuse it (skip Step 5) or create a new one."""
            create_call = (
                f'`netlicensing_create_licensee(product_number="{product_number}", '
                f'name="{customer_name}")`\n(no number: NetLicensing generates it)'
            )

        if license_template_number:
            choose = f"""Call `netlicensing_get_license_template(template_number="{license_template_number}")`.
Check that it is active, then call
`netlicensing_get_product_module(module_number="<module number of the template>")`
and check that the module belongs to product {product_number}."""
        elif module_number:
            choose = (
                f"""Call `netlicensing_list_license_templates(module_number="{module_number}")`."""
            )
        else:
            choose = f"""Call `netlicensing_list_product_modules(product_number="{product_number}")`, then
`netlicensing_list_license_templates(module_number="<module number>")` for each
active module."""

        return _messages(f"""
{_ROLE} Onboard the customer **{customer_name}** for product
**{product_number}**: create the licensee, assign a license and check that it
validates.

{_HOW}

## Step 1 — Check the product
Call `netlicensing_get_product(product_number="{product_number}")`. Stop if it is
not found; if it is inactive, ask before continuing. Note
`licenseeSecretMode`: when it is PREDEFINED the licensee needs a secret. Ask
the user for it, pass it only as licensee_secret in Step 5 and never repeat it.

## Step 2 — Existing customer?
{existing}

## Step 3 — Choose the entitlement
{choose}
Show the active templates (number, name, license type, price, currency, time
volume, automatic) and let the user pick one, unless the template is already
given. Templates with automatic=true are assigned to every new licensee by
NetLicensing: do not create a second license from them. To provision several
templates at once, a bundle can be used instead: `netlicensing_list_bundles()`
and, in Step 7, `netlicensing_obtain_bundle(bundle_number="<bundle number>", licensee_number="<licensee number>")`.

## Step 4 — Confirm
Show the plan (licensee number and name, template, license values) and wait
for explicit confirmation.

## Step 5 — Create the licensee
{create_call}
Add licensee_secret only when licenseeSecretMode is PREDEFINED.

## Step 6 — Check licenses assigned automatically
Call `netlicensing_list_licenses(licensee_number="<licensee number>")`. If a
license from the chosen template already exists (for example one assigned
automatically), skip Step 7.

## Step 7 — Assign the license
`netlicensing_create_license(licensee_number="<licensee number>", license_template_number="<template number>")`
Some values are mandatory depending on the template's type and module's model
(take them from the template unless the user says otherwise; ask when unknown):
- TIMEVOLUME: start_date (ISO 8601, e.g. now) and time_volume; the optional
  time_volume_period (DAY, WEEK, MONTH or YEAR) sets the unit;
- PayPerUse or NodeLocked model: quantity;
- TIMEVOLUME in a Rental module: parent_feature.

## Step 8 — Validate
Call `netlicensing_validate_licensee(licensee_number="<licensee number>", product_number="{product_number}", dry_run=true)`
(a dry run changes nothing). If a module is not valid, call
`netlicensing_explain_validation(licensee_number="<licensee number>", product_number="{product_number}")`
and include its explanation.

## Step 9 — Optional checkout link
Only if the user wants the customer to buy or renew on their own:
`netlicensing_create_shop_token(licensee_number="<licensee number>")`. The
checkout URL is shown once: hand it to the user and do not repeat it later.

## Step 10 — Report
| Licensee # | Name | License # | Template | Type | Valid | Expires |
|---|---|---|---|---|---|---|

{_SAFETY}
""")

    # ── 4. Customer migration (license transfer) ─────────────────────────────

    @mcp.prompt(title="Move a customer's licenses to another licensee")
    @clean_doc
    def migrate_customer(
        from_licensee_number: Annotated[str, Field(description="Source licensee")],
        to_licensee_number: Annotated[str, Field(description="Destination licensee")],
    ) -> list[UserMessage]:
        """Preview both licensees and their licenses, then move all licenses from one
        licensee to another with `netlicensing_transfer_licenses`.

        After confirmation it prepares the licensees where needed
        (markedForTransfer on the source, active state) before the transfer.
        The source licensee is consumed by the transfer.
        """
        src = from_licensee_number
        dst = to_licensee_number
        return _messages(f"""
{_ROLE} Move all licenses of licensee **{src}** to licensee **{dst}**.

{_HOW}

`netlicensing_transfer_licenses` moves **all** licenses at once. NetLicensing
requires that the source licensee is marked for transfer
(markedForTransfer=true) and that both licensees are active, and the source
licensee is consumed by the transfer. There is no undo, so preview first.

## Step 1 — Preview: both licensees
Call `netlicensing_get_licensee(licensee_number="{src}")` and
`netlicensing_get_licensee(licensee_number="{dst}")`.
Record for each: name, product, active, markedForTransfer.
- If {dst} does not exist, ask whether to create it with
  `netlicensing_create_licensee(product_number="<product of {src}>", number="{dst}", name="<name>")`
  (after confirmation) or stop.
- If they belong to different products, point this out and ask the user
  before going on.

## Step 2 — Preview: licenses
Call `netlicensing_list_licenses(licensee_number="{src}")` and
`netlicensing_list_licenses(licensee_number="{dst}")`.
Optionally record the current state with
`netlicensing_validate_licensee(licensee_number="{src}", dry_run=true)` and
`netlicensing_validate_licensee(licensee_number="{dst}", dry_run=true)`.

## Step 3 — Show the preview and ask
| License # | Template | Type | Active | Moves from {src} to {dst} |
|---|---|---|---|---|
List what must change first (markedForTransfer on {src}, an inactive
licensee) and say that {src} is consumed by the transfer.
Ask for explicit confirmation. Do not change anything before the user confirms.

## Step 4 — Prepare
Only the changes the preview showed are needed:
- `netlicensing_update_licensee(licensee_number="{src}", marked_for_transfer=true)`
- for an inactive licensee:
  `netlicensing_update_licensee(licensee_number="<licensee number>", active=true)`

## Step 5 — Transfer
`netlicensing_transfer_licenses(from_licensee_number="{src}", to_licensee_number="{dst}")`

## Step 6 — Verify
Call `netlicensing_list_licenses(licensee_number="{dst}")` and
`netlicensing_validate_licensee(licensee_number="{dst}", dry_run=true)`, then
`netlicensing_get_licensee(licensee_number="{src}")` to report the source's
state (it may no longer exist or have no licenses).

## Step 7 — Report
Licenses moved, the destination's validation per module, and the source's
state. Do not delete the source licensee; if the user wants it removed,
follow the safety rules below (preview first, prefer deactivation with
`netlicensing_update_licensee(licensee_number="{src}", active=false)`).

{_SAFETY}
""")

    # ── 5. Validation troubleshooting ────────────────────────────────────────

    @mcp.prompt(title="Troubleshoot a failing validation")
    @clean_doc
    def troubleshoot_validation(
        licensee_number: Annotated[str, Field(description="Licensee whose validation fails")],
        product_number: Annotated[
            str, Field(description="Product to scope the validation to (optional)")
        ] = "",
        product_module_number: Annotated[
            str, Field(description="Product module that fails (optional)")
        ] = "",
    ) -> list[UserMessage]:
        """Find out why a licensee's validation fails and how to fix it, without side
        effects: setup check, dry-run validation, plain-language explanation,
        customer health.

        Ends with a diagnosis per module and the tool calls that fix it, which
        are run only after the user confirms.
        """
        lic = licensee_number
        focus = f" Product: **{product_number}**." if product_number else ""
        if product_module_number:
            focus += f" Module: **{product_module_number}**."
        scope = f', product_number="{product_number}"' if product_number else ""
        if product_module_number:
            module_params = (
                f', module_parameters=[{{"product_module_number": "{product_module_number}"}}]'
            )
            module_step = f"""Call `netlicensing_get_product_module(module_number="{product_module_number}")`:
note its licensing model and whether it is active. Focus the diagnosis on
this module."""
        else:
            module_params = ""
            module_step = """For each module that is not valid, call
`netlicensing_get_product_module(module_number="<module number>")` and note its
licensing model and whether it is active."""

        return _messages(f"""
{_ROLE} Find out why the license validation of licensee **{lic}** fails
and how to fix it.{focus}

{_HOW}

Every step up to the report is read-only: use dry_run=true for every
validation so nothing is checked out, checked in, bound or consumed.

## Step 1 — Check the setup
Call `netlicensing_server_info()`. If `status` is "error", the problem is the
MCP setup or the API key, not the license: show `next_steps` and stop. A
warning about the key's role means some reads may be refused (403).

## Step 2 — Check the licensee
Call `netlicensing_get_licensee(licensee_number="{lic}")`.
- Not found: check the number (case-sensitive) and the product's
  licenseeAutoCreate with `netlicensing_get_product(product_number="<product number>")`.
- Inactive: that alone makes validation fail.

## Step 3 — Explain the validation
Call `netlicensing_explain_validation(licensee_number="{lic}"{scope}{module_params})`.
It returns per-module status, plain-language explanations and
`suggested_actions`. Floating and NodeLocked modules need a session_id or a
node_secret: ask the user only if the result says one is missing, pass it in
module_parameters and never repeat a node secret.

## Step 4 — Raw validation result
Call `netlicensing_validate_licensee(licensee_number="{lic}"{scope}, dry_run=true)`
and read each module's `valid`, expiry, quota and the `warnings` (API infos
such as "No free floating licenses found.").

## Step 5 — Licenses and health
Call `netlicensing_get_customer_health(licensee_number="{lic}", refresh_warning_level=false)`
for the license list (active / inactive, templates) and warnings (Step 4
already validated, so no second validation is needed).
{module_step}

## Step 6 — Diagnosis
| Module | Licensing model | Valid | Cause | Fix |
|---|---|---|---|---|
Typical causes: inactive licensee, license, module or product; no license for
the module; subscription or trial expired; quota used up; all floating
sessions in use; node secret does not match; the API key's role does not
allow the call.

## Step 7 — Recommended fixes
Give each fix with the exact tool call, for example:
- re-activate a license: `netlicensing_update_license(license_number="<license number>", active=true)`
- re-activate the licensee: `netlicensing_update_licensee(licensee_number="{lic}", active=true)`
- renewal or top-up checkout: `netlicensing_create_shop_token(licensee_number="{lic}")`
- a missing license: `netlicensing_create_license(licensee_number="{lic}", license_template_number="<template number>")`
Do not run any of them without the user's explicit confirmation. After a fix,
validate again with dry_run=true.

{_SAFETY}
""")

    # ── 6. API key issuance ──────────────────────────────────────────────────

    @mcp.prompt(title="Issue a scoped API key")
    @clean_doc
    def issue_api_key(
        purpose: Annotated[
            str,
            Field(
                description=(
                    "What the key is for, e.g. 'license validation in our desktop app' "
                    "or 'nightly reporting'"
                )
            ),
        ],
    ) -> list[UserMessage]:
        """Pick the least-privilege API key role for a purpose and create the key,
        which is shown once.

        The key can be scoped to one licensee. It is created after confirmation
        and never repeated afterwards; the prompt also explains how to revoke it.
        """
        return _messages(f"""
{_ROLE} Issue a new NetLicensing API key for this purpose: **{purpose}**.

{_HOW}

NetLicensing API key roles, each including the rights of the ones above it:
| Role | Allows |
|---|---|
| ROLE_APIKEY_LICENSEE | validate and transfer licenses, create shop tokens (for keys embedded in client software) |
| ROLE_APIKEY_ANALYTICS | also read (get / list) all entities (reporting) |
| ROLE_APIKEY_OPERATION | also create, update and delete licensees and licenses |
| ROLE_APIKEY_MAINTENANCE | also create, update and delete products, product modules and license templates |
| ROLE_APIKEY_ADMIN | full access, like the account login; use only when the user insists |

## Step 1 — Check the setup
Call `netlicensing_server_info()`. If `status` is "error", show `next_steps`
and stop.

## Step 2 — Pick the least privilege
Choose the lowest role that serves the purpose and explain why. If the key
is for one customer, ask for the licensee number to scope it to, and check it
with `netlicensing_get_licensee(licensee_number="<licensee number>")`.
To see which keys exist already, call
`netlicensing_list_tokens(filter="tokenType=APIKEY")` (their numbers are masked).

## Step 3 — Confirm
Confirm the role and the licensee scope (if any) with the user. Ask again,
explicitly, before creating a ROLE_APIKEY_ADMIN key.

## Step 4 — Create
`netlicensing_create_api_token(api_key_role="<role>", licensee_number="<licensee number, or leave empty>")`
The result has shown_once=true: its token `number` is the API key, shown
ONCE and never again in full (later reads mask it).

## Step 5 — Hand over the key
Show the key to the user exactly once, in a code block, with the role and the
scope, and tell them to store it in a secret manager now. Do not repeat the
key afterwards: not in summaries, not in later answers, not in any other tool
call, file or log. When you refer to it later, use the role and the masked
form only.

## Step 6 — Revoking
If the key leaks or is no longer needed: revoking needs the FULL key, because
for an API key the token number is the key itself and NetLicensing lists it
only masked. Ask the user to paste the full key or to copy it from the
NetLicensing console; do not reuse the copy shown earlier in this
conversation. Pass the full key only as token_number to
`netlicensing_preview_delete_token` and `netlicensing_delete_token`, never
echo it, and never put it into any other tool call. Their results show the
key only masked (the preview's `target`, the delete message); refer to it by
that masked form and the role, and report only that the key was revoked.
1. `netlicensing_preview_delete_token(token_number="<full API key from the user>")`
   and show the role and type it would revoke;
2. after confirmation,
   `netlicensing_delete_token(token_number="<full API key from the user>", confirm_token="<token from the preview>")`.

{_SAFETY}
""")
