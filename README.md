# Customer Retention Advisory Agent (Project 15)

A single agent with tools and a conditional workflow that recommends retention actions
for customers whose purchases and engagement are declining. It **only recommends**:
every plan is saved as `pending_review` for a human to approve.

**Team:** Monika Gurbani (data, tools, tests) and [Amber Sharma] (policy, retrieval, agent, UI)
**Live app:** [deploying]

## Features
- Rule-based risk (Low / Medium / High) from purchase and engagement decline. Not a predictive model.
- Seasonality check against the same months last year.
- Offer eligibility: contact consent, open complaints, risk level, segment, budget.
- Policy retrieval from a PDF with source references (e.g. "Policy §7, p.2"), relevance grading and up to 2 query rewrites.
- Guardrails: declines action requests ("send it now"), ignores instructions inside retrieved text, never guesses when nothing matches.
- Saved plans with unique IDs, timestamps and duplicate prevention (SQLite).
- Every tool call logged to `data/tool_calls.jsonl`; rule trace shown in the UI.

## Architecture
See `docs/workflow_diagram.png`.
`validate -> assign_retention_risk -> get_eligible_offers -> decide -> policy retrieval -> build -> save_retention_plan`
Business rules live in code (`tools/analysis.py`) and `config/risk_rules.yaml`, never in prompts.

## Run locally
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python generate_data.py
python make_policy.py
streamlit run app.py
```

## Tests
```
pytest -v
```
40 tests cover normal, boundary (exactly 50% / 40%), failure, missing information, irrelevant
retrieval, tool failure, conflicting evidence (seasonal vs high decline), repeated requests and
follow-up questions. Results are in `test_report.txt`.

## Sample customers
| ID | Scenario |
|---|---|
| C-301 | Normal decline, offer recommended |
| C-302 | New customer, insufficient history |
| C-303 | Seasonal decline, monitor only |
| C-304 | Open complaint, service first |
| C-305 | No matching offers |
| C-306 | Opted out of contact |
| C-307 | Medium risk |
| C-308 | Boundary case (High) |

## Project structure
`app.py` UI · `agent/` workflow, guardrails, chat · `tools/` five tools and logger ·
`retrieval/` policy search · `config/` risk rules · `data/` sample data ·
`docs/` policy PDF and diagram · `tests/`

## Assumptions and limits
- Data is synthetic. The compared months are set in `config/risk_rules.yaml`.
- Seasonal declines are rated Low and monitored.
- Retrieval uses TF-IDF keyword matching, not embeddings.
- On free hosting, saved plans reset when the app restarts.
- No tool sends offers or contacts customers.