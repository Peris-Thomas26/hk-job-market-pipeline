# 🇭🇰 HK Government Job Market Pipeline

An end-to-end data pipeline that collects live Hong Kong Government job vacancies, cleans and enriches them with Pandas, stores them in MongoDB, and presents insights in an interactive Streamlit dashboard.

![Dashboard](docs/dashboard.png)

## Architecture

```
DATA.GOV.HK (Civil Service Bureau JSON feed, updated hourly)
        │  requests (retries, timeouts, polite User-Agent)
        ▼
data/raw/  ── timestamped raw snapshots (never modified)
        │  Pandas + NumPy cleaning
        ▼
data/processed/  ── clean CSV + JSON
        │  PyMongo (bulk upserts, indexes, aggregation pipelines)
        ▼
MongoDB  ──►  Streamlit + Plotly dashboard
```

| Stage | File | What it does |
|---|---|---|
| Extract | `src/scraper.py` | Downloads the vacancy feed with retries and saves a timestamped raw copy |
| Transform | `src/cleaner.py` | Flattens nested JSON, deduplicates, parses salaries, fixes dates, extracts skills, produces a data-quality report |
| Load | `src/load_to_mongo.py` | Idempotent bulk upserts keyed on `job_id`, indexes, aggregation analytics |
| Present | `app.py` | Filterable dashboard: KPIs, hiring departments, pay distribution, skills, qualifications |

## Data cleaning highlights
- **Nested JSON → flat table:** vacancies are spread across several groups; they are flattened into one DataFrame.
- **Deduplication** on `job_id` (the same vacancy can appear in more than one group).
- **Salary parsing:** pay is split across monthly/hourly/daily fields, and the maximum only exists in free text (e.g. `"HK$72,430 - HK$103,810 depending on…"`). Regex extracts numeric `min_pay` / `max_pay` and a `pay_basis` column, so hourly and monthly pay are never mixed.
- **Placeholder dates:** `2099-12-31` means "no closing date"; it is converted to a boolean `open_until_filled` instead of a misleading date.
- **Text normalisation:** tabs, line breaks, empty strings and `"-"` are cleaned to proper missing values.
- **Feature engineering:** highest qualification required, skills mentioned (Excel, SQL, Putonghua…), days since posted.

## MongoDB design
- **Upserts** on `job_id`: re-running the pipeline updates existing jobs instead of duplicating them; `first_seen` / `last_seen` track each vacancy's lifetime.
- **Indexes:** unique `job_id`; `department`; compound `(pay_basis, min_pay)` for pay-ranked queries; `published_date`; text index on title + duties for keyword search.
- **Aggregation pipelines** (`$match`, `$group`, `$unwind`, `$sort`) compute analytics inside the database.

## Key insights (snapshot: 9 Nov 2026, 61 vacancies)
- **Department of Health is the largest hirer** (13 of 61 vacancies), followed by Development Bureau and Education Bureau (5 each).
- **English is required in 51 of 61 roles; data skills are rare.** SQL appears in 1 vacancy and data analysis in 2, which points to an opportunity to build data capability in public-sector roles.
- **Average pay needs care:** several departments have only one vacancy, so the dashboard uses the **median** and shows job counts next to averages.

## Challenges solved
- The government feed starts with a **UTF-8 BOM**, which breaks standard JSON parsing; it is decoded with `utf-8-sig`.
- Salary information was split across inconsistent fields and free text (see above).

## Run it locally
```bash
git clone https://github.com/<your-username>/hk-job-market-pipeline.git
cd hk-job-market-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set MONGO_URI (local MongoDB or Atlas)
python run_pipeline.py        # scrape → clean → load
streamlit run app.py          # open http://localhost:8501
```

## Responsible data collection
Data comes from DATA.GOV.HK open data, which is published for public reuse. The scraper identifies itself with a User-Agent, uses timeouts and backs off between retries.

## Roadmap
- [ ] Scheduled daily runs (GitHub Actions / cron) to build a history of vacancies over time
- [ ] Additional private-sector sources with **Scrapy** (scale) and **Selenium** (JavaScript-rendered pages)
- [ ] **FastAPI** endpoint so other systems can query the data
- [ ] **Docker** packaging and cloud deployment (MongoDB Atlas + Streamlit Community Cloud)
- [ ] Unit tests for the cleaning functions (pytest)

## Tech stack
Python · Requests · Pandas · NumPy · MongoDB · PyMongo · Streamlit · Plotly