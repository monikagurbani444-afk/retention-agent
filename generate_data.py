import pandas as pd
import os

os.makedirs("data", exist_ok=True)

# purchases: customer_id, month, orders, amount
purchases = [
    # C-301 declining (not seasonal: last year was flat)
    ("C-301","2025-08",4,11500),("C-301","2025-09",4,12000),
    ("C-301","2026-08",4,12000),("C-301","2026-09",1,2500),

    # C-302 new customer, one month only
    ("C-302","2026-09",3,9000),

    # C-303 seasonal decline (same drop last year)
    ("C-303","2025-08",5,14000),("C-303","2025-09",2,5800),
    ("C-303","2026-08",5,15000),("C-303","2026-09",2,6000),

    # C-304 declining + open complaint
    ("C-304","2025-08",4,10000),("C-304","2025-09",4,10200),
    ("C-304","2026-08",4,10000),("C-304","2026-09",1,2000),

    # C-305 declining, segment has no offers
    ("C-305","2025-08",6,29000),("C-305","2025-09",6,30000),
    ("C-305","2026-08",6,30000),("C-305","2026-09",2,9000),

    # C-306 declining, opted out of contact
    ("C-306","2025-08",3,8000),("C-306","2025-09",3,8100),
    ("C-306","2026-08",3,8000),("C-306","2026-09",1,2500),

    # C-307 Medium risk (30% purchase drop, last year flat)
    ("C-307","2025-08",4,10000),("C-307","2025-09",4,10000),
    ("C-307","2026-08",4,10000),("C-307","2026-09",3,7000),

    # C-308 boundary (exactly 50% drop, last year flat)
    ("C-308","2025-08",4,10000),("C-308","2025-09",4,10000),
    ("C-308","2026-08",4,10000),("C-308","2026-09",2,5000),
]

pd.DataFrame(
    purchases,
    columns=["customer_id", "month", "orders", "amount"]
).to_csv("data/purchases.csv", index=False)


# engagement: customer_id, month, logins, emails_opened
engagement = [
    ("C-301","2026-08",10,6),("C-301","2026-09",2,0),
    ("C-302","2026-09",5,3),
    ("C-303","2026-08",9,5),("C-303","2026-09",4,2),
    ("C-304","2026-08",8,4),("C-304","2026-09",1,0),
    ("C-305","2026-08",12,7),("C-305","2026-09",3,1),
    ("C-306","2026-08",7,4),("C-306","2026-09",2,0),

    ("C-307","2026-08",10,5),("C-307","2026-09",8,4),
    ("C-308","2026-08",6,2),("C-308","2026-09",4,1),
]

pd.DataFrame(
    engagement,
    columns=["customer_id", "month", "logins", "emails_opened"]
).to_csv("data/engagement.csv", index=False)


# customers: segment and contact preference
customers = [
    ("C-301","Regular","email"),("C-302","Regular","email"),
    ("C-303","Regular","email"),("C-304","Regular","email"),
    ("C-305","Enterprise","email"),("C-306","Regular","none"),

    ("C-307","Regular","email"),("C-308","Regular","email"),
]

pd.DataFrame(
    customers,
    columns=["customer_id", "segment", "contact_preference"]
).to_csv("data/customers.csv", index=False)


# complaints
complaints = [
    ("CMP-1","C-304","2026-09-05","open","Late delivery, no response"),
    ("CMP-2","C-301","2026-07-10","resolved","Wrong item shipped"),
]

pd.DataFrame(
    complaints,
    columns=["complaint_id", "customer_id", "date", "status", "issue"]
).to_csv("data/complaints.csv", index=False)


# offers.xlsx with two sheets: offers and budgets
offers = [
    ("OF-1","10% voucher","Medium",300,"Regular"),
    ("OF-2","15% off + free shipping","High",600,"Regular"),
    ("OF-3","Loyalty bonus points","High",800,"Loyal"),
]

budgets = [
    ("Regular",5000),
    ("Loyal",3000),
    ("Enterprise",2000),
]

with pd.ExcelWriter("data/offers.xlsx") as w:
    pd.DataFrame(
        offers,
        columns=["offer_id", "description", "min_risk", "cost", "eligible_segment"]
    ).to_excel(w, sheet_name="offers", index=False)

    pd.DataFrame(
        budgets,
        columns=["segment", "budget"]
    ).to_excel(w, sheet_name="budgets", index=False)

print("Data files created in /data")