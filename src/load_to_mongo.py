"""Step 3 of the pipeline: load the clean jobs into MongoDB, add indexes, run analytics."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient, TEXT, UpdateOne

CLEAN_FILE = Path("data/processed/jobs_clean.json")


def get_collection():
    load_dotenv()
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("DB_NAME", "hk_jobs")]
    return db["jobs"]


def to_datetime(value):
    """Turn ISO date strings from the JSON file into real dates MongoDB can sort and filter."""
    return datetime.fromisoformat(value) if value else None


def load_jobs(collection):
    jobs = json.loads(CLEAN_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)

    operations = []
    for job in jobs:
        job["published_date"] = to_datetime(job.get("published_date"))
        job["closing_date"] = to_datetime(job.get("closing_date"))
        job["last_seen"] = now
        # Upsert: update the job if job_id already exists, otherwise insert it.
        # Re-running the pipeline therefore never creates duplicates.
        operations.append(
            UpdateOne(
                {"job_id": job["job_id"]},
                {"$set": job, "$setOnInsert": {"first_seen": now}},
                upsert=True,
            )
        )

    result = collection.bulk_write(operations)
    print(f"✅ Upserted into MongoDB: {result.upserted_count} new, "
          f"{result.modified_count} updated, {collection.count_documents({})} total")


def create_indexes(collection):
    """Indexes make the queries the dashboard runs fast instead of scanning every document."""
    collection.create_index([("job_id", ASCENDING)], unique=True)
    collection.create_index([("department", ASCENDING)])
    collection.create_index([("pay_basis", ASCENDING), ("min_pay", DESCENDING)])
    collection.create_index([("published_date", DESCENDING)])
    collection.create_index([("job_title", TEXT), ("duties", TEXT)])  # keyword search
    print("✅ Indexes:", [ix["name"] for ix in collection.list_indexes()])


def run_analytics(collection):
    """Aggregation pipelines: the analysis happens inside the database."""
    print("\n=== Top 5 hiring departments ===")
    for row in collection.aggregate([
        {"$group": {"_id": "$department", "jobs": {"$sum": 1}}},
        {"$sort": {"jobs": -1}},
        {"$limit": 5},
    ]):
        print(f"  {row['jobs']:>3}  {row['_id']}")

    print("\n=== Average starting monthly pay by department (HK$) ===")
    for row in collection.aggregate([
        {"$match": {"pay_basis": "monthly"}},
        {"$group": {"_id": "$department", "avg_pay": {"$avg": "$min_pay"}, "jobs": {"$sum": 1}}},
        {"$sort": {"avg_pay": -1}},
        {"$limit": 5},
    ]):
        print(f"  {row['avg_pay']:>10,.0f}  {row['_id']} ({row['jobs']} jobs)")

    print("\n=== Most requested skills ===")
    for row in collection.aggregate([
        {"$unwind": "$skills"},
        {"$group": {"_id": "$skills", "jobs": {"$sum": 1}}},
        {"$sort": {"jobs": -1}},
    ]):
        print(f"  {row['jobs']:>3}  {row['_id']}")


def main():
    collection = get_collection()
    load_jobs(collection)
    create_indexes(collection)
    run_analytics(collection)


if __name__ == "__main__":
    main()