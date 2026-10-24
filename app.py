import json
import os
import uuid

import pandas as pd
import streamlit as st

from agent.graph import run_agent
from agent.chat import handle_message
from tools.analysis import list_retention_plans, load_rules

st.set_page_config(
    page_title="Retention Advisory Agent",
    page_icon="📉",
    layout="wide",
)

COLORS = {
    "High": "#d93025",
    "Medium": "#f29900",
    "Low": "#188038",
    "Not assigned": "#5f6368",
}

SAMPLES = {
    "C-301": "Normal decline, offer allowed",
    "C-302": "New customer (little history)",
    "C-303": "Seasonal decline",
    "C-304": "Open complaint",
    "C-305": "No matching offers",
    "C-306": "Opted out of contact",
    "C-307": "Medium risk",
    "C-308": "Boundary case (exactly 50% / 40%)",
}

PLAN_COLS = [
    "plan_id",
    "customer_id",
    "period",
    "risk_level",
    "action",
    "offer_id",
    "cost",
    "rationale",
    "status",
    "created_at",
]

if "state" not in st.session_state:
    st.session_state.state = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# One thread per browser session = thread-based memory.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = uuid.uuid4().hex

# ---------- Sidebar ----------
rules = load_rules()
comparison_rules = rules["comparison"]

with st.sidebar:
    st.title("Retention Advisor")
    st.caption(
        "Recommendations only. A human must approve any action."
    )

    cid = st.text_input(
        "Customer ID",
        value="C-301",
    ).strip().upper()

    analysis_month = st.text_input(
        "Analysis month (YYYY-MM)",
        value=comparison_rules["analysis_month"],
        help="The month you want to analyse.",
    ).strip()

    comparison_month = st.text_input(
        "Comparison month (YYYY-MM)",
        value=comparison_rules["comparison_month"],
        help="The earlier month used for comparison.",
    ).strip()

    budget_limit = st.number_input(
        "Maximum offer budget",
        min_value=0.0,
        value=500.0,
        step=50.0,
        help=(
            "Maximum budget allowed for an offer. "
            "The customer's segment budget still applies."
        ),
    )

    if st.button("Analyse customer", type="primary"):
        st.session_state.state = run_agent(
            cid,
            analysis_month=analysis_month,
            comparison_month=comparison_month,
            budget_limit=budget_limit,
            thread_id=st.session_state.thread_id,
        )
        st.session_state.chat = []

    st.markdown("**Sample customers**")

    for customer_id, description in SAMPLES.items():
        st.caption(f"{customer_id}: {description}")

# ---------- Main page ----------
st.title("Customer Retention Advisory Agent")

state = st.session_state.state

tab_rec, tab_trace, tab_plans = st.tabs(
    ["Recommendation", "Tool-call trace", "Saved plans"]
)

# ---------- Recommendation ----------
with tab_rec:
    if not state:
        st.info(
            "Enter a customer ID in the sidebar and click "
            "**Analyse customer**."
        )
    else:
        rec = state["recommendation"]

        if rec["outcome"] == "needs_info":
            st.warning(rec["action"])

        elif rec["outcome"] == "error":
            st.error(rec["action"])

        else:
            level = rec["risk_level"]

            st.markdown(
                f"<span style='background:"
                f"{COLORS.get(level, '#5f6368')};"
                f"color:white;padding:4px 14px;"
                f"border-radius:14px;font-weight:600'>"
                f"{level} risk</span>"
                " &nbsp; <span style='color:gray'>"
                "Rule-based, not predictive</span>",
                unsafe_allow_html=True,
            )

            st.subheader(rec["action"])

            calc = rec["calculations"]

            if calc:
                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Purchase decline",
                    f"{calc['purchase_decline_pct']}%",
                )

                c2.metric(
                    "Engagement decline",
                    f"{calc['engagement_decline_pct']}%",
                )

                c3.metric(
                    "Seasonal pattern",
                    "Yes" if calc["seasonal"] else "No",
                )

            st.markdown(f"**Next action:** {rec['next_action']}")

            if rec["alternatives"]:
                st.markdown("**Alternatives / rejected options**")

                for alternative in rec["alternatives"]:
                    st.write(f"- {alternative}")

            st.markdown(
                "**Sources:** "
                + (", ".join(rec["sources"]) or "none found")
            )

            st.markdown("**Assumptions**")

            for assumption in rec["assumptions"]:
                st.write(f"- {assumption}")

            if rec["rule_trace"]:
                with st.expander("Why this risk level (rule trace)"):
                    for line in rec["rule_trace"]:
                        st.write(f"- {line}")

            saved = state.get("saved", {})

            if saved.get("status") == "ok":
                st.success(
                    f"Saved as {saved['data']['plan_id']} "
                    "(pending review)"
                )

            elif saved.get("status") == "duplicate":
                st.warning(
                    f"Plan already exists: {saved['data']['plan_id']} "
                    f"(status: {saved['data']['status']}). "
                    "Nothing new saved."
                )

# ---------- Trace ----------
with tab_trace:
    if state:
        st.markdown("**Agent steps**")

        for step in state.get("trace", []):
            st.write(f"- {step}")

    log = "data/tool_calls.jsonl"

    if os.path.exists(log):
        st.markdown("**Recent tool calls (log)**")

        with open(log, encoding="utf-8") as file:
            rows = [
                json.loads(line)
                for line in file.readlines()[-15:]
                if line.strip()
            ]

        if rows:
            log_df = pd.DataFrame(rows)
            columns = [
                column
                for column in ["time", "tool", "status", "reason"]
                if column in log_df.columns
            ]

            st.dataframe(
                log_df[columns],
                hide_index=True,
            )

# ---------- Saved plans ----------
with tab_plans:
    plans = list_retention_plans()

    if plans:
        st.dataframe(
            pd.DataFrame(plans, columns=PLAN_COLS),
            hide_index=True,
        )
    else:
        st.info("No plans saved yet.")

# ---------- Chat ----------
st.divider()
st.subheader("Ask a follow-up")

st.caption(
    "Try: why not OF-2? | what is the source? | "
    "Send it now | analyse C-304"
)

for role, message_text in st.session_state.chat:
    with st.chat_message(role):
        st.write(message_text)

msg = st.chat_input(
    "Ask about this recommendation or type a customer ID"
)

if msg:
    result = handle_message(
        msg,
        st.session_state.state,
    )

    st.session_state.chat.append(("user", msg))
    st.session_state.chat.append(("assistant", result["text"]))

    if result.get("state"):
        st.session_state.state = result["state"]

    st.rerun()