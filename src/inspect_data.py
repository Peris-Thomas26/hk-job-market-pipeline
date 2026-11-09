"""Quick look at the structure of the raw data (helper, not part of the pipeline)."""
import json
from pathlib import Path

# Load the most recent raw file
latest = sorted(Path("data/raw").glob("gov_jobs_*.json"))[-1]
data = json.loads(latest.read_text(encoding="utf-8"))

for i, group in enumerate(data["common"]):
    jobs = group.get("vacancies", [])
    other = {k: str(v)[:60] for k, v in group.items() if k != "vacancies"}
    print(f"\nGroup {i}: {len(jobs)} jobs | other fields: {other}")

print("\nFields in one job (values shortened):")
first_job = data["common"][0]["vacancies"][0]
for key, value in first_job.items():
    print(f"  {key:20} {type(value).__name__:6} {str(value)[:70]!r}")