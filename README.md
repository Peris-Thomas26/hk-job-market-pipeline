# 🇭🇰 HK Government Job Market Pipeline

An end-to-end data pipeline that collects live Hong Kong Government job vacancies, cleans and enriches them with Pandas, stores them in MongoDB, and presents insights in an interactive Streamlit dashboard.


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
- **Text normalisation:** tabs, line breaks, empty strings, and `"-"` are cleaned to proper missing values.
- **Feature engineering:** highest qualification required, skills mentioned (Excel, SQL, Putonghua…), days since posted.

## MongoDB design
- **Upserts** on `job_id`: re-running the pipeline updates existing jobs instead of duplicating them; `first_seen` / `last_seen` track each vacancy's lifetime.
- **Indexes:** unique `job_id`; `department`; compound `(pay_basis, min_pay)` for pay-ranked queries; `published_date`; text index on title + duties for keyword search.
- **Aggregation pipelines** (`$match`, `$group`, `$unwind`, `$sort`) compute analytics inside the database.


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
- [ ] Scheduled daily runs (GitHub Actions/cron) to build a history of vacancies over time
- [ ] Additional private-sector sources with **Scrapy** (scale) and **Selenium** (JavaScript-rendered pages)
- [ ] **FastAPI** endpoint so other systems can query the data
- [ ] **Docker** packaging and cloud deployment (MongoDB Atlas + Streamlit Community Cloud)
- [ ] Unit tests for the cleaning functions (pytest)

## Tech stack
Python · Requests · Pandas · NumPy · MongoDB · PyMongo · Streamlit · Plotly
