import uuid

import pytest
import agent.graph as graph
from agent.chat import handle_message
from tools.analysis import (
    save_retention_plan,
    lookup_customer_memory,
    load_rules,
)

C = load_rules()["comparison"]


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db = str(tmp_path / "plans.db")
    monkeypatch.setattr(
        graph,
        "save_retention_plan",
        lambda plan: save_retention_plan(plan, db_path=db),
    )
    monkeypatch.setattr(
        graph,
        "lookup_customer_memory",
        lambda cid: lookup_customer_memory(cid, db_path=db),
    )


def run(cid, budget=500.0, thread_id=None):
    """Run the agent with the configured periods on a fresh thread."""
    return graph.run_agent(
        cid,
        analysis_month=C["analysis_month"],
        comparison_month=C["comparison_month"],
        budget_limit=budget,
        thread_id=thread_id or uuid.uuid4().hex,
    )


def test_blank_fields_ask_for_missing_info():
    r = graph.run_agent(
        "C-301", analysis_month="", comparison_month="", budget_limit=""
    )["recommendation"]
    assert r["outcome"] == "needs_info"
    assert "analysis month" in r["action"]
    assert "comparison month" in r["action"]
    assert "budget" in r["action"]


def test_one_blank_field_asks_only_for_that_field():
    r = graph.run_agent(
        "C-301",
        analysis_month="",
        comparison_month=C["comparison_month"],
        budget_limit=500.0,
    )["recommendation"]
    assert r["outcome"] == "needs_info"
    assert "analysis month" in r["action"]
    assert "comparison month" not in r["action"]


def test_needs_info_saves_nothing():
    r = graph.run_agent(
        "C-301", analysis_month="", comparison_month="", budget_limit=""
    )
    assert r["saved"] == {}


def test_new_customer_no_crash():
    r = run("C-302")["recommendation"]
    assert r["outcome"] == "insufficient_data"
    assert r["risk_level"] == "Not assigned"


def test_opted_out_no_outreach():
    assert run("C-306")["recommendation"]["outcome"] == "blocked"


def test_open_complaint_service_first():
    assert run("C-304")["recommendation"]["outcome"] == "service_first"


def test_seasonal_is_monitor_only():
    assert run("C-303")["recommendation"]["outcome"] == "monitor_seasonal"


def test_budget_cap_blocks_offer():
    assert run("C-301", budget=0)["recommendation"]["outcome"] == "no_offer"


def test_thread_memory_keeps_history():
    t = uuid.uuid4().hex
    run("C-301", thread_id=t)
    r = run("C-307", thread_id=t)
    assert len(r["history"]) == 2


def test_new_thread_starts_empty():
    r = run("C-301", thread_id=uuid.uuid4().hex)
    assert len(r["history"]) == 1


def test_earlier_plan_is_mentioned_on_rerun():
    run("C-301")
    r = run("C-301")["recommendation"]
    assert any("earlier plan" in a for a in r["assumptions"])


def test_chat_analyse_reuses_state_settings():
    first = run("C-301", budget=300.0)
    out = handle_message("analyse C-304", first)
    assert out["kind"] == "analysis"
    assert out["state"]["budget_limit"] == 300.0
    assert out["state"]["thread_id"] == first["thread_id"]


def test_chat_analyse_without_state_uses_defaults():
    out = handle_message("analyse C-304")
    assert out["kind"] == "analysis"
    assert out["state"]["recommendation"]["outcome"] == "service_first"