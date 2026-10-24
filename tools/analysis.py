import sqlite3
import uuid
from datetime import datetime, timezone

import pandas as pd
import yaml

from tools.logger import logged


def load_rules(path="config/risk_rules.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def _same_month_last_year(month):
    year, mm = month.split("-")
    return f"{int(year) - 1}-{mm}"


def _result(status, data=None, reason=""):
    # Every tool returns this same shape
    return {"status": status, "data": data or {}, "reason": reason}


@logged
def calculate_purchase_decline(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml"
):
    rules = load_rules(rules_path)

    analysis_month = (
        analysis_month or rules["comparison"]["analysis_month"]
    )
    comparison_month = (
        comparison_month or rules["comparison"]["comparison_month"]
    )

    # 1. Validate input
    if not customer_id or not isinstance(customer_id, str):
        return _result(
            "error",
            reason="customer_id must be a non-empty string"
        )

    # 2. Load this customer's purchases
    try:
        df = pd.read_csv(f"{data_dir}/purchases.csv")
    except FileNotFoundError:
        return _result("error", reason="purchases.csv not found")

    df = df[df["customer_id"] == customer_id]

    if df.empty:
        return _result(
            "error",
            reason=f"No purchase records for {customer_id}"
        )

    # 3. New customer check
    months_of_history = df["month"].nunique()

    if months_of_history < rules["minimum_history_months"]:
        return _result(
            "insufficient_data",
            reason=(
                f"Only {months_of_history} month(s) of history; "
                f"need {rules['minimum_history_months']}. "
                "Risk not assigned."
            )
        )

    amounts = df.set_index("month")["amount"]

    def decline_pct(old_month, new_month):
        if old_month not in amounts or new_month not in amounts:
            return None

        old, new = amounts[old_month], amounts[new_month]

        if old == 0:
            return None

        return float(round((old - new) / old * 100, 2))

    # 4. Current decline
    current = decline_pct(comparison_month, analysis_month)

    if current is None:
        return _result(
            "insufficient_data",
            reason=(
                f"Missing data for {comparison_month} "
                f"or {analysis_month}"
            )
        )

    # 5. Seasonality: same two months one year earlier
    last_year = decline_pct(
        _same_month_last_year(comparison_month),
        _same_month_last_year(analysis_month)
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
        )
    )


@logged
def calculate_engagement_score(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml"
):
    rules = load_rules(rules_path)

    analysis_month = (
        analysis_month or rules["comparison"]["analysis_month"]
    )
    comparison_month = (
        comparison_month or rules["comparison"]["comparison_month"]
    )

    w = rules["engagement_weights"]

    # 1. Validate input
    if not customer_id or not isinstance(customer_id, str):
        return _result(
            "error",
            reason="customer_id must be a non-empty string"
        )

    # 2. Load engagement data
    try:
        df = pd.read_csv(f"{data_dir}/engagement.csv")
    except FileNotFoundError:
        return _result("error", reason="engagement.csv not found")

    df = df[df["customer_id"] == customer_id]

    if df.empty:
        return _result(
            "error",
            reason=f"No engagement records for {customer_id}"
        )

    # 3. Calculate weighted engagement score
    df = df.assign(
        score=(
            df["logins"] * w["logins"]
            + df["emails_opened"] * w["emails_opened"]
        )
    )

    scores = df.set_index("month")["score"]

    # 4. Validate monthly data
    if comparison_month not in scores or analysis_month not in scores:
        return _result(
            "insufficient_data",
            reason=(
                f"Missing engagement data for {comparison_month} "
                f"or {analysis_month}"
            )
        )

    # 5. Calculate engagement decline
    old = float(scores[comparison_month])
    new = float(scores[analysis_month])

    if old == 0:
        return _result(
            "insufficient_data",
            reason="Comparison month score is 0"
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
        }
    )


@logged
def assign_retention_risk(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    data_dir="data",
    rules_path="config/risk_rules.yaml"
):
    rules = load_rules(rules_path)

    kwargs = dict(
        analysis_month=analysis_month,
        comparison_month=comparison_month,
        data_dir=data_dir,
        rules_path=rules_path
    )

    trace = []

    # 1. Run the two analysis tools
    purchase = calculate_purchase_decline(customer_id, **kwargs)
    trace.append(
        f"calculate_purchase_decline -> {purchase['status']}"
    )

    if purchase["status"] != "ok":
        return _result(
            purchase["status"],
            reason=purchase["reason"]
        )

    engagement = calculate_engagement_score(customer_id, **kwargs)
    trace.append(
        f"calculate_engagement_score -> {engagement['status']}"
    )

    if engagement["status"] != "ok":
        return _result(
            engagement["status"],
            reason=engagement["reason"]
        )

    p = purchase["data"]["purchase_decline_pct"]
    e = engagement["data"]["engagement_decline_pct"]
    seasonal = purchase["data"]["seasonal"]

    trace.append(
        f"purchase decline {p}%, engagement decline {e}%"
    )

    # 2. Seasonal declines are not treated as churn risk
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
            reason="Decline matches last year's seasonal pattern"
        )

    # 3. Apply YAML rules, first match wins
    for rule in rules["risk_levels"]:
        if rule["match"] == "default":
            trace.append(
                f"no higher rule matched -> {rule['level']}"
            )
            level = rule["level"]
            break

        p_ok = p >= rule["purchase_decline_pct_min"]
        e_ok = e >= rule["engagement_decline_pct_min"]

        hit = (
            (p_ok and e_ok)
            if rule["match"] == "all"
            else (p_ok or e_ok)
        )

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

    return _result(
        "ok",
        {
            "customer_id": customer_id,
            "risk_level": level,
            "purchase_decline_pct": p,
            "engagement_decline_pct": e,
            "seasonal": False,
            "rule_trace": trace,
        }
    )


@logged
def get_eligible_offers(
    customer_id,
    risk_level,
    data_dir="data",
    rules_path="config/risk_rules.yaml",
    budget_spent=0
):
    rules = load_rules(rules_path)
    order = rules["risk_order"]

    if risk_level not in order:
        return _result(
            "error",
            reason=f"Unknown risk level: {risk_level}"
        )

    try:
        customers = pd.read_csv(f"{data_dir}/customers.csv")
        complaints = pd.read_csv(f"{data_dir}/complaints.csv")
        offers = pd.read_excel(
            f"{data_dir}/offers.xlsx",
            sheet_name="offers"
        )
        budgets = pd.read_excel(
            f"{data_dir}/offers.xlsx",
            sheet_name="budgets"
        )
    except FileNotFoundError as e:
        return _result("error", reason=f"Data file missing: {e}")

    cust = customers[customers["customer_id"] == customer_id]

    if cust.empty:
        return _result(
            "error",
            reason=f"Unknown customer {customer_id}"
        )

    segment = cust.iloc[0]["segment"]
    contact = cust.iloc[0]["contact_preference"]

    # 1. Consent
    if contact == "none":
        return _result(
            "blocked",
            {
                "customer_id": customer_id,
                "eligible_offers": []
            },
            reason=(
                "Customer opted out of contact. "
                "No outreach allowed."
            )
        )

    # 2. Open complaint: service first
    open_c = complaints[
        (complaints["customer_id"] == customer_id)
        & (complaints["status"] == "open")
    ]

    if not open_c.empty:
        ids = ", ".join(open_c["complaint_id"].astype(str))

        return _result(
            "service_first",
            {
                "customer_id": customer_id,
                "open_complaints": ids,
                "eligible_offers": []
            },
            reason=(
                f"Open complaint ({ids}). "
                "Resolve service issue before any offer."
            )
        )

    # 3-5. Risk, segment, budget
    budget_row = budgets[budgets["segment"] == segment]

    budget_left = (
        float(budget_row.iloc[0]["budget"]) - budget_spent
        if not budget_row.empty
        else 0.0
    )

    eligible, rejected = [], []

    for _, o in offers.iterrows():
        if order.index(risk_level) < order.index(o["min_risk"]):
            rejected.append(
                f"{o['offer_id']}: risk {risk_level} "
                f"below required {o['min_risk']}"
            )

        elif o["eligible_segment"] != segment:
            rejected.append(
                f"{o['offer_id']}: for {o['eligible_segment']} "
                f"segment, customer is {segment}"
            )

        elif o["cost"] > budget_left:
            rejected.append(
                f"{o['offer_id']}: cost {o['cost']} "
                f"exceeds budget left {budget_left}"
            )

        else:
            eligible.append(
                {
                    "offer_id": o["offer_id"],
                    "description": o["description"],
                    "cost": float(o["cost"])
                }
            )

    # Cheapest eligible offer first
    eligible.sort(key=lambda x: x["cost"])

    data = {
        "customer_id": customer_id,
        "segment": segment,
        "risk_level": risk_level,
        "budget_left": budget_left,
        "eligible_offers": eligible,
        "rejected": rejected
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
    "action"
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
    # 1. Validate
    if not isinstance(plan, dict):
        return _result(
            "error",
            reason="plan must be a dictionary"
        )

    missing = [
        f for f in REQUIRED_PLAN_FIELDS
        if not plan.get(f)
    ]

    if missing:
        return _result(
            "error",
            reason=f"Missing required fields: {', '.join(missing)}"
        )

    conn = None

    try:
        conn = _connect(db_path)

        # 2. Duplicate check (same customer + period)
        row = conn.execute(
            "SELECT plan_id, status, created_at FROM plans "
            "WHERE customer_id = ? AND period = ?",
            (plan["customer_id"], plan["period"])
        ).fetchone()

        if row:
            return _result(
                "duplicate",
                {
                    "plan_id": row[0],
                    "status": row[1],
                    "created_at": row[2]
                },
                reason=(
                    "A plan already exists for this customer "
                    "and period. Nothing saved."
                )
            )

        # 3. Save as pending human review (never auto-approved)
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
                created_at
            )
        )

        conn.commit()

    except sqlite3.Error as e:
        return _result(
            "error",
            reason=f"Database error: {e}"
        )

    finally:
        if conn is not None:
            conn.close()

    return _result(
        "ok",
        {
            "plan_id": plan_id,
            "status": "pending_review",
            "created_at": created_at
        },
        reason="Saved for human review. No action has been taken."
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