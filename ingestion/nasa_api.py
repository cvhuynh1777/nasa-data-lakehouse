import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os
import json
import hashlib
import time
from datetime import datetime, timedelta

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY")
BASE_URL = "https://api.nasa.gov"
BRONZE_PATH = Path("storage/bronze")


def fetch_neo(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch NEO data and store everything raw."""
    response = requests.get(
        f"{BASE_URL}/neo/rest/v1/feed",
        params={"start_date": start_date, "end_date": end_date, "api_key": NASA_API_KEY}
    )
    response.raise_for_status()
    data = response.json()

    records = []
    for date, objects in data["near_earth_objects"].items():
        for obj in objects:
            records.append({
                "hash_id": hashlib.md5(f"{obj['id']}_{date}".encode()).hexdigest(),
                "id": obj["id"],
                "name": obj["name"],
                "date": date,
                "raw": json.dumps(obj),
            })

    return pd.DataFrame(records)


def save_to_bronze(df: pd.DataFrame, name: str) -> Path:
    """Save dataframe as parquet to bronze layer."""
    BRONZE_PATH.mkdir(parents=True, exist_ok=True)
    filepath = BRONZE_PATH / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved → {filepath}")
    return filepath


if __name__ == "__main__":
    end = datetime.today()
    start = end - timedelta(days=365 * 5)
    current = start
    all_dfs = []
    chunk = 0

    print(f"Pulling {start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}\n")

    while current < end:
        chunk_end = min(current + timedelta(days=7), end)
        try:
            df = fetch_neo(current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d"))
            all_dfs.append(df)
            chunk += 1
            print(f"chunk {chunk} — {len(df)} objects")

            if chunk % 50 == 0:
                checkpoint = pd.concat(all_dfs, ignore_index=True)
                save_to_bronze(checkpoint, f"neo_checkpoint_{chunk}")

        except Exception as e:
            print(f"  error: {e}, skipping...")

        current = chunk_end + timedelta(days=1)
        time.sleep(0.5)

    full_df = pd.concat(all_dfs, ignore_index=True)
    full_df = full_df.drop_duplicates(subset="hash_id", keep="first")
    print(f"\nTotal: {len(full_df)} objects")
    save_to_bronze(full_df, "neo_5yr")