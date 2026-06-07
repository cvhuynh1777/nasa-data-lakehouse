"""
Data catalog — describes every dataset in the lakehouse.
Auto-updates after each pipeline run.
"""

import json
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

CATALOG_PATH = Path("catalog/catalog.json")
GOLD_NEO     = str(Path("storage/gold/neo") / "neo_*.parquet")
GOLD_APOD    = str(Path("storage/gold/apod") / "apod_*.parquet")


def build_neo_entry() -> dict:
    con = duckdb.connect()
    stats = con.execute(f"""
        SELECT
            COUNT(*)                          AS total_records,
            MIN(date)::DATE                   AS date_from,
            MAX(date)::DATE                   AS date_to,
            SUM(is_potentially_hazardous)     AS hazardous_count,
            SUM(is_sentry_object)             AS sentry_count,
            SUM(critical_alert)               AS critical_alerts,
            ROUND(AVG(hazard_score), 4)       AS avg_hazard_score
        FROM read_parquet('{GOLD_NEO}')
    """).df().to_dict(orient="records")[0]

    return {
        "name": "neo",
        "description": "NASA Near Earth Object asteroid close approaches",
        "source": "https://api.nasa.gov/neo/rest/v1/feed",
        "coverage": "2021-2026",
        "last_updated": datetime.now().isoformat(),
        "layers": {
            "bronze": {
                "path": "storage/bronze/neo/",
                "description": "Raw JSON from NASA API",
                "fields": ["hash_id", "id", "name", "date", "raw"]
            },
            "silver": {
                "path": "storage/silver/neo/",
                "description": "Cleaned and typed fields",
                "fields": ["hash_id", "id", "name", "date", "absolute_magnitude_h",
                          "diameter_km_avg", "is_potentially_hazardous", "is_sentry_object",
                          "velocity_km_per_s", "miss_distance_lunar", "nasa_jpl_url"]
            },
            "gold": {
                "path": "storage/gold/neo/",
                "delta": "storage/delta/neo/",
                "description": "Enriched with risk scoring and percentiles",
                "fields": ["hazard_score", "hazard_label", "size_class", "is_named",
                          "critical_alert", "miss_distance_percentile",
                          "velocity_percentile", "size_percentile"]
            }
        },
        "stats": stats,
        "key_finding": "is_potentially_hazardous and is_sentry_object never overlap in 5 years of data"
    }


def build_apod_entry() -> dict:
    con = duckdb.connect()
    stats = con.execute(f"""
        SELECT
            COUNT(*)              AS total_records,
            MIN(date)::DATE       AS date_from,
            MAX(date)::DATE       AS date_to,
            SUM(has_image)        AS image_count,
            ROUND(AVG(word_count), 1) AS avg_word_count
        FROM read_parquet('{GOLD_APOD}')
    """).df().to_dict(orient="records")[0]

    return {
        "name": "apod",
        "description": "NASA Astronomy Picture of the Day with explanations",
        "source": "https://api.nasa.gov/planetary/apod",
        "coverage": "2021-2026",
        "last_updated": datetime.now().isoformat(),
        "layers": {
            "bronze": {
                "path": "storage/bronze/apod/",
                "description": "Raw JSON from NASA API",
                "fields": ["hash_id", "date", "raw"]
            },
            "silver": {
                "path": "storage/silver/apod/",
                "description": "Cleaned and typed fields",
                "fields": ["hash_id", "date", "title", "explanation",
                          "media_type", "url", "hdurl", "copyright"]
            },
            "gold": {
                "path": "storage/gold/apod/",
                "delta": "storage/delta/apod/",
                "description": "Enriched for RAG with rag_text and metadata",
                "fields": ["rag_text", "word_count", "has_image", "year", "month"]
            }
        },
        "rag": {
            "embedding_model": "all-MiniLM-L6-v2",
            "vector_store": "Chroma",
            "vector_path": "storage/chroma/",
            "indexed_field": "rag_text"
        },
        "stats": stats
    }


def build_catalog() -> dict:
    return {
        "name": "NASA Data Lakehouse",
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "datasets": [
            build_neo_entry(),
            build_apod_entry()
        ]
    }


def save_catalog(catalog: dict) -> Path:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2, default=str)
    print(f"  saved → {CATALOG_PATH}")
    return CATALOG_PATH


if __name__ == "__main__":
    print("Building catalog...")
    catalog = build_catalog()
    save_catalog(catalog)
    print(f"\nDatasets: {[d['name'] for d in catalog['datasets']]}")
    print("Done!")