import yaml
with open("config/risk_rules.yaml") as f:
    rules = yaml.safe_load(f)
print(rules["risk_levels"][0])