from fastapi import FastAPI
import duckdb
from pathlib import Path
from nl_query.service import ask

app = FastAPI(
    title="NASA Data Lakehouse",
    description="Query NASA asteroid data with SQL and semantic search",
    version="0.1.0"
)

GOLD_PATH = str(Path("storage/gold/neo") / "neo_*.parquet")

@app.get("/")
def root():
    return {"message": "NASA Data Lakehouse API", "version": "0.1.0"}

@app.get("/nl-query")
def nl_query(question: str):
    """Ask a natural language question — Claude generates SQL and queries the lakehouse."""
    return ask(question)


@app.get("/datasets")
def datasets():
    """List available datasets and their record counts."""
    con = duckdb.connect()
    result = con.execute(f"""
        SELECT
            COUNT(*)                          AS total_records,
            MIN(date)::DATE                   AS date_from,
            MAX(date)::DATE                   AS date_to,
            SUM(is_potentially_hazardous)     AS hazardous_count,
            SUM(is_sentry_object)             AS sentry_count,
            SUM(critical_alert)               AS critical_alerts
        FROM read_parquet('{GOLD_PATH}')
    """).df()

    return {
        "datasets": [
            {
                "name": "neo",
                "description": "NASA Near Earth Object close approaches",
                "source": "api.nasa.gov/neo/rest/v1/feed",
                "coverage": "2021-2026",
                "layers": ["bronze", "silver", "gold"],
                "stats": result.to_dict(orient="records")[0]
            }
        ]
    }


@app.get("/query")
def query(
    hazard_label: str = None,
    size_class: str = None,
    limit: int = 20
):
    """Query NEO gold data with optional filters."""
    con = duckdb.connect()

    filters = []
    if hazard_label:
        filters.append(f"hazard_label = '{hazard_label}'")
    if size_class:
        filters.append(f"size_class = '{size_class}'")

    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    df = con.execute(f"""
        SELECT
            name, date, hazard_score, hazard_label, size_class,
            miss_distance_lunar, velocity_km_per_s,
            is_potentially_hazardous, is_sentry_object, critical_alert,
            nasa_jpl_url
        FROM read_parquet('{GOLD_PATH}')
        {where}
        ORDER BY hazard_score DESC
        LIMIT {limit}
    """).df()

    return df.to_dict(orient="records")


@app.get("/hazardous")
def hazardous(limit: int = 20):
    """Return the highest risk asteroid passes."""
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            name, date, hazard_score, hazard_label, size_class,
            miss_distance_lunar, velocity_km_per_s,
            is_potentially_hazardous, is_sentry_object
        FROM read_parquet('{GOLD_PATH}')
        WHERE hazard_label IN ('critical', 'high')
        ORDER BY hazard_score DESC
        LIMIT {limit}
    """).df()
    return df.to_dict(orient="records")


@app.get("/sentry")
def sentry():
    """Return all objects on NASA's Sentry impact watch list."""
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            name, date, hazard_score, hazard_label, size_class,
            miss_distance_lunar, velocity_km_per_s, nasa_jpl_url
        FROM read_parquet('{GOLD_PATH}')
        WHERE is_sentry_object = true
        ORDER BY miss_distance_lunar ASC
    """).df()
    return df.to_dict(orient="records")