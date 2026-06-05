import pandas as pd
from pathlib import Path
from datetime import datetime

SILVER_PATH = Path("storage/silver/apod")
GOLD_PATH = Path("storage/gold/apod")


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Silver → gold enrichment for APOD."""
    df = df.copy()

    # derived columns
    df['word_count'] = df['explanation'].str.split().str.len()
    df['has_image']  = df['media_type'] == 'image'
    df['year']       = df['date'].dt.year
    df['month']      = df['date'].dt.month

    # filter thin content
    df = df[df['word_count'] >= 50]

    # combine title + explanation for richer RAG embedding
    df['rag_text'] = df['title'] + '. ' + df['explanation']

    # clean column order
    cols = [
        'hash_id', 'date', 'year', 'month',
        'title', 'explanation', 'rag_text',
        'media_type', 'has_image',
        'word_count', 'url', 'hdurl', 'copyright'
    ]
    return df[cols]


def save_to_gold(df: pd.DataFrame, name: str) -> Path:
    GOLD_PATH.mkdir(parents=True, exist_ok=True)
    filepath = GOLD_PATH / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  saved → {filepath}")
    return filepath


if __name__ == "__main__":
    files = sorted(SILVER_PATH.glob("apod_*.parquet"))
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
    print(f"\nWord count stats:\n{df_gold['word_count'].describe().round(1)}")
    print(f"\nMedia types:\n{df_gold['media_type'].value_counts()}")
    print(f"\nEntries per year:\n{df_gold['year'].value_counts().sort_index()}")

    save_to_gold(df_gold, "apod")
    print("\nDone!")