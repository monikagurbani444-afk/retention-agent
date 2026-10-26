import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


fig, ax = plt.subplots(figsize=(13, 7))
ax.set_xlim(0, 13)
ax.set_ylim(0, 7)
ax.axis("off")


def box(x, y, w, h, text, color, fs=9):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.05",
            fc=color,
            ec="#333",
            lw=1.2,
        )
    )
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fs,
    )


def arrow(x1, y1, x2, y2, label=""):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="->",
            lw=1.3,
            color="#333",
        ),
    )

    if label:
        ax.text(
            (x1 + x2) / 2 + 0.1,
            (y1 + y2) / 2,
            label,
            fontsize=8,
            ha="left",
            va="center",
            color="#b00020",
            bbox=dict(fc="white", ec="none", pad=1.5),
        )


BLUE, GREEN, AMBER, GREY, PURPLE = (
    "#cfe3ff",
    "#d5f0d5",
    "#ffe9b5",
    "#e6e6e6",
    "#e6dcff",
)


box(0.2, 5.3, 1.9, 0.9,
    "User input\n(customer ID / chat)", GREY)

box(2.6, 5.3, 1.7, 0.9,
    "Guardrails\n(decline actions)", AMBER)

box(4.8, 5.3, 1.7, 0.9,
    "1. Validate input\n(ID, months, budget)\nblank: ask user", BLUE, fs=8)

box(7.0, 5.3, 2.2, 0.9,
    "2. assign_retention_risk\n(purchase + engagement\n+ seasonality)", BLUE)

box(9.7, 5.3, 2.2, 0.9,
    "3. get_eligible_offers\n(consent, complaint,\nrisk, segment, budget)", BLUE)

box(9.7, 3.7, 2.2, 0.9,
    "4. Decide outcome\n(offer / monitor /\nservice first / blocked)", GREEN)

box(7.0, 3.7, 2.2, 0.9,
    "5. Policy retrieval\n(PDF, grade, rewrite x2,\ninjection filter)", GREEN)

box(4.4, 3.7, 2.0, 0.9,
    "6. Build\nrecommendation", GREEN)

box(1.9, 3.7, 2.0, 0.9,
    "7. save_retention_plan\n(pending_review,\nno duplicates)", BLUE)

box(4.7, 2.85, 2.2, 0.65,
    "Memory: thread history\n+ saved-plan lookup", PURPLE, fs=8)

box(1.9, 1.7, 2.0, 0.9,
    "Human reviewer\napproves any action", AMBER)

box(4.4, 1.7, 2.0, 0.9,
    "UI: recommendation,\nsources, trace", GREY)

box(7.0, 1.7, 2.6, 0.9,
    "tool_calls.jsonl\n(every call logged)", GREY)


arrow(2.1, 5.75, 2.6, 5.75)
arrow(4.3, 5.75, 4.8, 5.75)
arrow(6.5, 5.75, 7.0, 5.75)
arrow(9.2, 5.75, 9.7, 5.75)

arrow(10.8, 5.3, 10.8, 4.6)
arrow(9.7, 4.15, 9.2, 4.15)
arrow(7.0, 4.15, 6.4, 4.15)
arrow(4.4, 4.15, 3.9, 4.15)

arrow(2.9, 3.7, 2.9, 2.6)
arrow(3.9, 4.0, 4.4, 2.6)

# Memory feeds the recommendation (earlier plans are looked up).
arrow(5.8, 3.5, 5.8, 3.7)

arrow(6.0, 5.3, 5.6, 4.6, "error / needs info")
arrow(8.1, 5.3, 7.9, 4.6, "new customer")


ax.text(
    6.5,
    0.8,
    "Business rules are enforced in code (tools + config/risk_rules.yaml). "
    "The agent only recommends.",
    ha="center",
    fontsize=9,
    style="italic",
)

ax.set_title(
    "Customer Retention Advisory Agent: Workflow",
    fontsize=13,
    weight="bold",
)

plt.savefig(
    "docs/workflow_diagram.png",
    dpi=160,
    bbox_inches="tight",
)

print("saved docs/workflow_diagram.png")