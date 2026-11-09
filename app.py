"""Step 4 of the pipeline: interactive dashboard (Streamlit + Plotly).

Run with:  streamlit run app.py
Reads from MongoDB; falls back to the cleaned CSV if the database is unreachable
(e.g. when deployed somewhere without database access).
"""
import ast
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient

st.set_page_config(page_title="HK Government Job Market", page_icon="📊", layout="wide")


@st.cache_data(ttl=600)  # cache for 10 minutes so the page doesn't query the DB on every click
def load_data():
    load_dotenv()
    fields = {"_id": 0, "job_id": 1, "job_title": 1, "department": 1, "pay_basis": 1,
              "min_pay": 1, "max_pay": 1, "highest_qualification": 1, "skills": 1,
              "published_date": 1, "open_until_filled": 1, "apply_url": 1}
    try:
        client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                             serverSelectionTimeoutMS=3000)
        jobs = list(client[os.getenv("DB_NAME", "hk_jobs")]["jobs"].find({}, fields))
        source = "MongoDB"
    except Exception:
        jobs = pd.read_csv("data/processed/jobs_clean.csv")[[k for k in fields if k != "_id"]]
        jobs["skills"] = jobs["skills"].map(ast.literal_eval)  # CSV stores lists as text
        jobs = jobs.to_dict("records")
        source = "CSV snapshot"
    df = pd.DataFrame(jobs)
    df["published_date"] = pd.to_datetime(df["published_date"])
    return df, source


df, source = load_data()

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")
departments = st.sidebar.multiselect("Department", sorted(df["department"].dropna().unique()))
pay_basis = st.sidebar.radio("Pay basis", ["monthly", "hourly", "all"], index=0)
keyword = st.sidebar.text_input("Keyword in job title", placeholder="e.g. doctor, officer")

view = df.copy()
if departments:
    view = view[view["department"].isin(departments)]
if pay_basis != "all":
    view = view[view["pay_basis"] == pay_basis]
if keyword:
    view = view[view["job_title"].str.contains(keyword, case=False, na=False)]

# ---------- Header + KPIs ----------
st.title("📊 Hong Kong Government Job Market")
st.caption(f"Source: DATA.GOV.HK – Civil Service Bureau vacancies feed · loaded from {source} · "
           f"latest posting {df['published_date'].max():%d %b %Y}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Open vacancies", len(view))
c2.metric("Hiring departments", view["department"].nunique())
monthly = view[view["pay_basis"] == "monthly"]["min_pay"]
c3.metric("Median starting pay (monthly)", f"HK${monthly.median():,.0f}" if len(monthly) else "–")
c4.metric("No closing date", f"{view['open_until_filled'].mean():.0%}" if len(view) else "–")

if view.empty:
    st.warning("No jobs match these filters.")
    st.stop()

# ---------- Charts ----------
def bar_chart(counts, title):
    """Horizontal bar chart from a value_counts() result."""
    data = counts.sort_values().rename_axis("label").reset_index(name="vacancies")
    fig = px.bar(data, x="vacancies", y="label", orientation="h", title=title,
                 labels={"vacancies": "Vacancies", "label": ""})
    return fig


left, right = st.columns(2)
left.plotly_chart(bar_chart(view["department"].value_counts().head(10), "Top hiring departments"),
                  width="stretch")
right.plotly_chart(bar_chart(view.explode("skills")["skills"].dropna().value_counts(),
                             "Skills mentioned in requirements & duties"),
                   width="stretch")

left, right = st.columns(2)
if pay_basis != "all":
    left.plotly_chart(
        px.histogram(view, x="min_pay", nbins=20, title=f"Starting pay distribution ({pay_basis}, HK$)",
                     labels={"min_pay": "Starting pay (HK$)"}),
        width="stretch",
    )
right.plotly_chart(bar_chart(view["highest_qualification"].value_counts(),
                             "Highest qualification required"),
                   width="stretch")

# ---------- Table ----------
st.subheader("Vacancies")
st.dataframe(
    view.sort_values("min_pay", ascending=False)[
        ["job_title", "department", "pay_basis", "min_pay", "max_pay", "highest_qualification",
         "published_date", "apply_url"]],
    column_config={
        "min_pay": st.column_config.NumberColumn("Min pay (HK$)", format="%.0f"),
        "max_pay": st.column_config.NumberColumn("Max pay (HK$)", format="%.0f"),
        "published_date": st.column_config.DateColumn("Published"),
        "apply_url": st.column_config.LinkColumn("Apply"),
    },
    hide_index=True,
    width="stretch",
)