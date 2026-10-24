import re
from agent.graph import run_agent, get_index
from agent.guardrails import is_action_request, is_injected, DECLINE_TEXT
from retrieval.policy import retrieve

CID = re.compile(r"\bC-\d{3}\b", re.I)
OFFER = re.compile(r"\bOF-\d+\b", re.I)


def _summary(state):
    r = state["recommendation"]
    if r["outcome"] in ("error", "needs_info"):
        return r["action"]
    src = ", ".join(r["sources"]) or "no policy source found"
    return (f"{r['customer_id'] if 'customer_id' in r else ''} {r['action']} "
            f"Risk: {r['risk_level']}. Source: {src}. Next: {r['next_action']}").strip()


def _follow_up(msg, state):
    r, q = state["recommendation"], msg.lower()
    if r["outcome"] in ("error", "needs_info"):
        return None
    m = OFFER.search(msg)
    if m:
        oid = m.group(0).upper()
        if r.get("offer") and r["offer"]["offer_id"] == oid:
            return f"{oid} is the recommended offer."
        for alt in r["alternatives"]:
            if alt.startswith(oid):
                return alt
        return f"{oid} is not among the eligible or rejected offers for this customer."
    if "risk" in q or "why" in q:
        if r["rule_trace"]:
            return "How the risk level was decided: " + " | ".join(r["rule_trace"])
    if "cost" in q or "budget" in q:
        o = r.get("offer")
        return f"Offer cost: {o['cost']}." if o else "There is no recommended offer, so no cost."
    if "source" in q or "cite" in q:
        return "Sources: " + (", ".join(r["sources"]) or "none found")
    if "assum" in q:
        return "Assumptions: " + " ".join(r["assumptions"])
    return None


def handle_message(message, state=None):
    msg = (message or "").strip()
    if not msg:
        return {"kind": "empty", "text": "Please type a customer ID (e.g. C-301) or a question."}
    if is_action_request(msg):
        return {"kind": "declined", "text": DECLINE_TEXT}
    m = CID.search(msg)
    if m:
        # Reuse the periods, budget and thread of the current analysis.
        # With no earlier analysis, the agent falls back to its defaults.
        st_ = state or {}
        new = run_agent(
            m.group(0).upper(),
            analysis_month=st_.get("analysis_month"),
            comparison_month=st_.get("comparison_month"),
            budget_limit=st_.get("budget_limit"),
            thread_id=st_.get("thread_id", "default"),
        )
        return {"kind": "analysis", "text": _summary(new), "state": new}
    if state:
        answer = _follow_up(msg, state)
        if answer:
            return {"kind": "follow_up", "text": answer}
    r = retrieve(get_index(), msg)
    hits = [h for h in r["hits"] if not is_injected(h["text"])]
    if hits:
        return {"kind": "policy", "text": f"{hits[0]['text']} ({hits[0]['ref']})"}
    return {"kind": "not_found",
            "text": "I couldn't find that in the retention policy, so I won't guess."}