import pandas as pd
from pathlib import Path
from datetime import datetime

SILVER_PATH = Path("storage/silver")
GOLD_PATH = Path("storage/gold")


def classify_size(diameter_km: float) -> str:
    """
    Classify asteroid by estimated average diameter.
    Based on general planetary defense categories.
    """
    if diameter_km < 0.025:    return "tiny"        # car to house sized, burns up
    elif diameter_km < 0.140:  return "small"       # house to city block
    elif diameter_km < 1.0:    return "medium"      # city scale
    elif diameter_km < 5.0:    return "large"       # regional devastation
    else:                      return "major"       # extinction level


def is_named(name: str) -> bool:
    """
    Proper names have a number prefix followed by a real word.
    e.g. '433 Eros' or '136818 Selqet' vs '(2025 US6)'
    """
    return not name.strip().startswith("(")


def risk_label(score: float) -> str:
    if score >= 0.60:   return "critical"
    elif score >= 0.40: return "high"
    elif score >= 0.20: return "moderate"
    else:               return "low"


def compute_risk_score(df: pd.DataFrame) -> pd.Series:
    """
    Composite risk score (0-1) combining:
      - proximity  (40%) — closer = higher risk
      - velocity   (30%) — faster = higher risk
      - size       (30%) — bigger = higher risk

    Each component is normalized against the full dataset
    so scores are relative to all known passes.
    """
    prox  = 1 - (df["miss_distance_lunar"]     / df["miss_distance_lunar"].max())
    vel   = df["velocity_km_per_s"]             / df["velocity_km_per_s"].max()
    size  = df["estimated_diameter_km_avg"]     / df["estimated_diameter_km_avg"].max()

    return ((prox * 0.40) + (vel * 0.30) + (size * 0.30)).round(4)


def compute_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each pass, compute what percentile it falls in
    for distance, velocity, and size relative to all 5 years of data.
    """
    df["miss_distance_percentile"] = (
        df["miss_distance_lunar"].rank(pct=True).mul(100).round(1)
    )
    df["velocity_percentile"] = (
        df["velocity_km_per_s"].rank(pct=True).mul(100).round(1)
    )
    df["size_percentile"] = (
        df["estimated_diameter_km_avg"].rank(pct=True).mul(100).round(1)
    )
    return df


def enrich_neo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Orchestrates all gold enrichment steps.
    Input: silver dataframe
    Output: gold dataframe with 17 columns
    """
    df = df.copy()

    # enrichments
    df["size_class"]  = df["estimated_diameter_km_avg"].apply(classify_size)
    df["is_named"]    = df["name"].apply(is_named)
    df["risk_score"]  = compute_risk_score(df)
    df["risk_label"]  = df["risk_score"].apply(risk_label)
    df = compute_percentiles(df)

    # clean column order
    cols = [
        "hash_id", "id", "name", "date", "close_approach_date",
        "is_potentially_hazardous", "risk_score", "risk_label",
        "size_class", "is_named",
        "estimated_diameter_km_avg", "size_percentile",
        "miss_distance_lunar", "miss_distance_percentile",
        "velocity_km_per_s", "velocity_percentile",
        "orbiting_body",
    ]
    return df[cols]


def save_to_gold(df: pd.DataFrame, dataset_name: str) -> Path:
    GOLD_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = GOLD_PATH / f"{dataset_name}_{timestamp}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved to {filepath}")
    return filepath


if __name__ == "__main__":
    # load latest silver file
    files = sorted(SILVER_PATH.glob("neo_*.parquet"))
    if not files:
        print("No silver NEO files found. Run transform.py first.")
        exit()

    latest = files[-1]
    print(f"Reading: {latest}")
    df_silver = pd.read_parquet(latest)

    print("Enriching...")
    df_gold = enrich_neo(df_silver)

    print(f"\nShape: {df_gold.shape}")
    print(f"\nRisk distribution:\n{df_gold['risk_label'].value_counts()}")
    print(f"\nSize distribution:\n{df_gold['size_class'].value_counts()}")

    save_to_gold(df_gold, "neo")
    print("\nDone!")