from tools.analysis import (
    get_customer_memory,
    save_retention_plan,
)


def test_customer_memory_retrieves_saved_plan(tmp_path):
    db = str(tmp_path / "memory_test.db")

    plan = {
        "customer_id": "C-TEST",
        "period": "2026-09",
        "risk_level": "Medium",
        "action": "Recommend an offer for human approval",
        "offer_id": "OF-1",
        "cost": 300,
        "rationale": "Test policy reference",
    }

    saved = save_retention_plan(plan, db_path=db)

    assert saved["status"] == "ok"

    memory = get_customer_memory("C-TEST", db_path=db)

    assert len(memory) == 1
    assert memory[0]["risk_level"] == "Medium"
    assert memory[0]["offer_id"] == "OF-1"
    assert memory[0]["period"] == "2026-09"
    assert memory[0]["status"] == "pending_review"


def test_customer_memory_is_empty_for_unknown_customer(tmp_path):
    db = str(tmp_path / "empty_memory.db")

    memory = get_customer_memory("C-UNKNOWN", db_path=db)

    assert memory == []


def test_customer_memory_keeps_multiple_periods(tmp_path):
    db = str(tmp_path / "multiple_periods.db")

    first_plan = {
        "customer_id": "C-TEST",
        "period": "2026-08",
        "risk_level": "Low",
        "action": "Monitor customer",
        "rationale": "First period",
    }

    second_plan = {
        "customer_id": "C-TEST",
        "period": "2026-09",
        "risk_level": "High",
        "action": "Recommend an offer for human approval",
        "offer_id": "OF-1",
        "cost": 300,
        "rationale": "Second period",
    }

    first_saved = save_retention_plan(first_plan, db_path=db)
    second_saved = save_retention_plan(second_plan, db_path=db)

    assert first_saved["status"] == "ok"
    assert second_saved["status"] == "ok"

    memory = get_customer_memory("C-TEST", db_path=db)

    assert len(memory) == 2
    assert {item["period"] for item in memory} == {
        "2026-08",
        "2026-09",
    }