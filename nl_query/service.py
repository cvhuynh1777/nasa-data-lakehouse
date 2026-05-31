"""
Natural language query service.
Uses Claude to translate natural language questions into DuckDB SQL,
runs the query against the gold lakehouse, and returns both the SQL and results.

Note: this is text-to-SQL, not RAG. RAG (with embeddings + vector search)
will be added when APOD text data is ingested.
"""

import duckdb
import anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

GOLD_PATH = str(Path("storage/gold/neo") / "neo_*.parquet")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SCHEMA = """
Table: neo (read from parquet files)

Columns:
- name (string) — asteroid designation e.g. '(2018 YC2)' or '433 Eros'
- date (date) — date of close approach
- hazard_score (float) — composite risk score 0-1
- hazard_label (string) — 'low', 'moderate', 'high', 'critical'
- size_class (string) — 'tiny', 'small', 'medium', 'large', 'major'
- is_potentially_hazardous (bool) — NASA hazard flag
- is_sentry_object (bool) — on NASA impact watch list
- critical_alert (bool) — both hazardous AND sentry (very rare)
- miss_distance_lunar (float) — distance in lunar distances (1 LD = 384,400 km)
- velocity_km_per_s (float) — speed relative to Earth
- absolute_magnitude_h (float) — brightness, lower = bigger
- diameter_km_avg (float) — estimated diameter in km
- miss_distance_percentile (float) — how close vs 5yr history
- velocity_percentile (float) — how fast vs 5yr history
- size_percentile (float) — how large vs 5yr history
- nasa_jpl_url (string) — link to NASA database entry
- close_approach_date (date) — exact date of closest approach
- close_approach_datetime (datetime) — exact time of closest approach

Date range: 2021-05-31 to 2026-05-30
"""

SYSTEM_PROMPT = f"""You are a NASA data lakehouse assistant. You translate natural 
language questions into DuckDB SQL queries against a NEO (Near Earth Object) dataset.

{SCHEMA}

Rules:
- Always use read_parquet('{GOLD_PATH}') as the table source
- Return ONLY the SQL query, no explanation, no markdown, no backticks
- Use DATE literals like DATE '2026-01-01'
- For relative dates use: DATE '2026-05-30' - INTERVAL N DAYS
- Always include a LIMIT (default 10, max 50)
- Order results meaningfully (closest first, highest score first, etc.)
- For "recent" or "last few days" use the last 7 days from DATE '2026-05-30'
"""


def generate_sql(question: str) -> str:
    """Use Claude to translate a natural language question into SQL."""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}]
    )
    return message.content[0].text.strip()


def run_query(sql: str) -> list:
    """Run a SQL query against the gold parquet files."""
    con = duckdb.connect()
    df = con.execute(sql).df()
    return df.to_dict(orient="records")


def ask(question: str) -> dict:
    """Full RAG pipeline: question → SQL → results."""
    sql = generate_sql(question)
    try:
        results = run_query(sql)
        return {
            "question": question,
            "sql": sql,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {
            "question": question,
            "sql": sql,
            "error": str(e),
            "results": []
        }


if __name__ == "__main__":
    questions = [
        "what asteroids came closest to Earth this week?",
        "show me all critical hazard objects in 2024",
        "which sentry objects passed closest?",
        "how many hazardous asteroids were there each year?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        result = ask(q)
        print(f"SQL: {result['sql']}")
        print(f"Results: {result['count']} records")
        if result["results"]:
            print(result["results"][0])