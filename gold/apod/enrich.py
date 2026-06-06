import pandas as pd
import pyarrow as pa
from pathlib import Path
from datetime import datetime
from deltalake.writer import write_deltalake
from deltalake import DeltaTable

SILVER_PATH = Path("storage/silver/apod")
GOLD_PATH   = Path("storage/gold/apod")
DELTA_PATH  = Path("storage/delta/apod")


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Silver → gold enrichment for APOD."""
    df = df.copy()

    df['word_count'] = df['explanation'].str.split().str.len()
    df['has_image']  = df['media_type'] == 'image'
    df['year']       = df['date'].dt.year
    df['month']      = df['date'].dt.month

    # filter thin content
    df = df[df['word_count'] >= 50]

    # combine title + explanation for richer RAG embedding
    df['rag_text'] = df['title'] + '. ' + df['explanation']

    cols = [
        'hash_id', 'date', 'year', 'month',
        'title', 'explanation', 'rag_text',
        'media_type', 'has_image',
        'word_count', 'url', 'hdurl', 'copyright'
    ]
    return df[cols]


def save_to_gold(df: pd.DataFrame) -> None:
    """Save to both Parquet (for DuckDB) and Delta Lake (for versioning)."""
    # plain parquet — DuckDB reads this
    GOLD_PATH.mkdir(parents=True, exist_ok=True)
    filepath = GOLD_PATH / f"apod_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(filepath, index=False)
    print(f"  parquet → {filepath}")

    # delta lake — versioned, ACID
    DELTA_PATH.mkdir(parents=True, exist_ok=True)
    arrow_table = pa.Table.from_pandas(df)
    write_deltalake(str(DELTA_PATH), arrow_table, mode="overwrite")
    dt = DeltaTable(str(DELTA_PATH))
    print(f"  delta  → {DELTA_PATH} (version {dt.version()})")


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

    save_to_gold(df_gold)
    print("\nDone!")