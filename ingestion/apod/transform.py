import pandas as pd
import json
from pathlib import Path
from datetime import datetime

BRONZE_PATH = Path("storage/bronze/apod")
SILVER_PATH = Path("storage/silver/apod")


def unpack_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Unpack raw JSON into flat columns."""
    records = []
    for _, row in df.iterrows():
        obj = json.loads(row["raw"])
        records.append({
            "hash_id":      row["hash_id"],
            "date":         obj["date"],
            "title":        obj["title"],
            "explanation":  obj["explanation"],
            "media_type":   obj["media_type"],
            "url":          obj.get("url", None),
            "hdurl":        obj.get("hdurl", None),
            "copyright":    obj.get("copyright", None),
        })
    return pd.DataFrame(records)


def fix_types(df: pd.DataFrame) -> pd.DataFrame:
    """Fix data types."""
    df["date"] = pd.to_datetime(df["date"])
    return df


def transform(df_bronze: pd.DataFrame) -> pd.DataFrame:
    """Full bronze → silver transformation."""
    df = unpack_raw(df_bronze)
    df = fix_types(df)
    df = df.drop_duplicates(subset="hash_id", keep="first")
    return df


def save_to_silver(df: pd.DataFrame, name: str) -> Path:
    """Save dataframe to silver layer."""
    SILVER_PATH.mkdir(parents=True, exist_ok=True)
    filepath = SILVER_PATH / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved → {filepath}")
    return filepath


if __name__ == "__main__":
    files = sorted(BRONZE_PATH.glob("apod_5yr*.parquet"))
    if not files:
        print("No bronze files found. Run extract.py first.")
        exit()

    latest = files[-1]
    print(f"Reading: {latest}")
    df_bronze = pd.read_parquet(latest)
    print(f"Bronze shape: {df_bronze.shape}")

    print("Transforming...")
    df_silver = transform(df_bronze)
    print(f"Silver shape: {df_silver.shape}")
    print(f"\nSample:")
    print(df_silver[["date", "title", "media_type", "copyright"]].head())
    print(f"\nTypes:\n{df_silver.dtypes}")
    print(f"\nMedia types:\n{df_silver['media_type'].value_counts()}")
    print(f"\nMissing copyright: {df_silver['copyright'].isna().sum()}")

    save_to_silver(df_silver, "apod")
    print("\nDone!")