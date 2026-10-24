import re
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from tools.analysis import (
    assign_retention_risk,
    get_eligible_offers,
    save_retention_plan,
    lookup_customer_memory,
    load_rules,
)
from retrieval.policy import PolicyIndex, retrieve
from agent.guardrails import is_injected


_INDEX = None
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def get_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = PolicyIndex()
    return _INDEX


class State(TypedDict, total=False):
    customer_id: str
    analysis_month: str
    comparison_month: str
    budget_limit: float
    thread_id: str
    risk: dict
    offers: dict
    outcome: str
    error: str
    policy: dict
    recommendation: dict
    saved: dict
    trace: list
    history: list


POLICY_QUERY = {
    "recommend_offer": "offer eligibility segment budget lowest cost",
    "monitor_seasonal": "seasonal declines same months previous year",
    "service_first": "open complaint resolve service issue before offer",
    "blocked": "customer opted out of contact consent no outreach",
    "no_offer": "no eligible offer escalate retention manager",
    "insufficient_data": "new customers fewer than 2 months insufficient history",
}


def validate(s):
    trace = s["trace"]
    cid = (s.get("customer_id") or "").strip().upper()

    if not cid:
        return {
            "outcome": "error",
            "error": "Please enter a customer ID.",
            "trace": trace + ["validate: empty customer ID"],
        }

    cfg = load_rules()["comparison"]
    am = s.get("analysis_month")
    cm = s.get("comparison_month")
    bl = s.get("budget_limit")

    # Missing information. A blank field (empty string) means the user
    # left it empty, so the agent asks. None means the caller did not
    # supply it, so the configured default is used.
    missing = []
    if am is not None and not str(am).strip():
        missing.append("analysis month")
    if cm is not None and not str(cm).strip():
        missing.append("comparison month")
    if isinstance(bl, str) and not bl.strip():
        missing.append("budget")

    if missing:
        return {
            "customer_id": cid,
            "outcome": "needs_info",
            "error": "Please provide: " + ", ".join(missing) + ".",
            "trace": trace + [f"validate: missing {missing}"],
        }

    am = cfg["analysis_month"] if am is None else str(am).strip()
    cm = cfg["comparison_month"] if cm is None else str(cm).strip()

    if not MONTH_RE.match(am) or not MONTH_RE.match(cm):
        return {
            "customer_id": cid,
            "outcome": "error",
            "error": "Months must be in YYYY-MM format (for example 2026-09).",
            "trace": trace + ["validate: bad month format"],
        }

    if am == cm:
        return {
            "customer_id": cid,
            "outcome": "error",
            "error": "Analysis and comparison months must be different.",
            "trace": trace + ["validate: identical months"],
        }

    if bl is not None:
        try:
            bl = float(bl)
        except (TypeError, ValueError):
            return {
                "customer_id": cid,
                "outcome": "error",
                "error": "Budget must be a valid number.",
                "trace": trace + ["validate: budget not a number"],
            }
        if bl < 0:
            return {
                "customer_id": cid,
                "outcome": "error",
                "error": "Budget must be non-negative.",
                "trace": trace + ["validate: negative budget"],
            }

    return {
        "customer_id": cid,
        "analysis_month": am,
        "comparison_month": cm,
        "budget_limit": bl,
        "trace": trace + [f"validate: {cid}, {cm} vs {am}"],
    }


def risk(s):
    r = assign_retention_risk(
        s["customer_id"],
        analysis_month=s["analysis_month"],
        comparison_month=s["comparison_month"],
    )
    t = s["trace"] + [
        f"assign_retention_risk -> {r['status']}"
    ]

    if r["status"] == "insufficient_data":
        return {
            "risk": r,
            "outcome": "insufficient_data",
            "trace": t,
        }

    if r["status"] != "ok":
        return {
            "risk": r,
            "outcome": "error",
            "error": r["reason"],
            "trace": t,
        }

    return {
        "risk": r,
        "trace": t + [
            f"risk level: {r['data']['risk_level']}"
        ],
    }


def offers(s):
    level = s["risk"]["data"]["risk_level"]
    o = get_eligible_offers(
        s["customer_id"],
        level,
        budget_override=s.get("budget_limit"),
    )

    return {
        "offers": o,
        "trace": s["trace"] + [
            f"get_eligible_offers -> {o['status']}"
        ],
    }


def decide(s):
    o, d = s["offers"], s["risk"]["data"]

    if o["status"] in ("blocked", "service_first"):
        outcome = o["status"]

    elif o["status"] != "ok":
        return {
            "outcome": "error",
            "error": o["reason"],
        }

    elif d["seasonal"]:
        outcome = "monitor_seasonal"

    elif o["data"]["eligible_offers"]:
        outcome = "recommend_offer"

    else:
        outcome = "no_offer"

    return {
        "outcome": outcome,
        "trace": s["trace"] + [f"decision: {outcome}"],
    }


def policy(s):
    r = retrieve(get_index(), POLICY_QUERY[s["outcome"]])

    # Remove retrieved chunks containing embedded instructions.
    r["hits"] = [
        h for h in r["hits"]
        if not is_injected(h["text"])
    ]

    t = s["trace"] + [
        f"policy search -> {r['status']} "
        f"({len(r['attempts'])} tries)"
    ]

    return {
        "policy": r,
        "trace": t,
    }


def build(s):
    outcome = s["outcome"]

    if outcome in ("error", "needs_info"):
        return {
            "recommendation": {
                "outcome": outcome,
                "action": s.get("error", "Error"),
                "next_action": "Check the details and try again.",
                "sources": [],
                "assumptions": [],
                "calculations": {},
                "alternatives": [],
            }
        }

    d = s.get("risk", {}).get("data", {})

    # Memory: earlier saved plans for this customer.
    prev = lookup_customer_memory(s["customer_id"])
    previous = (
        prev["data"].get("previous_plans", [])
        if prev["status"] == "ok" else []
    )

    eligible = (
        s.get("offers", {})
        .get("data", {})
        .get("eligible_offers", [])
    )

    rejected = (
        s.get("offers", {})
        .get("data", {})
        .get("rejected", [])
    )

    best = eligible[0] if eligible else None

    action, nxt, alternatives = {
        "recommend_offer": (
            (
                f"Recommend {best['description']} "
                f"({best['offer_id']}, cost {best['cost']}) "
                "for human approval"
            ) if best else "",
            "Send to a retention manager for approval.",
            [
                f"{o['offer_id']}: {o['description']} "
                f"(cost {o['cost']})"
                for o in eligible[1:]
            ] + rejected,
        ),

        "monitor_seasonal": (
            "Monitor only: the decline matches last year's "
            "seasonal pattern.",
            "Re-check next period.",
            [],
        ),

        "service_first": (
            "Resolve the open complaint before any offer.",
            "Escalate to customer service.",
            [],
        ),

        "blocked": (
            "No outreach: the customer opted out of contact.",
            "Take no further action.",
            [],
        ),

        "no_offer": (
            "No eligible offer.",
            "Escalate to a retention manager or keep monitoring.",
            rejected,
        ),

        "insufficient_data": (
            "Risk not assigned: not enough purchase history.",
            "Monitor until at least 2 months of data exist.",
            [],
        ),
    }[outcome]

    sources = [
        h["ref"]
        for h in s.get("policy", {}).get("hits", [])[:1]
    ]

    assumptions = [
        "Risk level is rule-based, not a predictive model.",
        f"Comparison uses {s['comparison_month']} vs "
        f"{s['analysis_month']}.",
        "This is a recommendation only. A human must approve any action.",
    ]

    if not sources:
        assumptions.append(
            "No matching policy section was found."
        )

    if previous:
        assumptions.append(
            f"{len(previous)} earlier plan(s) on file for this "
            f"customer; latest: {previous[0]['action']}"
        )

    calc = {}

    if d:
        calc = {
            "purchase_decline_pct": d.get("purchase_decline_pct"),
            "engagement_decline_pct": d.get("engagement_decline_pct"),
            "seasonal": d.get("seasonal"),
        }

    rec = {
        "customer_id": s["customer_id"],
        "outcome": outcome,
        "action": action,
        "risk_level": d.get("risk_level", "Not assigned"),
        "calculations": calc,
        "alternatives": alternatives,
        "sources": sources,
        "assumptions": assumptions,
        "next_action": nxt,
        "offer": best,
        "rule_trace": d.get("rule_trace", []),
    }

    return {"recommendation": rec}


def save(s):
    rec = s["recommendation"]

    plan = {
        "customer_id": rec["customer_id"],
        "period": s["analysis_month"],
        "risk_level": rec["risk_level"],
        "action": rec["action"],
        "offer_id": (
            rec["offer"]["offer_id"]
            if rec["offer"] else None
        ),
        "cost": (
            rec["offer"]["cost"]
            if rec["offer"] else None
        ),
        "rationale": "; ".join(rec["sources"]),
    }

    r = save_retention_plan(plan)

    return {
        "saved": r,
        "history": s.get("history", []) + [{
            "customer_id": rec["customer_id"],
            "outcome": rec["outcome"],
            "offer_id": plan["offer_id"],
        }],
        "trace": s["trace"] + [
            f"save_retention_plan -> {r['status']}"
        ],
    }


def after_validate(s):
    return (
        "build"
        if s.get("outcome") in ("error", "needs_info")
        else "risk"
    )


def after_risk(s):
    if s.get("outcome") == "error":
        return "build"

    return "policy" if s.get("outcome") else "offers"


def after_decide(s):
    return "build" if s.get("outcome") == "error" else "policy"


def after_build(s):
    return (
        END
        if s["recommendation"]["outcome"] in ("error", "needs_info")
        else "save"
    )


def make_graph():
    g = StateGraph(State)

    for name, fn in [
        ("validate", validate),
        ("risk", risk),
        ("offers", offers),
        ("decide", decide),
        ("policy", policy),
        ("build", build),
        ("save", save),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("validate")

    g.add_conditional_edges("validate", after_validate)
    g.add_conditional_edges("risk", after_risk)
    g.add_edge("offers", "decide")
    g.add_conditional_edges("decide", after_decide)
    g.add_edge("policy", "build")
    g.add_conditional_edges("build", after_build)
    g.add_edge("save", END)

    # MemorySaver gives thread-based memory across runs.
    return g.compile(checkpointer=MemorySaver())


_APP = None


def run_agent(
    customer_id,
    analysis_month=None,
    comparison_month=None,
    budget_limit=None,
    thread_id="default",
):
    global _APP

    if _APP is None:
        _APP = make_graph()

    # Per-run fields are reset so one customer's result never leaks
    # into the next run on the same thread. `history` is not reset:
    # it is the thread memory.
    return _APP.invoke(
        {
            "customer_id": customer_id,
            "analysis_month": analysis_month,
            "comparison_month": comparison_month,
            "budget_limit": budget_limit,
            "thread_id": thread_id,
            "trace": [],
            "outcome": "",
            "error": "",
            "risk": {},
            "offers": {},
            "policy": {},
            "recommendation": {},
            "saved": {},
        },
        config={"configurable": {"thread_id": thread_id}},
    )