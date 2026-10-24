# Tool Interface (for agent / UI)

Every tool returns: `{"status": str, "data": dict, "reason": str}`

**Statuses:** `ok`, `insufficient_data`, `blocked`, `service_first`, `duplicate`, `error`.
The agent must route on `status`, never on the text in `reason`.

| Tool | Inputs | Key data returned |
|---|---|---|
| `calculate_purchase_decline(customer_id, analysis_month=None, comparison_month=None)` | customer ID, optional months | `purchase_decline_pct`, `last_year_decline_pct`, `seasonal` |
| `calculate_engagement_score(customer_id, ...)` | same | `comparison_score`, `analysis_score`, `engagement_decline_pct` |
| `assign_retention_risk(customer_id, ...)` | same | `risk_level` (Low/Medium/High), `rule_trace` (list of strings) |
| `get_eligible_offers(customer_id, risk_level, budget_spent=0)` | ID, risk level | `eligible_offers` (cheapest first), `rejected` (with reasons), `budget_left` |
| `save_retention_plan(plan)` | dict with `customer_id`, `period`, `risk_level`, `action` (optional: `offer_id`, `cost`, `rationale`) | `plan_id`, `status="pending_review"`, `created_at` |

## Status meanings
- `insufficient_data`: new customer or missing months. Do NOT assign risk.
- `service_first`: open complaint. Recommend fixing service, no offer.
- `blocked`: customer opted out of contact. No outreach.
- `duplicate`: plan already saved for this customer and period (returns the existing ID).
- `error`: bad input or missing file. Show `reason`, don't guess.

## Rules enforced in code (do not re-implement in prompts)
- Thresholds live in `config/risk_rules.yaml` (High: purchase >= 50% AND engagement >= 40%; Medium: purchase >= 25% OR engagement >= 40%).
- Seasonal declines are rated Low.
- Plans are ALWAYS saved as `pending_review`. No tool sends offers or contacts customers.
- Every tool call is logged to `data/tool_calls.jsonl`.

## Sample customers
C-301 normal High | C-302 new customer | C-303 seasonal | C-304 open complaint |
C-305 no matching offers | C-306 opted out | C-307 Medium | C-308 boundary (High)