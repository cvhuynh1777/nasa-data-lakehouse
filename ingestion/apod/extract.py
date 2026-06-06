import requests
import pandas as pd
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import osA

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY")
BASE_URL = "https://api.nasa.gov"
BRONZE_PATH = Path("storage/bronze/apod")


def fetch_apod(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch APOD entries for a date range and store raw."""
    response = requests.get(
        f"{BASE_URL}/planetary/apod",
        params={
            "start_date": start_date,
            "end_date": end_date,
            "api_key": NASA_API_KEY
        }
    )
    response.raise_for_status()
    entries = response.json()

    records = []
    for entry in entries:
        records.append({
            "hash_id": hashlib.md5(entry["date"].encode()).hexdigest(),
            "date": entry["date"],
            "raw": json.dumps(entry),
        })

    return pd.DataFrame(records)


def save_to_bronze(df: pd.DataFrame, name: str) -> Path:
    """Save dataframe to bronze layer."""
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
            df = fetch_apod(
                current.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d")
            )
            all_dfs.append(df)
            chunk += 1
            print(f"chunk {chunk} — {len(df)} entries")

            if chunk % 50 == 0:
                checkpoint = pd.concat(all_dfs, ignore_index=True)
                save_to_bronze(checkpoint, f"apod_checkpoint_{chunk}")

        except Exception as e:
            print(f"  error: {e}, skipping...")

        current = chunk_end + timedelta(days=1)
        time.sleep(0.3)

    full_df = pd.concat(all_dfs, ignore_index=True)
    full_df = full_df.drop_duplicates(subset="hash_id", keep="first")
    print(f"\nTotal: {len(full_df)} entries")
    save_to_bronze(full_df, "apod_5yr")
    print("Done!")