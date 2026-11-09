"""Step 2 of the pipeline: clean the raw government job data with Pandas + NumPy.

Input : newest data/raw/gov_jobs_*.json
Output: data/processed/jobs_clean.csv  (for analysis / Excel)
        data/processed/jobs_clean.json (records ready to load into MongoDB)
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")

# Fields we keep, and the clearer names we give them
RENAME = {
    "jobid": "job_id",
    "jobname": "job_title",
    "deptnamejve": "department",
    "division": "division",
    "academic": "qualifications",
    "entrypay": "pay_text",
    "minpaym": "min_pay_monthly",
    "minpayh": "min_pay_hourly",
    "minpayd": "min_pay_daily",
    "expfrom": "exp_years_min",
    "expto": "exp_years_max",
    "iscs": "is_civil_service",
    "pubdate": "published_date",
    "enddate": "closing_date",
    "duties": "duties",
    "entreq": "entry_requirements",
    "onlineformurl": "apply_url",
    "depturl": "department_url",
}

# Rough ranking of qualification levels, used to find each job's highest requirement
QUAL_RANK = {
    "Degree": 4,
    "Professional Qualification": 4,
    "Teacher Certificate": 3,
    "Higher Diploma": 3,
    "Associate Degree": 3,
    "Diploma": 2,
    "HKDSEE results": 1,
    "HKCEE results": 1,
}

SKILL_KEYWORDS = {
    "Python": r"\bpython\b",
    "SQL": r"\bsql\b",
    "Excel": r"\bexcel\b",
    "Data analysis": r"data analy",
    "Statistics": r"statistic",
    "Project management": r"project management",
    "Chinese (Putonghua)": r"putonghua",
    "English": r"\benglish\b",
    "Driving licence": r"driving licen[cs]e",
    "Computer skills": r"computer",
}


def load_raw():
    """Read the newest raw file and flatten every group's 'vacancies' list into one table."""
    latest = sorted(RAW_DIR.glob("gov_jobs_*.json"))[-1]
    data = json.loads(latest.read_text(encoding="utf-8"))
    rows = []
    for group_no, group in enumerate(data["common"]):
        for job in group.get("vacancies", []):
            rows.append({**job, "source_group": group_no})
    print(f"Loaded {len(rows)} raw rows from {latest.name}")
    return pd.DataFrame(rows)


def clean_text(value):
    """Collapse tabs, line breaks and repeated spaces into single spaces."""
    if not isinstance(value, str):
        return value
    value = re.sub(r"\s+", " ", value).strip()
    return value if value not in ("", "-") else np.nan


def max_pay_from_text(text):
    """Pull the highest $ figure out of free text, e.g. 'HK$72,430 - HK$103,810' -> 103810."""
    if not isinstance(text, str):
        return np.nan
    numbers = re.findall(r"\$\s?([\d,]+(?:\.\d+)?)", text)
    values = [float(n.replace(",", "")) for n in numbers if n.replace(",", "")]
    return max(values) if values else np.nan


def highest_qualification(quals):
    if not isinstance(quals, list) or not quals:
        return np.nan
    return max(quals, key=lambda q: QUAL_RANK.get(q, 0))


def find_skills(text):
    if not isinstance(text, str):
        return []
    text = text.lower()
    return [skill for skill, pattern in SKILL_KEYWORDS.items() if re.search(pattern, text)]


def clean(df):
    report = {"raw_rows": len(df)}

    # 1. Keep useful columns and rename them
    df = df[[c for c in RENAME if c in df.columns] + ["source_group"]].rename(columns=RENAME)

    # 2. Deduplicate: the same job can appear in more than one group
    df = df.drop_duplicates(subset="job_id", keep="first")
    report["duplicates_removed"] = report["raw_rows"] - len(df)

    # 3. Tidy free text (line breaks, tabs, extra spaces; '' and '-' become missing)
    text_cols = ["job_title", "department", "division", "pay_text", "duties",
                 "entry_requirements", "apply_url", "department_url"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].map(clean_text)

    # 4. Pay: work out pay basis and convert to numbers
    for col in ["min_pay_monthly", "min_pay_hourly", "min_pay_daily"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["pay_basis"] = np.select(
        [df["min_pay_monthly"].notna(), df["min_pay_hourly"].notna(), df["min_pay_daily"].notna()],
        ["monthly", "hourly", "daily"],
        default="unknown",
    )
    df["min_pay"] = df["min_pay_monthly"].fillna(df["min_pay_hourly"]).fillna(df["min_pay_daily"])
    df["max_pay"] = df["pay_text"].map(max_pay_from_text)
    # If the text has no higher figure (or a smaller one from another pay basis), max = min
    df["max_pay"] = np.where(df["max_pay"] >= df["min_pay"], df["max_pay"], df["min_pay"])

    # 5. Dates: '2099-12-31' is a placeholder meaning "no closing date"
    df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
    df["closing_date"] = pd.to_datetime(df["closing_date"], errors="coerce")
    df["open_until_filled"] = df["closing_date"].dt.year >= 2099
    df.loc[df["open_until_filled"], "closing_date"] = pd.NaT
    df["days_since_posted"] = (pd.Timestamp.today().normalize() - df["published_date"]).dt.days

    # 6. Flags and numbers
    df["is_civil_service"] = df["is_civil_service"].eq("Y")
    df["exp_years_min"] = pd.to_numeric(df["exp_years_min"], errors="coerce")
    df["exp_years_max"] = pd.to_numeric(df["exp_years_max"], errors="coerce")

    # 7. Derived insight columns
    df["qualifications"] = df["qualifications"].map(lambda q: q if isinstance(q, list) else [])
    df["highest_qualification"] = df["qualifications"].map(highest_qualification)
    df["skills"] = (df["entry_requirements"].fillna("") + " " + df["duties"].fillna("")).map(find_skills)

    # 8. Data-quality report
    report["clean_rows"] = len(df)
    report["missing_values"] = {
        c: int(n) for c, n in df[["min_pay", "max_pay", "published_date", "department"]]
        .isna().sum().items()
    }
    return df.reset_index(drop=True), report


def save(df):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "jobs_clean.csv", index=False)
    # JSON for MongoDB: dates as ISO strings, missing values as null
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    (OUT_DIR / "jobs_clean.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    df, report = clean(load_raw())
    save(df)
    print("\n=== Data-quality report ===")
    print(json.dumps(report, indent=2))
    print("\n=== Preview ===")
    print(df[["job_id", "job_title", "department", "pay_basis", "min_pay", "max_pay",
              "highest_qualification", "open_until_filled"]].head(10).to_string())
    print(f"\n✅ Saved {len(df)} clean jobs to {OUT_DIR}/")


if __name__ == "__main__":
    main()