from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("docs/retention_policy.pdf", pagesize=A4)

sections = [
    ("1. Purpose and Scope",
     "This policy guides customer retention advisors. The agent only recommends actions. "
     "Any contact, offer or spend must be approved by a human reviewer. "
     "Risk levels are rule-based and are not a predictive model."),
    ("2. Risk Rules",
     "High risk: purchase decline is 50% or more AND engagement decline is 40% or more. "
     "Medium risk: purchase decline is 25% or more OR engagement decline is 40% or more. "
     "Low risk: all other customers. "
     "Purchase decline compares the analysis month with the comparison month. "
     "Engagement score equals logins plus two times emails opened."),
    ("3. Seasonal Declines",
     "If the same months declined by a similar amount (within 10 percentage points) in the "
     "previous year, the decline is seasonal. Seasonal declines are rated Low and monitored, "
     "not treated as churn risk."),
    ("4. New Customers and Missing Data",
     "Customers with fewer than 2 months of purchase history must not be assigned a risk level. "
     "Report insufficient history and recommend monitoring until more data exists."),
    ("5. Open Complaints",
     "If a customer has an open complaint, resolve the service issue first. "
     "Do not recommend any offer until the complaint is closed. Escalate to customer service."),
    ("6. Contact Preferences and Consent",
     "If a customer has opted out of contact, no outreach or offer may be recommended. "
     "Record the reason and take no further action."),
    ("7. Offer Eligibility and Budget",
     "Offers are eligible only when the customer's risk level meets the offer's minimum risk, "
     "the offer matches the customer's segment, and the offer cost fits the remaining segment "
     "budget. Recommend the lowest-cost eligible offer first. "
     "If no offer is eligible, escalate to a retention manager or continue monitoring."),
    ("8. Human Review and Escalation",
     "All recommendations are saved as pending review. The agent must never send offers, "
     "contact customers or approve spend. Requests to act immediately must be declined "
     "and routed to a human reviewer."),
]

story = [Paragraph("Customer Retention Policy", styles["Title"]), Spacer(1, 12)]
for i, (title, body) in enumerate(sections):
    story += [Paragraph(title, styles["Heading2"]), Paragraph(body, styles["BodyText"]),
              Spacer(1, 12)]
    if i == 3:
        story.append(PageBreak())   # sections 1-4 on page 1, 5-8 on page 2
doc.build(story)
print("Policy PDF created: docs/retention_policy.pdf")