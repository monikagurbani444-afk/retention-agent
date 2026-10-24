from tools.analysis import assign_retention_risk, get_eligible_offers

for cid in ["C-307", "C-308"]:
    risk = assign_retention_risk(cid)
    level = risk["data"]["risk_level"]
    print(cid, risk["status"], level,
          "| purchase", risk["data"]["purchase_decline_pct"],
          "| engagement", risk["data"]["engagement_decline_pct"])
    offers = get_eligible_offers(cid, level)
    print("   offers:", [o["offer_id"] for o in offers["data"]["eligible_offers"]])

print("Budget exhausted:", get_eligible_offers("C-301", "High", budget_spent=4800)["data"]["eligible_offers"])