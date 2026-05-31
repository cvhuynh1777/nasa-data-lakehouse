import pandas as pd
from pathlib import Path
from datetime import datetime

BRONZE_PATH = Path("storage/bronze")
SILVER_PATH = Path("storage/silver")


def clean_neo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw NEO bronze data into clean silver data.
    - fix data types
    - rename confusing columns
    - add derived columns
    """
    df = df.copy()

    # fix types
    df["id"] = df["id"].astype(str)
    df["date"] = pd.to_datetime(df["date"])
    df["close_approach_datetime"] = pd.to_datetime(df["close_approach_datetime"], format="%Y-%b-%d %H:%M")

    # add a derived column — diameter midpoint estimate
    df["estimated_diameter_km_avg"] = (
        df["estimated_diameter_km_min"] + df["estimated_diameter_km_max"]
    ) / 2

    # add miss distance in lunar units (1 lunar distance = 384,400 km)
    df["miss_distance_lunar"] = df["miss_distance_km"] / 384400

    # rename for clarity
    df = df.rename(columns={
        "relative_velocity_km_per_s": "velocity_km_per_s",
    })

    print(f"  cleaned dataframe: {df.shape[0]} rows, {df.shape[1]} columns")
    return df


def save_to_silver(df: pd.DataFrame, dataset_name: str) -> Path:
    """Save cleaned dataframe to silver layer."""
    SILVER_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = SILVER_PATH / f"{dataset_name}_{timestamp}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved to {filepath}")
    return filepath


if __name__ == "__main__":
    # find latest bronze NEO file
    files = sorted(BRONZE_PATH.glob("neo_*.parquet"))
    if not files:
        print("No bronze NEO files found. Run nasa_api.py first.")
        exit()

    latest = files[-1]
    print(f"Reading: {latest}")
    df_bronze = pd.read_parquet(latest)

    df_silver = clean_neo(df_bronze)
    print("\nSample silver data:")
    print(df_silver[["name", "date", "miss_distance_lunar", "estimated_diameter_km_avg", "is_potentially_hazardous"]].head())

    save_to_silver(df_silver, "neo")