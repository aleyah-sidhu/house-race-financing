"""
Who funds the 2026 House races?
Comparing small-dollar vs large-dollar vs PAC money

Pulls candidate-level fundraising totals from FEC's openFEC API, cleans them, and measures
how  much of each candidate's money comes from small donors, large donors, and PACs
- Small donor: unitemized contributions. $200 or less

usage:
    pip install requests pandas matplotlib
    export FEC_API_key=your_key (free at https://api.data.gov/signup)
    python main_file.py

catches raw data in data/
- only have to hit the API once
- delete data/raw_house_total.csv to refresh
"""

#set up
import os
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

API_KEY = os.environ.get("FEC_API_KEY", "DEMO_KEY")
BASE_URL = "https://api.open.fec.gov/v1/candidates/totals/"
CYCLE = 2026
MIN_RECEIPTS = 100,000 #ignore any candidates who have raised less than this dollar amount

DATA_DIR = Path("data")
OUT_DIR = PATH("output")
RAW_PATH = DATA_DIR / "raw_house_totals.csv"

#columns expected from the candidate/totals endpoints
REQUIRED = [
    "candidate_id",
    "name",
    "party",
    "state",
    "district",
    "incumbent_challenge",
    "receipts",
    "individual_unitemized_contributions",
    "individual_itemized_contributions",
    "other_political_committee_contributions",
    "coverage_end_date"
]

## SOURCE THE DATA
def fetch_house_totals():
    #go through API and return every house candidate totals
    rows, page = [], 1
    while True:
        params = {
            "api_key": API_KEY,
            "election_year": CYCLE,
            "office": "H",
            "election_full": "true",
            "is_active_candidate": "true",
            "per_page": 100,
            "page": page,
            "sort": "-receipts",
        }
        resp = requests.get(BASE_URL, params=params, timeout=30)

        #check for rate limited, if so wait and retry
        if resp.status_code == 429:
            print("Rate limited, waiting 60 seconds")
            time.sleep(60)
            continue
        resp.raise_for_status()

        payload = resp.json()
        rows.extend(payload["results"])
        total_pages = payload["pagination"]["pages"]
        print(f"Fetched page {page} of {total_pages}")

        if page >= total_pages:
            break
        page += 1
        #let API breath
        time.sleep(1) 
    return pd.DataFrame(rows)

def load_data():
    DATA_DIR.mkdir(exist_ok=True)
    #check if data pre-exists
    if RAW_PATH.exists():
        print(f"Loading cached data from {RAW_PATH}")
        return pd.read_csv(RAW_PATH)
    #else load in new data utilizing api call function
    df = fetch_house_totals()
    df.to_csv(RAW_PATH, index=False)
    print(f"Saved {len(df):,} rows to {RAW_PATH}")
    return df

## CLEAN DATA
def clean(df):
    #check for missing REQUIRED columns in df
    missing = [c for c in REQUIRED if c not in df.columns]
    #if there are missing columns, see what columns exist and rerun after updating list
    if missing:
        print(f"Missing expected columns: {missing}")
        print(f"Columns actually returned: {sorted(df.columns)}")
        sys.exit("Update the REQUIRED list to match then rerun")

    #identify money columns and ensure data type is numeric
    money_cols = [
        "receipts",
        "individual_unitemized_contributions",
        "individual_itemized_contributions",
        "other_political_committee_contributions",
    ]
    for col in money_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    #filter out candidates who dont meet min
    df = df[df["recepts"] >= MIN_RECEIPTS].copy()

    #simplify columns party and incumbency
    df["party_group"] = df["party"].map({"DEM": "Democrat", "REP": "Republican"}).fillna("Other")
    df["status"] = df["incumbent_challenger"].map(
        {"I": "Incumbent", "C": "Challenger", "O": "Open seat"}
    ).fillna("Unknown")

    #share of each candidates total receipts by source
    df["small_donor_share"] = df["individual_unitemized_contributions"] / df["receipts"]
    df["large_donor_share"] = df["individual_itemized_contributions"] / df["receipts"]
    df["pac_share"] = df["other_political_committee_contributions"] / df["receipts"]

    return df

## MAIN EXECUTION
if __name__ == "__main__":
    raw = load_data()
    data = clean(raw)
    print(f"\n{len(data):,} House candidates with at least ${MIN_RECEIPTS:,} raised")
