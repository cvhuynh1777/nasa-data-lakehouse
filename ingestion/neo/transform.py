import pandas as pd
import json
from pathlib import Path
from datetime import datetime

BRONZE_PATH = Path("storage/bronze/neo")
SILVER_PATH = Path("storage/silver/neo")


def unpack_raw(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unpack the raw JSON column into flat columns.
    Bronze stores everything as raw JSON — silver extracts what we need.
    """
    records = []
    for _, row in df.iterrows():
        obj = json.loads(row["raw"])
        ca = obj["close_approach_data"][0]

        records.append({
            # identity
            "hash_id":          row["hash_id"],
            "id":               obj["id"],
            "name":             obj["name"],
            "date":             row["date"],
            "nasa_jpl_url":     obj["nasa_jpl_url"],

            # physical
            "absolute_magnitude_h":     obj["absolute_magnitude_h"],
            "diameter_km_min":          obj["estimated_diameter"]["kilometers"]["estimated_diameter_min"],
            "diameter_km_max":          obj["estimated_diameter"]["kilometers"]["estimated_diameter_max"],

            # risk flags
            "is_potentially_hazardous": obj["is_potentially_hazardous_asteroid"],
            "is_sentry_object":         obj["is_sentry_object"],

            # close approach
            "close_approach_date":      ca["close_approach_date"],
            "close_approach_datetime":  ca["close_approach_date_full"],

            # velocity — string from API, cast below
            "velocity_km_per_s":        ca["relative_velocity"]["kilometers_per_second"],

            # miss distance — strings from API, cast below
            "miss_distance_au":         ca["miss_distance"]["astronomical"],
            "miss_distance_lunar":      ca["miss_distance"]["lunar"],
            "miss_distance_km":         ca["miss_distance"]["kilometers"],
        })

    return pd.DataFrame(records)


def fix_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fix data types.
    NASA returns velocity and miss distance as strings — cast to float.
    """
    # dates
    df["date"] = pd.to_datetime(df["date"])
    df["close_approach_date"] = pd.to_datetime(df["close_approach_date"])
    df["close_approach_datetime"] = pd.to_datetime(df["close_approach_datetime"], format="%Y-%b-%d %H:%M")  # add this

    # strings → float
    float_cols = [
        "velocity_km_per_s",
        "miss_distance_au",
        "miss_distance_lunar",
        "miss_distance_km",
    ]
    df[float_cols] = df[float_cols].astype(float)

    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple derived columns.
    These are basic calculations from existing fields — not enrichment.
    """
    df["diameter_km_avg"] = (df["diameter_km_min"] + df["diameter_km_max"]) / 2
    return df


def transform(df_bronze: pd.DataFrame) -> pd.DataFrame:
    """
    Full bronze → silver transformation.
    Unpack raw JSON, fix types, add derived columns.
    """
    df = unpack_raw(df_bronze)
    df = fix_types(df)
    df = add_derived_columns(df)
    # deduplicate — round before comparing to catch floating point differences
    df["_miss_distance_rounded"] = df["miss_distance_lunar"].round(4)
    df["_velocity_rounded"] = df["velocity_km_per_s"].round(4)
    df = df.drop_duplicates(
        subset=["date", "_miss_distance_rounded", "_velocity_rounded"],
        keep="first"
    )
    df = df.drop(columns=["_miss_distance_rounded", "_velocity_rounded"])
    return df

def save_to_silver(df: pd.DataFrame, name: str) -> Path:
    """Save dataframe to silver layer."""
    SILVER_PATH.mkdir(parents=True, exist_ok=True)
    filepath = SILVER_PATH / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved → {filepath}")
    return filepath


if __name__ == "__main__":
    # load latest bronze file
    files = sorted(BRONZE_PATH.glob("neo_5yr*.parquet"))
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
    print(df_silver.head())
    print(f"\nTypes:\n{df_silver.dtypes}")

    save_to_silver(df_silver, "neo")
    print("\nDone!")