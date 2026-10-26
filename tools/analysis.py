import sqlite3
import uuid
from datetime import datetime, timezone

import pandas as pd
import yaml

from tools.logger import logged


def load_rules(path="config/risk_rules.yaml"):
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def _same_month_last_year(month):
    year, mm = month.split("-")
    return f"{int(year) - 1}-{mm}"


def _clean(df, key_cols, value_cols):
    """Drop exact duplicate rows and rows with blank values.

    Returns (clean_df, problem). problem is a message when the same key
    appears twice with different values (conflicting duplicates).
    """
    df = df.drop_duplicates()
    if df.duplicated(subset=key_cols).any():
        return df, "Conflicting duplicate records found"
    return df.dropna(subset=value_cols), None


def _result(status, data=None, reason=""):
    # Every tool returns the same structure.
    return {
        "status": status,
        "data": data or {},
        "reason": reason,
    }


@logged
def calculate_purchase_decline(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml",
):
    rules = load_rules(rules_path)

    analysis_month = (
        analysis_month or rules["comparison"]["analysis_month"]
    )
    comparison_month = (
        comparison_month or rules["comparison"]["comparison_month"]
    )

    if not customer_id or not isinstance(customer_id, str):
        return _result(
            "error",
            reason="customer_id must be a non-empty string",
        )

    try:
        df = pd.read_csv(f"{data_dir}/purchases.csv")
    except FileNotFoundError:
        return _result("error", reason="purchases.csv not found")

    df = df[df["customer_id"] == customer_id]

    if df.empty:
        return _result(
            "error",
            reason=f"No purchase records for {customer_id}",
        )

    # Edge cases: exact duplicate rows are dropped, blank amounts ignored.
    df, problem = _clean(df, ["month"], ["amount"])
    if problem:
        return _result("error", reason=problem)

    months_of_history = df["month"].nunique()

    if months_of_history < rules["minimum_history_months"]:
        return _result(
            "insufficient_data",
            reason=(
                f"Only {months_of_history} month(s) of history; "
                f"need {rules['minimum_history_months']}. "
                "Risk not assigned."
            ),
        )

    amounts = df.set_index("month")["amount"]

    def decline_pct(old_month, new_month):
        if old_month not in amounts.index or new_month not in amounts.index:
            return None

        old = amounts[old_month]
        new = amounts[new_month]

        if old == 0:
            return None

        return float(round((old - new) / old * 100, 2))

    current = decline_pct(comparison_month, analysis_month)

    if current is None:
        return _result(
            "insufficient_data",
            reason=(
                f"Missing data for {comparison_month} "
                f"or {analysis_month}"
            ),
        )

    last_year = decline_pct(
        _same_month_last_year(comparison_month),
        _same_month_last_year(analysis_month),
    )

    tolerance = rules["seasonality"]["tolerance_pct"]

    seasonal = bool(
        current > 0
        and last_year is not None
        and last_year > 0
        and abs(current - last_year) <= tolerance
    )

    return _result(
        "ok",
        {
            "customer_id": customer_id,
            "analysis_month": analysis_month,
            "comparison_month": comparison_month,
            "purchase_decline_pct": current,
            "last_year_decline_pct": last_year,
            "seasonal": seasonal,
        },
        reason=(
            "Seasonal pattern: similar drop last year"
            if seasonal else ""
        ),
    )


@logged
def calculate_engagement_score(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml",
):
    rules = load_rules(rules_path)

    analysis_month = (
        analysis_month or rules["comparison"]["analysis_month"]
    )
    comparison_month = (
        comparison_month or rules["comparison"]["comparison_month"]
    )

    weights = rules["engagement_weights"]

    if not customer_id or not isinstance(customer_id, str):
        return _result(
            "error",
            reason="customer_id must be a non-empty string",
        )

    try:
        df = pd.read_csv(f"{data_dir}/engagement.csv")
    except FileNotFoundError:
        return _result("error", reason="engagement.csv not found")

    df = df[df["customer_id"] == customer_id]

    if df.empty:
        return _result(
            "error",
            reason=f"No engagement records for {customer_id}",
        )

    # Edge cases: exact duplicates dropped, blank logins/emails ignored.
    df, problem = _clean(df, ["month"], ["logins", "emails_opened"])
    if problem:
        return _result("error", reason=problem)

    df = df.assign(
        score=(
            df["logins"] * weights["logins"]
            + df["emails_opened"] * weights["emails_opened"]
        )
    )

    scores = df.set_index("month")["score"]

    if (
        comparison_month not in scores.index
        or analysis_month not in scores.index
    ):
        return _result(
            "insufficient_data",
            reason=(
                f"Missing engagement data for {comparison_month} "
                f"or {analysis_month}"
            ),
        )

    old = float(scores[comparison_month])
    new = float(scores[analysis_month])

    if old == 0:
        return _result(
            "insufficient_data",
            reason="Comparison month score is 0",
        )

    engagement_decline = float(
        round((old - new) / old * 100, 2)
    )

    return _result(
        "ok",
        {
            "customer_id": customer_id,
            "comparison_score": old,
            "analysis_score": new,
            "engagement_decline_pct": engagement_decline,
        },
    )


@logged
def assign_retention_risk(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml",
):
    rules = load_rules(rules_path)

    kwargs = {
        "analysis_month": analysis_month,
        "comparison_month": comparison_month,
        "data_dir": data_dir,
        "rules_path": rules_path,
    }

    trace = []

    purchase = calculate_purchase_decline(customer_id, **kwargs)

    trace.append(
        f"calculate_purchase_decline -> {purchase['status']}"
    )

    if purchase["status"] != "ok":
        return _result(
            purchase["status"],
            reason=purchase["reason"],
        )

    engagement = calculate_engagement_score(customer_id, **kwargs)

    trace.append(
        f"calculate_engagement_score -> {engagement['status']}"
    )

    if engagement["status"] != "ok":
        return _result(
            engagement["status"],
            reason=engagement["reason"],
        )

    p = purchase["data"]["purchase_decline_pct"]
    e = engagement["data"]["engagement_decline_pct"]
    seasonal = purchase["data"]["seasonal"]

    trace.append(
        f"purchase decline {p}%, engagement decline {e}%"
    )

    # Seasonal declines are monitored rather than treated as churn risk.
    if seasonal:
        trace.append(
            "seasonal pattern detected -> risk set to Low (monitor)"
        )

        return _result(
            "ok",
            {
                "customer_id": customer_id,
                "risk_level": "Low",
                "purchase_decline_pct": p,
                "engagement_decline_pct": e,
                "seasonal": True,
                "rule_trace": trace,
            },
            reason="Decline matches last year's seasonal pattern",
        )

    # Apply YAML rules in order; the first matching rule wins.
    level = None

    for rule in rules["risk_levels"]:
        if rule["match"] == "default":
            trace.append(
                f"no higher rule matched -> {rule['level']}"
            )
            level = rule["level"]
            break

        p_ok = p >= rule["purchase_decline_pct_min"]
        e_ok = e >= rule["engagement_decline_pct_min"]

        if rule["match"] == "all":
            hit = p_ok and e_ok
        else:
            hit = p_ok or e_ok

        trace.append(
            f"{rule['level']} rule ({rule['match']}): "
            f"purchase>={rule['purchase_decline_pct_min']} "
            f"is {p_ok}, "
            f"engagement>={rule['engagement_decline_pct_min']} "
            f"is {e_ok} "
            f"-> {'MATCH' if hit else 'no match'}"
        )

        if hit:
            level = rule["level"]
            break

    if level is None:
        return _result(
            "error",
            reason="No matching risk rule or default rule found",
        )

    return _result(
        "ok",
        {
            "customer_id": customer_id,
            "risk_level": level,
            "purchase_decline_pct": p,
            "engagement_decline_pct": e,
            "seasonal": False,
            "rule_trace": trace,
        },
    )


@logged
def get_eligible_offers(
    customer_id,
    risk_level,
    data_dir="data",
    rules_path="config/risk_rules.yaml",
    budget_spent=0,
    budget_override=None,
):
    rules = load_rules(rules_path)
    order = rules["risk_order"]

    if risk_level not in order:
        return _result(
            "error",
            reason=f"Unknown risk level: {risk_level}",
        )

    try:
        # keep_default_na=False: a blank stays "" and "none" stays "none".
        customers = pd.read_csv(
            f"{data_dir}/customers.csv",
            dtype=str,
            keep_default_na=False,
        ).drop_duplicates()

        complaints = pd.read_csv(
            f"{data_dir}/complaints.csv",
            dtype=str,
            keep_default_na=False,
        ).drop_duplicates()

        # "Open ", "OPEN" and "open" all count as open.
        complaints["status"] = (
            complaints["status"].str.strip().str.lower()
        )

        offers = pd.read_excel(
            f"{data_dir}/offers.xlsx",
            sheet_name="offers",
        ).drop_duplicates()

        budgets = pd.read_excel(
            f"{data_dir}/offers.xlsx",
            sheet_name="budgets",
        )

    except FileNotFoundError as exc:
        return _result(
            "error",
            reason=f"Data file missing: {exc}",
        )

    cust = customers[customers["customer_id"] == customer_id]

    if cust.empty:
        return _result(
            "error",
            reason=f"Unknown customer {customer_id}",
        )

    segment = cust.iloc[0]["segment"].strip()
    contact = cust.iloc[0]["contact_preference"].strip().lower()

    # 1. Respect consent before considering any offer.
    #    A blank preference is treated as "no consent on file".
    if contact in ("none", ""):
        return _result(
            "blocked",
            {
                "customer_id": customer_id,
                "eligible_offers": [],
            },
            reason=(
                "Customer opted out of contact or has no contact "
                "preference on file. No outreach allowed."
            ),
        )

    # 2. Resolve open complaints before offering anything.
    open_complaints = complaints[
        (complaints["customer_id"] == customer_id)
        & (complaints["status"] == "open")
    ]

    if not open_complaints.empty:
        complaint_ids = ", ".join(
            open_complaints["complaint_id"].astype(str)
        )

        return _result(
            "service_first",
            {
                "customer_id": customer_id,
                "open_complaints": complaint_ids,
                "eligible_offers": [],
            },
            reason=(
                f"Open complaint ({complaint_ids}). "
                "Resolve service issue before any offer."
            ),
        )

    # 3. Calculate the segment's remaining budget.
    budget_row = budgets[budgets["segment"] == segment]

    if budget_row.empty:
        segment_budget_left = 0.0
    else:
        segment_budget_left = (
            float(budget_row.iloc[0]["budget"])
            - float(budget_spent)
        )

    segment_budget_left = max(0.0, segment_budget_left)

    # 4. Apply the optional user-specified cap without bypassing
    #    the segment's configured budget.
    if budget_override is None:
        budget_left = segment_budget_left
    else:
        try:
            budget_cap = float(budget_override)
        except (TypeError, ValueError):
            return _result(
                "error",
                reason="Budget override must be a valid number",
            )

        if pd.isna(budget_cap) or budget_cap < 0:
            return _result(
                "error",
                reason="Budget override must be non-negative",
            )

        budget_left = min(segment_budget_left, budget_cap)

    eligible = []
    rejected = []

    # 5. Check risk level, segment and budget for every offer.
    for _, offer in offers.iterrows():
        offer_id = offer["offer_id"]

        # Edge case: an offer with a blank or invalid cost is skipped.
        if pd.isna(offer["cost"]):
            rejected.append(f"{offer_id}: cost is missing")
            continue

        cost = float(offer["cost"])

        if order.index(risk_level) < order.index(offer["min_risk"]):
            rejected.append(
                f"{offer_id}: risk {risk_level} "
                f"below required {offer['min_risk']}"
            )

        elif offer["eligible_segment"] != segment:
            rejected.append(
                f"{offer_id}: for {offer['eligible_segment']} "
                f"segment, customer is {segment}"
            )

        elif cost > budget_left:
            rejected.append(
                f"{offer_id}: cost {cost} "
                f"exceeds budget left {budget_left}"
            )

        else:
            eligible.append({
                "offer_id": offer_id,
                "description": offer["description"],
                "cost": cost,
            })

    # Cheapest eligible offer first.
    eligible.sort(key=lambda item: item["cost"])

    data = {
        "customer_id": customer_id,
        "segment": segment,
        "risk_level": risk_level,
        "budget_left": budget_left,
        "segment_budget_left": segment_budget_left,
        "eligible_offers": eligible,
        "rejected": rejected,
    }

    reason = (
        ""
        if eligible
        else "No eligible offer. Escalate or monitor instead."
    )

    return _result("ok", data, reason)


REQUIRED_PLAN_FIELDS = [
    "customer_id",
    "period",
    "risk_level",
    "action",
]


def _connect(db_path):
    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            period TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            action TEXT NOT NULL,
            offer_id TEXT,
            cost REAL,
            rationale TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (customer_id, period)
        )
    """)

    return conn


@logged
def save_retention_plan(plan, db_path="data/plans.db"):
    if not isinstance(plan, dict):
        return _result(
            "error",
            reason="plan must be a dictionary",
        )

    missing = [
        field
        for field in REQUIRED_PLAN_FIELDS
        if not plan.get(field)
    ]

    if missing:
        return _result(
            "error",
            reason=f"Missing required fields: {', '.join(missing)}",
        )

    conn = None

    try:
        conn = _connect(db_path)

        # One plan per customer and analysis month.
        row = conn.execute(
            "SELECT plan_id, status, created_at FROM plans "
            "WHERE customer_id = ? AND period = ?",
            (plan["customer_id"], plan["period"]),
        ).fetchone()

        if row:
            return _result(
                "duplicate",
                {
                    "plan_id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                },
                reason=(
                    "A plan already exists for this customer "
                    "and period. Nothing saved."
                ),
            )

        # Always pending human review; never auto-approved.
        plan_id = "PLAN-" + uuid.uuid4().hex[:8].upper()

        created_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )

        conn.execute(
            "INSERT INTO plans VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                plan_id,
                plan["customer_id"],
                plan["period"],
                plan["risk_level"],
                plan["action"],
                plan.get("offer_id"),
                plan.get("cost"),
                plan.get("rationale", ""),
                "pending_review",
                created_at,
            ),
        )

        conn.commit()

    except sqlite3.Error as exc:
        return _result(
            "error",
            reason=f"Database error: {exc}",
        )

    finally:
        if conn is not None:
            conn.close()

    return _result(
        "ok",
        {
            "plan_id": plan_id,
            "status": "pending_review",
            "created_at": created_at,
        },
        reason="Saved for human review. No action has been taken.",
    )


def list_retention_plans(db_path="data/plans.db"):
    conn = _connect(db_path)

    try:
        rows = conn.execute(
            "SELECT * FROM plans ORDER BY created_at"
        ).fetchall()

        return rows

    finally:
        conn.close()
def get_customer_memory(customer_id, db_path="data/plans.db"):
    """Retrieve previous retention plans for one customer."""
    conn = _connect(db_path)

    try:
        rows = conn.execute(
            """
            SELECT plan_id, period, risk_level, action,
                   offer_id, cost, status, created_at
            FROM plans
            WHERE customer_id = ?
            ORDER BY created_at DESC
            """,
            (customer_id,),
        ).fetchall()

        columns = [
            "plan_id",
            "period",
            "risk_level",
            "action",
            "offer_id",
            "cost",
            "status",
            "created_at",
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        conn.close()  

@logged
def lookup_customer_memory(customer_id, db_path="data/plans.db"):
    """Same as get_customer_memory, but logged and in the standard result shape."""
    if not customer_id or not isinstance(customer_id, str):
        return _result("error", reason="customer_id must be a non-empty string")
    plans = get_customer_memory(customer_id, db_path=db_path)
    return _result("ok", {"customer_id": customer_id,
                          "previous_plans": plans, "count": len(plans)},
                   reason="" if plans else "No previous plans for this customer")             