"""Run the full pipeline: scrape -> clean -> load into MongoDB."""
from src import cleaner, load_to_mongo, scraper

if __name__ == "__main__":
    print("1/3 Scraping...");         scraper.main()
    print("\n2/3 Cleaning...");       cleaner.main()
    print("\n3/3 Loading to MongoDB..."); load_to_mongo.main()
    print("\n✅ Pipeline complete. Start the dashboard with: streamlit run app.py")