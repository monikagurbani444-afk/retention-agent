from typing import TypedDict
from langgraph.graph import StateGraph, END
from tools.analysis import (assign_retention_risk, get_eligible_offers,
                            save_retention_plan, load_rules)
from retrieval.policy import PolicyIndex, retrieve

_INDEX = None


def get_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = PolicyIndex()
    return _INDEX


class State(TypedDict, total=False):
    customer_id: str
    risk: dict
    offers: dict
    outcome: str
    error: str
    policy: dict
    recommendation: dict
    saved: dict
    trace: list


POLICY_QUERY = {
    "recommend_offer": "offer eligibility segment budget lowest cost",
    "monitor_seasonal": "seasonal declines same months previous year",
    "service_first": "open complaint resolve service issue before offer",
    "blocked": "customer opted out of contact consent no outreach",
    "no_offer": "no eligible offer escalate retention manager",
    "insufficient_data": "new customers fewer than 2 months insufficient history",
}


def validate(s):
    cid = (s.get("customer_id") or "").strip().upper()
    if not cid:
        return {"outcome": "error", "error": "Please enter a customer ID.",
                "trace": s["trace"] + ["validate: empty customer ID"]}
    return {"customer_id": cid, "trace": s["trace"] + [f"validate: {cid}"]}


def risk(s):
    r = assign_retention_risk(s["customer_id"])
    t = s["trace"] + [f"assign_retention_risk -> {r['status']}"]
    if r["status"] == "insufficient_data":
        return {"risk": r, "outcome": "insufficient_data", "trace": t}
    if r["status"] != "ok":
        return {"risk": r, "outcome": "error", "error": r["reason"], "trace": t}
    return {"risk": r, "trace": t + [f"risk level: {r['data']['risk_level']}"]}


def offers(s):
    level = s["risk"]["data"]["risk_level"]
    o = get_eligible_offers(s["customer_id"], level)
    return {"offers": o, "trace": s["trace"] + [f"get_eligible_offers -> {o['status']}"]}


def decide(s):
    o, d = s["offers"], s["risk"]["data"]
    if o["status"] in ("blocked", "service_first"):
        outcome = o["status"]
    elif o["status"] != "ok":
        return {"outcome": "error", "error": o["reason"]}
    elif d["seasonal"]:
        outcome = "monitor_seasonal"
    elif o["data"]["eligible_offers"]:
        outcome = "recommend_offer"
    else:
        outcome = "no_offer"
    return {"outcome": outcome, "trace": s["trace"] + [f"decision: {outcome}"]}


def policy(s):
    r = retrieve(get_index(), POLICY_QUERY[s["outcome"]])
    t = s["trace"] + [f"policy search -> {r['status']} ({len(r['attempts'])} tries)"]
    return {"policy": r, "trace": t}


def build(s):
    outcome = s["outcome"]
    if outcome == "error":
        return {"recommendation": {"outcome": "error", "action": s.get("error", "Error"),
                "next_action": "Check the customer ID and try again.",
                "sources": [], "assumptions": [], "calculations": {}, "alternatives": []}}
    d = s["risk"]["data"]
    eligible = s.get("offers", {}).get("data", {}).get("eligible_offers", [])
    rejected = s.get("offers", {}).get("data", {}).get("rejected", [])
    best = eligible[0] if eligible else None
    action, nxt, alternatives = {
        "recommend_offer": (
            f"Recommend {best['description']} ({best['offer_id']}, cost {best['cost']}) "
            "for human approval" if best else "",
            "Send to a retention manager for approval.",
            [f"{o['offer_id']}: {o['description']} (cost {o['cost']})" for o in eligible[1:]] + rejected),
        "monitor_seasonal": ("Monitor only: the decline matches last year's seasonal pattern.",
                             "Re-check next period.", []),
        "service_first": ("Resolve the open complaint before any offer.",
                          "Escalate to customer service.", []),
        "blocked": ("No outreach: the customer opted out of contact.",
                    "Take no further action.", []),
        "no_offer": ("No eligible offer.", "Escalate to a retention manager or keep monitoring.",
                     rejected),
        "insufficient_data": ("Risk not assigned: not enough purchase history.",
                              "Monitor until at least 2 months of data exist.", []),
    }[outcome]
    sources = [h["ref"] for h in s.get("policy", {}).get("hits", [])[:1]]
    assumptions = ["Risk level is rule-based, not a predictive model.",
                   "Comparison uses the months set in config/risk_rules.yaml.",
                   "This is a recommendation only. A human must approve any action."]
    if not sources:
        assumptions.append("No matching policy section was found.")
    calc = {}
    if d:
        calc = {"purchase_decline_pct": d.get("purchase_decline_pct"),
                "engagement_decline_pct": d.get("engagement_decline_pct"),
                "seasonal": d.get("seasonal")}
    rec = {"customer_id": s["customer_id"], "outcome": outcome, "action": action,
           "risk_level": d.get("risk_level", "Not assigned"), "calculations": calc,
           "alternatives": alternatives, "sources": sources, "assumptions": assumptions,
           "next_action": nxt, "offer": best,
           "rule_trace": d.get("rule_trace", [])}
    return {"recommendation": rec}


def save(s):
    rec = s["recommendation"]
    plan = {"customer_id": rec["customer_id"],
            "period": load_rules()["comparison"]["analysis_month"],
            "risk_level": rec["risk_level"], "action": rec["action"],
            "offer_id": rec["offer"]["offer_id"] if rec["offer"] else None,
            "cost": rec["offer"]["cost"] if rec["offer"] else None,
            "rationale": "; ".join(rec["sources"])}
    r = save_retention_plan(plan)
    return {"saved": r, "trace": s["trace"] + [f"save_retention_plan -> {r['status']}"]}


def after_validate(s):
    return "build" if s.get("outcome") == "error" else "risk"


def after_risk(s):
    if s.get("outcome") == "error":
        return "build"
    return "policy" if s.get("outcome") else "offers"


def after_decide(s):
    return "build" if s.get("outcome") == "error" else "policy"


def after_build(s):
    return END if s["recommendation"]["outcome"] == "error" else "save"


def make_graph():
    g = StateGraph(State)
    for name, fn in [("validate", validate), ("risk", risk), ("offers", offers),
                     ("decide", decide), ("policy", policy), ("build", build),
                     ("save", save)]:
        g.add_node(name, fn)
    g.set_entry_point("validate")
    g.add_conditional_edges("validate", after_validate)
    g.add_conditional_edges("risk", after_risk)
    g.add_edge("offers", "decide")
    g.add_conditional_edges("decide", after_decide)
    g.add_edge("policy", "build")
    g.add_conditional_edges("build", after_build)
    g.add_edge("save", END)
    return g.compile()


_APP = None


def run_agent(customer_id):
    global _APP
    if _APP is None:
        _APP = make_graph()
    return _APP.invoke({"customer_id": customer_id, "trace": []})