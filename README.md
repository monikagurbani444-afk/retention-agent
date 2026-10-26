# Customer Retention Advisory Agent (Project 15)

A single agent with tools and a conditional workflow that recommends retention actions
for customers whose purchases and engagement are declining. It **only recommends**:
every plan is saved as `pending_review` for a human to approve.

**Team:** Monika Gurbani (data, tools, tests) and Amber Sharma (policy, retrieval, agent, UI)
**Live app:** https://retention-advisor.streamlit.app/

## Features
- Rule-based risk (Low / Medium / High) from purchase and engagement decline. Not a predictive model.
- Seasonality check against the same months last year.
- Offer eligibility: contact consent, open complaints, risk level, segment, budget.
- Missing information: if the analysis month, comparison month or budget is blank, the agent asks for it before calling any tool.
- Input validation: bad month format, identical months and a negative budget are rejected with a clear message.
- Policy retrieval from a PDF with source references (e.g. "Policy §7, p.2"), relevance grading and up to 2 query rewrites.
- Memory:
  - Thread-based memory (LangGraph `MemorySaver`): each session has its own thread that keeps a history of analyses.
  - Saved-plan memory: earlier plans for the same customer are looked up and shown in the assumptions.
  - Customer data is re-read from the files on every analysis, so reassessments use fresh data.
- Guardrails: declines action requests ("send it now"), ignores instructions inside retrieved text, never guesses when nothing matches.
- Saved plans with unique IDs, timestamps and duplicate prevention (SQLite).
- Every tool call logged to `data/tool_calls.jsonl`; rule trace shown in the UI. A sample log from the test run is in `docs/sample_tool_calls.jsonl`.

## Architecture
See `docs/workflow_diagram.png`.

`validate -> assign_retention_risk -> get_eligible_offers -> decide -> policy retrieval -> build -> save_retention_plan`

Conditional routing:
- Blank fields or invalid input: stop at `validate`, ask the user, nothing is saved.
- New customer (insufficient history): skip offers, go to policy retrieval, risk not assigned.
- Opted out, open complaint, seasonal decline or no eligible offer: `decide` picks the outcome and no offer is sent.

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
68 tests cover normal, boundary (exactly 50% / 40%), failure, missing information, input validation,
irrelevant retrieval, tool failure, conflicting evidence (seasonal vs high decline), repeated requests,
follow-up questions, thread memory, saved-plan memory, and blank or duplicate data. Results are in `test_report.txt`.

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
- Data is synthetic. Analysis month, comparison month and budget are entered in the app; defaults come from `config/risk_rules.yaml`.
- The budget is entered in the app rather than stored in a file, so the budget input is the only source for it. The offers file (`data/offers.xlsx`) holds offer details and costs, not budgets.
- Business rules (risk thresholds, defaults and seasonality settings) are stored in YAML (`config/risk_rules.yaml`) rather than JSON. The format is simple and human-editable, and the rules are read by code, not hard-coded in prompts.
- The offers file has 7 rows. It is kept small so each offer's eligibility can be traced by hand, and the test expectations depend on these specific rows. Adding rows would require updating the tests.
- The agent analyses one customer at a time (no segment-level analysis).
- Seasonal declines are rated Low and monitored.
- Retrieval uses TF-IDF keyword matching, not embeddings.
- Thread memory is kept in RAM and resets when the app restarts or a new session starts.
- On free hosting, saved plans also reset when the app restarts.
- No tool sends offers or contacts customers.