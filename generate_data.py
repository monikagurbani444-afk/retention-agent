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

    # --- extra scenarios (rows above are unchanged) ---
    # new customers get 2 months of history (enough for the rule; keeps the file small)
    # C-309 Loyal segment, High risk
    ("C-309","2026-08",5,20000),("C-309","2026-09",1,4000),
    # C-310 exact duplicate row (data-entry error)
    ("C-310","2026-08",4,10000),("C-310","2026-09",1,2000),
    ("C-310","2026-09",1,2000),
    # C-311 blank amount in the analysis month
    ("C-311","2026-08",4,10000),("C-311","2026-09",2,None),
    # C-312 high purchase drop, but engagement has a blank
    ("C-312","2026-08",4,10000),("C-312","2026-09",1,2000),
    # C-313 high risk, blank contact preference (see customers)
    ("C-313","2026-08",4,10000),("C-313","2026-09",1,2000),
    # C-314 high risk, repeat complainant with open complaints (see complaints)
    ("C-314","2026-08",4,10000),("C-314","2026-09",1,2000),
    # C-315 / C-316 only appear in customers + complaints (tool-level tests)
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

    ("C-309","2026-08",10,5),("C-309","2026-09",2,0),
    ("C-310","2026-08",10,5),("C-310","2026-09",2,0),
    ("C-311","2026-08",10,5),("C-311","2026-09",2,0),
    ("C-312","2026-08",10,5),("C-312","2026-09",None,0),   # blank logins
    ("C-313","2026-08",10,5),("C-313","2026-09",2,0),
    ("C-314","2026-08",10,5),("C-314","2026-09",2,0),
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

    ("C-309","Loyal","email"),("C-310","Regular","email"),
    ("C-311","Regular","email"),("C-312","Regular","email"),
    ("C-312","Regular","email"),                       # duplicate row
    ("C-313","Regular",""),                            # blank contact preference
    ("C-314","Regular","email"),("C-315","Regular","email"),
    ("C-316","Regular","email"),
]

pd.DataFrame(
    customers,
    columns=["customer_id", "segment", "contact_preference"]
).to_csv("data/customers.csv", index=False)


# complaints
complaints = [
    ("CMP-1","C-304","2026-09-05","open","Late delivery, no response"),
    ("CMP-2","C-301","2026-07-10","resolved","Wrong item shipped"),
    ("CMP-3","C-301","2026-03-18","resolved","Invoice amount incorrect"),
    ("CMP-4","C-302","2026-09-12","resolved","Login problem"),
    ("CMP-5","C-303","2026-05-02","resolved","Damaged packaging"),
    ("CMP-6","C-305","2026-08-20","resolved","Billing query"),
    ("CMP-7","C-307","2026-06-14","resolved","Refund delay"),
    ("CMP-8","C-314","2026-04-09","resolved","Late delivery"),
    ("CMP-9","C-314","2026-08-30","open","Late delivery again, no reply"),
    ("CMP-10","C-314","2026-09-14","open","Refund not received"),
    ("CMP-11","C-315","2026-02-11","resolved","Wrong item shipped"),
    ("CMP-12","C-315","2026-07-22","resolved","Missing invoice"),
    ("CMP-13","C-316","2026-09-02","Open ","Product quality"),  # messy status
    ("CMP-13","C-316","2026-09-02","Open ","Product quality"),  # duplicate row
    ("CMP-14","C-309","2026-01-25","resolved","Slow support"),
    ("CMP-15","C-310","2026-06-30","","Unclear issue"),          # blank status
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
    ("OF-4","Early-access discount","Medium",400,"Loyal"),
    ("OF-5","Free premium upgrade","High",1500,"Loyal"),
    ("OF-6","Surprise gift","High",None,"Loyal"),      # blank cost
    ("OF-4","Early-access discount","Medium",400,"Loyal"),  # duplicate row
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