"""Step 1 of the pipeline: download HK government job vacancies and save the raw data."""
import json
import time
from datetime import datetime
from pathlib import Path

import requests

URL = "https://www.csb.gov.hk/datagovhk/gov-vacancies/gov-job-vacancies-en.json"
RAW_DIR = Path("data/raw")
HEADERS = {"User-Agent": "hk-job-market-pipeline/1.0 (portfolio project)"}


def fetch(url, retries=3):
    """Download JSON, retrying a few times if the network fails."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            # The government file starts with an invisible BOM character,
            # so decode with 'utf-8-sig' (which removes it) before parsing JSON.
            text = response.content.decode("utf-8-sig")
            return json.loads(text)
        except requests.RequestException as e:
            print(f"Attempt {attempt} failed: {e}")
            time.sleep(2 * attempt)
    raise RuntimeError("Could not fetch data after several attempts")


def main():
    data = fetch(URL)

    # Save the raw data exactly as received, with a timestamp in the filename
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = RAW_DIR / f"gov_jobs_{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Saved raw data to {path}")

    # Inspect the structure so we know how to clean it
    print("Top-level type:", type(data).__name__)
    if isinstance(data, dict):
        print("Top-level keys:", list(data.keys()))
    records = data if isinstance(data, list) else next(
        (v for v in data.values() if isinstance(v, list)), []
    )
    print("Number of records:", len(records))
    if records:
        print("First record:")
        print(json.dumps(records[0], ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()