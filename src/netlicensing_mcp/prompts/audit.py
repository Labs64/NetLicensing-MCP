"""Prompt templates for license audits."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent


def register_audit_prompts(mcp: FastMCP) -> None:
    """Register all license audit prompt templates on the MCP server."""

    # ── 1. Full account audit ────────────────────────────────────────────────

    @mcp.prompt()
    def audit_full(product_number: str) -> list[PromptMessage]:
        """Run a comprehensive license audit across all customers of a product.

        Args:
            product_number: The NetLicensing product number to audit (e.g. 'P001')
        """
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""
You are a software licensing auditor. Perform a full license audit
for NetLicensing product **{product_number}**.

Follow these steps in order — call each tool and wait for results before continuing.

## Step 1 — Product Overview
Call `netlicensing_get_product` with product_number="{product_number}".
Summarise: product name, description, version, active status.

## Step 2 — Module Inventory
Call `netlicensing_list_product_modules` with product_number="{product_number}".
List each module: number, name, licensing model, active state.

## Step 3 — Customer Roster
Call `netlicensing_list_licensees` with product_number="{product_number}".
Report: total customer count, list each licensee number and name.

## Step 4 — License Validation (per customer)
For EACH licensee found in Step 3, call `netlicensing_validate_licensee`.
For each result extract:
- Licensee number
- Module name(s) and their valid (true/false)
- License type (TIMEVOLUME, FLOATING, FEATURE, QUANTITY)
- Expiry date and time remaining (if present)
- Quantity used / total (if present)
- Warning level: OK / AT_RISK / EXPIRED

## Step 5 — License Inventory (per customer)
For each licensee, call `netlicensing_list_licenses`.
Record: license number, active status, template used, creation date.

## Step 6 — Audit Report

### 🟢 Compliant Customers
Licensees where ALL modules validate as true with no anomalies.

### 🔴 Non-Compliant Customers
| Licensee # | Name | Failing Module | Cause | Recommended Action |
|---|---|---|---|---|

### 🟡 At-Risk Customers
Licensees with licenses expiring within 30 days or quota below 10% remaining.
| Licensee # | Module | Expiry / Remaining | Days Left |
|---|---|---|---|

### 📊 Statistics
| Metric | Value |
|---|---|
| Total customers | |
| Compliant | |
| Non-compliant | |
| At-risk | |
| Total active licenses | |
| Total inactive licenses | |

### 🔧 Prioritised Recommended Actions
Numbered list for the account owner, most urgent first.
""",
                ),
            )
        ]

    # ── 2. Single-customer deep-dive ─────────────────────────────────────────

    @mcp.prompt()
    def audit_customer(licensee_number: str) -> list[PromptMessage]:
        """Deep-dive audit for a single customer's license health.

        Args:
            licensee_number: The licensee number to audit (e.g. 'I001')
        """
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""
You are a software licensing auditor. Perform a detailed audit
for licensee **{licensee_number}**.

## Step 1 — Customer Profile
Call `netlicensing_get_licensee` with licensee_number="{licensee_number}".
Extract: name, associated product, creation date, active status, custom properties.

## Step 2 — Validate All Modules
Call `netlicensing_validate_licensee` with licensee_number="{licensee_number}".
For each module record:
- Module name | Valid | License type | Expiry | Used/Total | Warning level

## Step 3 — License Inventory
Call `netlicensing_list_licenses` with licensee_number="{licensee_number}".
For each license: number, template, active, creation date, custom properties.

## Step 4 — Customer Report

### Overall Status
✅ COMPLIANT / ⚠️ AT-RISK / ❌ NON-COMPLIANT — with one-line justification.

### Module-by-Module Breakdown
| Module | Valid | Type | Expires | Used/Total | Status |
|---|---|---|---|---|---|

### Active Licenses
| License # | Template | Active | Created |
|---|---|---|---|

### Issues Found
Numbered list of any problems discovered.

### Recommended Actions
1. Immediate (non-compliant / expired)
2. Near-term (at-risk / expiring within 30 days)
3. Optional improvements

If any license is expired or invalid, call `netlicensing_create_shop_token`
with licensee_number="{licensee_number}" and include the renewal URL in the report.
""",
                ),
            )
        ]

    # ── 3. Expiry sweep ──────────────────────────────────────────────────────

    @mcp.prompt()
    def audit_expiry(
        product_number: str,
        days_threshold: int = 30,
    ) -> list[PromptMessage]:
        """Find all customers with licenses expiring within N days.

        Args:
            product_number: Product number to sweep
            days_threshold: Flag licenses expiring within this many days (default 30)
        """
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""
You are a software licensing auditor running an expiry sweep.

Target product: **{product_number}**
Flag threshold: licenses expiring within **{days_threshold} days** from today.

## Step 1 — Enumerate Customers
Call `netlicensing_list_licensees` with product_number="{product_number}".

## Step 2 — Validate Each Customer
For each licensee call `netlicensing_validate_licensee`.
Parse every module response for expirationTime, startDate/endDate,
timeVolume fields, or any currently invalid module.

## Step 3 — Expiry Report

### 🔴 Already Expired
| Customer # | Name | Module | Expired On | Days Overdue |
|---|---|---|---|---|

### 🟠 Expiring within {days_threshold} days
| Customer # | Name | Module | Expiry Date | Days Remaining |
|---|---|---|---|---|

### 🟢 Healthy (>{days_threshold} days remaining)
Total count only — do not list individually.

## Step 4 — Renewal URLs
For every expired or at-risk customer, call `netlicensing_create_shop_token`.
Present as:
| Customer # | Name | Expiry | Shop Renewal URL |
|---|---|---|---|

## Step 5 — Summary
- Total customers scanned:
- Already expired:
- Expiring within {days_threshold} days:
- Healthy:
- Renewal URLs generated:
- Next recommended action:
""",
                ),
            )
        ]

    # ── 4. Cleanup audit ─────────────────────────────────────────────────────

    @mcp.prompt()
    def audit_cleanup(product_number: str) -> list[PromptMessage]:
        """Identify inactive, unused, or orphaned licenses for cleanup.

        Args:
            product_number: Product number to inspect
        """
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""
You are a software licensing auditor performing a cleanup audit
for product **{product_number}**.

Goal: identify inactive licenses, zero-quota licensees, and orphaned records.

## Step 1 — Enumerate Customers
Call `netlicensing_list_licensees` with product_number="{product_number}".

## Step 2 — Inspect Each Customer
For each licensee:
a) Call `netlicensing_list_licenses` — flag any where active=false
b) Call `netlicensing_validate_licensee` — flag any where ALL modules are invalid

## Step 3 — Cleanup Report

### 🗑️ Fully Inactive Licensees
Customers with no active licenses at all.
| Licensee # | Name | Inactive License Count |
|---|---|---|

### 💤 Mixed Active/Inactive
| Licensee # | Name | Active | Inactive |
|---|---|---|---|

### 🔢 Zero-Quota / Fully Consumed
Floating or quantity-based licenses with 0 remaining.
| Licensee # | Module | Type | Used | Total |
|---|---|---|---|---|

## Step 4 — Cleanup Recommendations
For each category:
1. Whether to deactivate via `netlicensing_update_license`
2. Whether to delete via `netlicensing_delete_licensee`
3. Whether a renewal / upsell is more appropriate

⚠️ Do NOT call any destructive tool (`netlicensing_delete_*`, `netlicensing_update_license` with active=false)
without explicit confirmation from the user after they review this report.
""",
                ),
            )
        ]

    # ── 5. Anomaly detection ─────────────────────────────────────────────────

    @mcp.prompt()
    def audit_anomaly(product_number: str) -> list[PromptMessage]:
        """Detect anomalous usage patterns across all customers.

        Args:
            product_number: Product number to analyse
        """
        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""
You are a software licensing analyst performing an anomaly detection audit
for product **{product_number}**.

## Step 1 — Full Data Collection
Call `netlicensing_list_licensees` with product_number="{product_number}".
For each licensee call `netlicensing_validate_licensee` and `netlicensing_list_licenses`.

## Step 2 — Anomaly Analysis
Examine the collected data for:

**Usage anomalies**
- Licensees with unusually high quantity consumption vs peers
- Floating license seats maxed out consistently
- Sudden jumps in usage (infer from quota remaining vs total)

**Configuration anomalies**
- Licensees with licenses from templates no longer active
- Duplicate licenses from the same template on one licensee
- Licensees with licenses across more modules than their product tier suggests

**Compliance anomalies**
- Licensees where validation fails but active licenses exist
  (mismatch between license records and validation outcome)
- Licensees with no licenses but marked active

## Step 3 — Anomaly Report

### 🚨 High Severity
Issues that suggest over-use, abuse, or misconfiguration needing immediate action.

### ⚠️ Medium Severity
Unusual patterns that warrant investigation but are not immediately harmful.

### ℹ️ Informational
Patterns worth monitoring going forward.

### 📋 Recommended Actions
Concrete next steps for each finding, prioritised by severity.
""",
                ),
            )
        ]
