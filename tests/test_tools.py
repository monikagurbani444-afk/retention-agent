import json
import os

from tools.analysis import (
    calculate_purchase_decline,
    calculate_engagement_score,
    assign_retention_risk,
    get_eligible_offers,
    save_retention_plan,
    list_retention_plans,
)


# ---------- calculate_purchase_decline ----------
def test_purchase_decline_normal():
    r = calculate_purchase_decline("C-301")
    assert r["status"] == "ok"
    assert r["data"]["purchase_decline_pct"] == 79.17
    assert r["data"]["seasonal"] is False


def test_purchase_decline_seasonal():
    r = calculate_purchase_decline("C-303")
    assert r["status"] == "ok"
    assert r["data"]["seasonal"] is True


def test_purchase_decline_new_customer():
    r = calculate_purchase_decline("C-302")
    assert r["status"] == "insufficient_data"


def test_purchase_decline_unknown_customer():
    assert calculate_purchase_decline("C-999")["status"] == "error"


def test_purchase_decline_empty_id():
    assert calculate_purchase_decline("")["status"] == "error"


def test_purchase_decline_missing_file():
    r = calculate_purchase_decline(
        "C-301",
        data_dir="no_such_folder"
    )
    assert r["status"] == "error"


# ---------- calculate_engagement_score ----------
def test_engagement_normal():
    r = calculate_engagement_score("C-301")
    assert r["status"] == "ok"
    assert r["data"]["engagement_decline_pct"] == 90.91


def test_engagement_new_customer():
    assert (
        calculate_engagement_score("C-302")["status"]
        == "insufficient_data"
    )


def test_engagement_unknown_customer():
    assert calculate_engagement_score("C-999")["status"] == "error"


# ---------- assign_retention_risk ----------
def test_risk_high():
    assert assign_retention_risk("C-301")["data"]["risk_level"] == "High"


def test_risk_medium():
    assert assign_retention_risk("C-307")["data"]["risk_level"] == "Medium"


def test_risk_boundary_is_high():
    r = assign_retention_risk("C-308")  # Exactly 50% and 40%
    assert r["data"]["risk_level"] == "High"


def test_risk_seasonal_is_low():
    r = assign_retention_risk("C-303")
    assert r["data"]["risk_level"] == "Low"
    assert r["data"]["seasonal"] is True


def test_risk_new_customer_not_assigned():
    r = assign_retention_risk("C-302")
    assert r["status"] == "insufficient_data"
    assert "risk_level" not in r["data"]


def test_risk_has_rule_trace():
    assert len(assign_retention_risk("C-301")["data"]["rule_trace"]) > 0


# ---------- get_eligible_offers ----------
def ids(result):
    return [o["offer_id"] for o in result["data"]["eligible_offers"]]


def test_offers_high_risk():
    assert ids(get_eligible_offers("C-301", "High")) == ["OF-1", "OF-2"]


def test_offers_medium_risk_excludes_high_offer():
    assert ids(get_eligible_offers("C-307", "Medium")) == ["OF-1"]


def test_offers_open_complaint_service_first():
    r = get_eligible_offers("C-304", "High")
    assert r["status"] == "service_first"
    assert ids(r) == []


def test_offers_opted_out_blocked():
    r = get_eligible_offers("C-306", "High")
    assert r["status"] == "blocked"
    assert ids(r) == []


def test_offers_segment_mismatch():
    r = get_eligible_offers("C-305", "High")
    assert r["status"] == "ok"
    assert ids(r) == []


def test_offers_budget_exhausted():
    r = get_eligible_offers("C-301", "High", budget_spent=4800)
    assert ids(r) == []


def test_offers_unknown_customer():
    assert get_eligible_offers("C-999", "High")["status"] == "error"


def test_offers_bad_risk_level():
    assert get_eligible_offers("C-301", "Extreme")["status"] == "error"


# ---------- save_retention_plan (uses a temporary database) ----------
PLAN = {
    "customer_id": "C-301",
    "period": "2026-09",
    "risk_level": "High",
    "action": "Offer 10% voucher",
    "offer_id": "OF-1",
    "cost": 300,
}


def test_save_ok_is_pending_review(tmp_path):
    r = save_retention_plan(
        PLAN,
        db_path=str(tmp_path / "t.db")
    )
    assert r["status"] == "ok"
    assert r["data"]["status"] == "pending_review"
    assert r["data"]["plan_id"].startswith("PLAN-")


def test_save_retry_is_duplicate(tmp_path):
    db = str(tmp_path / "t.db")

    first = save_retention_plan(PLAN, db_path=db)
    second = save_retention_plan(PLAN, db_path=db)

    assert second["status"] == "duplicate"
    assert second["data"]["plan_id"] == first["data"]["plan_id"]
    assert len(list_retention_plans(db_path=db)) == 1


def test_save_missing_fields(tmp_path):
    r = save_retention_plan(
        {"customer_id": "C-301"},
        db_path=str(tmp_path / "t.db")
    )
    assert r["status"] == "error"


def test_save_not_a_dict(tmp_path):
    assert (
        save_retention_plan(
            "hello",
            db_path=str(tmp_path / "t.db")
        )["status"]
        == "error"
    )


# ---------- logging test ----------
def test_tool_calls_are_logged():
    assign_retention_risk("C-301")

    log_path = os.environ["RETENTION_LOG_PATH"]

    with open(log_path, encoding="utf-8") as f:
        entries = [json.loads(line) for line in f]

    tools_logged = [e["tool"] for e in entries]

    assert "assign_retention_risk" in tools_logged
    assert "calculate_purchase_decline" in tools_logged