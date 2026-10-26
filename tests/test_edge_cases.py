from tools.analysis import (
    calculate_purchase_decline,
    calculate_engagement_score,
    get_eligible_offers,
)


def ids(result):
    return [o["offer_id"] for o in result["data"]["eligible_offers"]]


def test_duplicate_purchase_row_is_ignored():
    r = calculate_purchase_decline("C-310")
    assert r["status"] == "ok"
    assert r["data"]["purchase_decline_pct"] == 80.0


def test_blank_purchase_amount_is_insufficient_data():
    assert calculate_purchase_decline("C-311")["status"] == "insufficient_data"


def test_blank_engagement_value_is_insufficient_data():
    assert calculate_engagement_score("C-312")["status"] == "insufficient_data"


def test_blank_contact_preference_is_blocked():
    assert get_eligible_offers("C-313", "High")["status"] == "blocked"


def test_repeat_complainant_with_open_complaints():
    r = get_eligible_offers("C-314", "High")
    assert r["status"] == "service_first"
    assert "CMP-9" in r["reason"] and "CMP-10" in r["reason"]


def test_only_resolved_complaints_do_not_block():
    r = get_eligible_offers("C-315", "High")
    assert r["status"] == "ok"
    assert ids(r) == ["OF-1", "OF-2"]


def test_status_with_trailing_space_still_counts_as_open():
    assert get_eligible_offers("C-316", "High")["status"] == "service_first"


def test_loyal_customer_gets_loyal_offers_only():
    r = get_eligible_offers("C-309", "High")
    assert ids(r) == ["OF-4", "OF-3", "OF-5"]


def test_offer_with_blank_cost_is_rejected_not_offered():
    r = get_eligible_offers("C-309", "High")
    assert "OF-6" not in ids(r)
    assert any("OF-6" in x for x in r["data"]["rejected"])
