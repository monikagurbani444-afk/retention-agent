from agent.graph import run_agent

for cid in ["C-301", "C-302", "C-303", "C-304", "C-305",
            "C-306", "C-307", "C-308", "C-999", ""]:
    s = run_agent(cid)
    rec = s["recommendation"]
    print(f"{cid or '(empty)':8} {rec['outcome']:17} | {rec['action']}")
    print(f"{'':8} sources: {rec['sources']} | saved: {s.get('saved', {}).get('status')}")