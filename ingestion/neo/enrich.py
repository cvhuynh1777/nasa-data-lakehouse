import pandas as pd
from pathlib import Path
from datetime import datetime

SILVER_PATH = Path("storage/silver/neo")
GOLD_PATH = Path("storage/gold/neo")


def classify_size(diameter_km: float) -> str:
    if diameter_km < 0.025:   return "tiny"
    elif diameter_km < 0.140: return "small"
    elif diameter_km < 1.0:   return "medium"
    elif diameter_km < 5.0:   return "large"
    else:                     return "major"


def is_named(name: str) -> bool:
    return not name.strip().startswith("(")


def compute_hazard_score(df: pd.DataFrame) -> pd.Series:
    prox = 1 - (df["miss_distance_lunar"] / df["miss_distance_lunar"].max())
    vel  = df["velocity_km_per_s"]         / df["velocity_km_per_s"].max()
    size = df["diameter_km_avg"]           / df["diameter_km_avg"].max()
    return ((prox * 0.40) + (vel * 0.30) + (size * 0.30)).round(4)


def hazard_label(score: float) -> str:
    if score >= 0.50:   return "critical"
    elif score >= 0.35: return "high"
    elif score >= 0.20: return "moderate"
    else:               return "low"


def compute_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    df["miss_distance_percentile"] = df["miss_distance_lunar"].rank(pct=True).mul(100).round(1)
    df["velocity_percentile"]      = df["velocity_km_per_s"].rank(pct=True).mul(100).round(1)
    df["size_percentile"]          = df["diameter_km_avg"].rank(pct=True).mul(100).round(1)
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["size_class"]     = df["diameter_km_avg"].apply(classify_size)
    df["is_named"]       = df["name"].apply(is_named)
    df["hazard_score"]   = compute_hazard_score(df)
    df["hazard_label"]   = df["hazard_score"].apply(hazard_label)
    df["critical_alert"] = df["is_potentially_hazardous"] & df["is_sentry_object"]
    df = compute_percentiles(df)

    cols = [
        "hash_id", "id", "name", "date", "nasa_jpl_url",
        "absolute_magnitude_h",
        "is_potentially_hazardous", "is_sentry_object", "critical_alert",
        "hazard_score", "hazard_label",
        "size_class", "is_named",
        "diameter_km_avg", "size_percentile",
        "miss_distance_lunar", "miss_distance_percentile",
        "velocity_km_per_s", "velocity_percentile",
        "close_approach_date", "close_approach_datetime",
    ]
    return df[cols]


def save_to_gold(df: pd.DataFrame, name: str) -> Path:
    GOLD_PATH.mkdir(parents=True, exist_ok=True)
    filepath = GOLD_PATH / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved → {filepath}")
    return filepath


if __name__ == "__main__":
    files = sorted(SILVER_PATH.glob("neo_*.parquet"))
    if not files:
        print("No silver files found. Run transform.py first.")
        exit()

    latest = files[-1]
    print(f"Reading: {latest}")
    df_silver = pd.read_parquet(latest)
    print(f"Silver shape: {df_silver.shape}")

    print("Enriching...")
    df_gold = enrich(df_silver)
    print(f"Gold shape: {df_gold.shape}")

    print(f"\nHazard labels:\n{df_gold['hazard_label'].value_counts()}")
    print(f"\nSize classes:\n{df_gold['size_class'].value_counts()}")
    print(f"\nCritical alerts: {df_gold['critical_alert'].sum()}")

    save_to_gold(df_gold, "neo")
    print("\nDone!")