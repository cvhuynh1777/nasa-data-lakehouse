# NASA Data Lakehouse

A local data lakehouse for NASA datasets with a RAG service and REST API. Built to run on a MacBook, containerizable with Podman, and deployable to Red Hat OpenShift.

---

## What it does

Pulls live NASA data, cleans and enriches it through a medallion storage architecture (bronze → silver → gold), makes it queryable with SQL, and will expose it through a REST API with semantic search via a RAG pipeline.

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11 | — |
| Environment | conda | isolated dependencies |
| Data format | Parquet | columnar, compressed, fast |
| Query engine | DuckDB | SQL directly on Parquet files, no server needed |
| Object store | local folders → MinIO (later) | S3-compatible, containerizable |
| Vector DB | Chroma (coming) | local, no setup, good for RAG |
| API | FastAPI (coming) | async, auto-docs, OpenShift-ready |
| Containers | Podman | rootless, Red Hat native |

---

## Project structure

```
nasa-data-lakehouse/
├── ingestion/
│   ├── neo/
│   │   ├── extract.py        # pulls raw NEO data from NASA API → bronze
│   │   └── transform.py      # unpacks raw JSON, fixes types → silver
│   └── shared/               # coming: shared utilities
├── gold/
│   └── neo/
│       └── enrich.py         # risk scoring, size classification → gold
├── storage/
│   ├── bronze/neo/           # raw JSON exactly as received (gitignored)
│   ├── silver/neo/           # cleaned, typed, derived columns (gitignored)
│   └── gold/neo/             # enriched, business logic applied (gitignored)
├── query/
│   └── duckdb_engine.py      # SQL queries directly on Parquet files
├── embeddings/               # coming: text → vectors pipeline
├── rag/                      # coming: retrieval + LLM answer service
├── api/                      # coming: FastAPI REST layer
├── docker/                   # coming: Dockerfile + docker-compose.yml
├── notebooks/
│   └── neo/
│       ├── 01_neo_discovery.ipynb   # API exploration, data structure
│       └── 02_neo_enrich.ipynb      # EDA, gold layer design
├── .env.example              # API key template (copy to .env, never commit)
└── requirements.txt
```

---

## Medallion architecture

Data flows through three layers, each adding more value:

```
Bronze  →  raw, untouched, exactly as the API returned it
Silver  →  cleaned types, renamed columns, simple derived fields
Gold    →  enriched with business logic, scoring, cross-dataset context
```

- Bronze is your safety net — if a transform breaks, the raw data is always there
- Silver is what most queries run against — clean and trustworthy
- Gold is what the API and RAG service expose — ready for decisions

---

## Datasets

### NEO — Near Earth Objects

Pulls asteroid close-approach data from NASA's NeoWs API. 5 years of data (2021-2026), 10,133 close approaches.

**Bronze** (`ingestion/neo/extract.py`) — raw storage:

| Field | Type | Description |
|---|---|---|
| hash_id | string | stable unique ID, hashed from natural keys |
| id | string | NASA catalog ID |
| name | string | asteroid designation e.g. `374038 (2004 HW)` |
| date | string | observation date |
| raw | string | full JSON object exactly as NASA returned it |

**Silver** (`ingestion/neo/transform.py`) — cleaned and typed:

| Field | Type | Description |
|---|---|---|
| absolute_magnitude_h | float | intrinsic brightness, relates to size |
| diameter_km_min/max/avg | float | estimated diameter in km |
| is_potentially_hazardous | bool | NASA hazard flag (size + orbit based) |
| is_sentry_object | bool | on NASA's active impact watch list |
| velocity_km_per_s | float | speed relative to Earth |
| miss_distance_lunar | float | closest distance in lunar distances |
| miss_distance_au | float | closest distance in astronomical units |
| close_approach_datetime | datetime | exact date and time of closest approach |
| nasa_jpl_url | string | link to NASA's full database entry |

**Gold** (`gold/neo/enrich.py`) — enriched:

| Field | Type | Description |
|---|---|---|
| hazard_score | float | composite risk score 0-1 (proximity 40%, velocity 30%, size 30%) |
| hazard_label | string | low / moderate / high / critical |
| size_class | string | tiny / small / medium / large / major |
| is_named | bool | has a proper name vs just a catalog designation |
| critical_alert | bool | True when both hazardous AND sentry (rare) |
| miss_distance_percentile | float | how close relative to 5yr history |
| velocity_percentile | float | how fast relative to 5yr history |
| size_percentile | float | how large relative to 5yr history |

Key finding from EDA: `is_potentially_hazardous` and `is_sentry_object` measure completely different risk profiles and never overlap in 5 years of data. Hazardous objects are large and close. Sentry objects are tiny but on mathematically intersecting orbital trajectories.

---

## Querying with DuckDB

DuckDB reads Parquet files directly with SQL — no database server needed.

```python
import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT name, hazard_score, hazard_label, size_class,
           miss_distance_lunar, velocity_km_per_s
    FROM read_parquet('storage/gold/neo/neo_*.parquet')
    WHERE hazard_label = 'critical'
    ORDER BY hazard_score DESC
""").df()
```

---

## Setup

**1. Clone and create environment**

```bash
git clone https://github.com/cvhuynh1777/nasa-data-lakehouse.git
cd nasa-data-lakehouse

conda create -n nasa-lakehouse python=3.11 -y
conda activate nasa-lakehouse
pip install -r requirements.txt
```

**2. Get a NASA API key**

Free, instant: [api.nasa.gov](https://api.nasa.gov)

**3. Add your key**

```bash
cp .env.example .env
# edit .env and paste your key
```

**4. Run the NEO pipeline**

```bash
python ingestion/neo/extract.py
python ingestion/neo/transform.py
python gold/neo/enrich.py
```

---

## Requirements

```
requests
pandas
pyarrow
duckdb
python-dotenv
seaborn
matplotlib
jupyter
```