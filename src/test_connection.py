import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()                      # loads MONGO_URI from the .env file
uri = os.getenv("MONGO_URI")       # the password stays in .env, never in code

client = MongoClient(uri)
try:
    client.admin.command("ping")
    print("Connected successfully")
    client.close()
except Exception as e:
    raise Exception("The following error occurred: ", e)