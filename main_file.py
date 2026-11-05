"""
Where does House campaign money come from in 2026?
Comparing large individual donors vs PACs vs other

Pulls candidate-level fundraising totals from FEC's openFEC API, cleans them, and measures
how  much of each candidate's money comes from large donors, PACs, and other sources
- large donors: itemized individual contributions (>$200 for the cycle)
- PACS: other political committees
- Everything else: remainder, including small non-itemized donors, party transfers, lonas, self-funding

usage:
    pip install requests pandas matplotlib
    export FEC_API_KEY=your_key (free at https://api.data.gov/signup) (bash)
    $env:FEC_API_KEY = "key" (windows)
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
MIN_RECEIPTS = 100000 #ignore any candidates who have raised less than this dollar amount

DATA_DIR = Path("data")
OUT_DIR = Path("output")
#where raw data is cached
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
    "individual_itemized_contributions",
    "other_political_committee_contributions",
    "coverage_end_date"
]

## SOURCE THE DATA
def fetch_house_totals():
    #go through API and return every house candidate totals
    #collect each candidates record in rows and start at page 1 for returning API results
    rows, page = [], 1
    #for each page
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
        resp.raise_for_status() #if request failed in non-429 way
        #convert response to a dict and add to page's candidates
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
        "individual_itemized_contributions",
        "other_political_committee_contributions",
    ]
    for col in money_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    #filter out candidates who dont meet min
    df = df[df["receipts"] >= MIN_RECEIPTS].copy()
    #simplify columns party and incumbency
    df["party_group"] = df["party"].map({"DEM": "Democrat", "REP": "Republican"}).fillna("Other")
    df["status"] = df["incumbent_challenge"].map(
        {"I": "Incumbent", "C": "Challenger", "O": "Open seat"}
    ).fillna("Unknown")
    #share of each candidates total receipts by source
    df["large_donor_share"] = df["individual_itemized_contributions"] / df["receipts"]
    df["pac_share"] = df["other_political_committee_contributions"] / df["receipts"]
    df["other_share"] = 1 - df["large_donor_share"] - df["pac_share"]
    #drop odd rows that push share outside 100%
    valid = (
        df["large_donor_share"].between(0,1)
        & df["pac_share"].between(0,1)
        & df["other_share"].between(0,1)
    )
    dropped = (-valid).sum()
    if dropped:
        print(f"Dropped {dropped} rows with shares outside 0-100%")

    return df[valid]

## ANALYZE DATA
def summarize(df):
    #group dollar-weighted shares by party and incumbency
    summary = (
        df.groupby(["party_group", "status"])
        .agg(
            candidates=("candidate_id", "count"), #num of candidates
            total_raised=("receipts", "sum"), #total dollars raised
            large_donor_dollars=("individual_itemized_contributions", "sum"),
            pac_dollars=("other_political_committee_contributions", "sum"),
            median_pac_share=("pac_share", "median"),
        )
        .reset_index()
    )
    summary["large_donor_share"] = summary["large_donor_dollars"] / summary["total_raised"]
    summary["pac_share"] = summary["pac_dollars"] / summary["total_raised"]
    summary["other_share"] = 1 - summary["large_donor_share"] - summary["pac_share"]

    return summary

## CHART OF SUMMARY: stacked horizontal bar chart
def make_chart(summary):
    OUT_DIR.mkdir(exist_ok=True)

    #define new df for plot
    plot_df = summary[
        summary["party_group"].isin(["Democrat", "Republican"])
        & summary["status"].isin(["Incumbent", "Challenger", "Open seat"])
        & (summary["candidates"] >= 5) #keep only dems and rep, and groups with 5+ candidates
    ].copy()
    #create labels for plot
    plot_df["label"] = plot_df["party_group"] + " " + plot_df["status"].str.lower()
    #sort plot df by status and party group
    plot_df = plot_df.sort_values(["status", "party_group"], ascending=[True, True])

    #plot:
    fig, ax = plt.subplots(figsize=(9,5))
    left = pd.Series(0.0, index=plot_df.index) #where next segment should start on bar
    parts = [
        ("large_donor_share", "Large individual donors", "#1f4e79"),
        ("pac_share", "PACs", "#e08e0b"),
        ("other_share", "Everything else (incl. small donors)", "#b8c4cf"),
    ]
    for col, label, color in parts:
        vals = plot_df[col] * 100 #convert to percentage
        ax.barh(plot_df["label"], vals, left=left, label=label, color=color)
        #add % label in each segment
        for y, (v, l) in enumerate(zip(vals, left)):
            if v >= 6:
                ax.text(l + v / 2, y, f"{v:.0f}%", ha="center", va="center", fontsize=9, 
                        color="white" if col != "other_share" else "black")
        left = left + vals

    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of total receipts")
    ax.set_title("Where 2026 House campaign money comes from", loc="left", fontsize=13, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)

    #footnote explaining data
    plt.figtext(
        0.01, 0.01,
        "Large donors = itemized individual contributions (over $200 per donor per cycle). "
        "'Everything else' also includes party transfers, loans, and self funding.\n"
        "Source: Federal Election Commission (openFEC); candidates with $100k+ raised.",
        fontsize=7.5, color="grey"
    )
    plt.tight_layout(rect=(0, 0.06, 1, 1))
    plt.savefig(OUT_DIR / "funding_mix.png", dpi=200)
    print(f"Saved chart to {OUT_DIR / 'funding_mix.png'}")

## MAIN EXECUTION
if __name__ == "__main__":
    raw = load_data()
    data = clean(raw)
    print(f"\n{len(data):,} House candidates with at least ${MIN_RECEIPTS:,} raised")

    print(f"Latest coverage end date in data: {data['coverage_end_date'].max()}")

    summary = summarize(data)
    OUT_DIR.mkdir(exist_ok=True)
    summary.to_csv(OUT_DIR / "summary_by_party_status.csv", index=False)

    #make printed numbers easier to read (3 decimals, wider lines)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    pd.set_option("display.width", 200)
    print("\n===Dollar-weighted funding mix by party and status ===")
    print(summary[["party_group", "status", "candidates", "total_raised", "large_donor_share", "pac_share", "other_share"]].to_string(index=False))

    cols = ["name", "party", "state", "district", "status", "receipts"]
    print("\n=== 10 candidates most reliant on PACS (min $500k raised) ===")
    big = data[data["receipts"] >= 500000]
    print(big.nlargest(10, "pac_share")[cols + ["pac_share"]].to_string(index=False))

    print("\n=== 10 candidates most reliant on large individual donors (min $500k raised) ===")
    print(big.nlargest(10, "large_donor_share")[cols + ["large_donor_share"]].to_string(index=False))

    print("\n=== 10 candidates who raised the most in total ===")
    print(data.nlargest(10, "receipts")[cols].to_string(index=False))

    make_chart(summary) 
