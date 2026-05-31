import duckdb
from pathlib import Path

SILVER_PATH = Path("storage/silver")
BRONZE_PATH = Path("storage/bronze")


def get_connection():
    """
    Returns a DuckDB connection.
    We use in-memory mode for now — fast, no setup needed.
    """
    return duckdb.connect()


def query_parquet(sql: str) -> "duckdb.DuckDBPyRelation":
    """Run a SQL query and return results as a dataframe."""
    con = get_connection()
    result = con.execute(sql).df()
    return result


if __name__ == "__main__":
    # point duckdb directly at your parquet files — no loading needed!
    silver_files = str(SILVER_PATH / "neo_*.parquet")

    con = get_connection()

    print("=== All hazardous asteroids ===")
    df = con.execute(f"""
        SELECT
            name,
            miss_distance_lunar,
            velocity_km_per_s,
            estimated_diameter_km_avg
        FROM read_parquet('{silver_files}')
        WHERE is_potentially_hazardous = true
        ORDER BY miss_distance_lunar ASC
    """).df()
    print(df)

    print("\n=== Fastest asteroids ===")
    df2 = con.execute(f"""
        SELECT
            name,
            velocity_km_per_s,
            miss_distance_lunar,
            is_potentially_hazardous
        FROM read_parquet('{silver_files}')
        ORDER BY velocity_km_per_s DESC
        LIMIT 5
    """).df()
    print(df2)

    print("\n=== Summary stats ===")
    df3 = con.execute(f"""
        SELECT
            COUNT(*)                           AS total_objects,
            SUM(is_potentially_hazardous)      AS hazardous_count,
            ROUND(AVG(velocity_km_per_s), 2)   AS avg_velocity_km_s,
            ROUND(MIN(miss_distance_lunar), 1)  AS closest_lunar_dist,
            ROUND(MAX(estimated_diameter_km_avg), 3) AS largest_diameter_km
        FROM read_parquet('{silver_files}')
    """).df()
    print(df3)