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
│   ├── nasa_api.py       # pulls raw data from NASA APIs → bronze
│   └── transform.py      # cleans bronze data → silver
├── storage/
│   ├── bronze/           # raw data exactly as received (gitignored)
│   ├── silver/           # cleaned, typed, derived columns (gitignored)
│   └── gold/             # enriched, business logic applied (gitignored)
├── query/
│   └── duckdb_engine.py  # SQL queries directly on Parquet files
├── embeddings/           # coming: text → vectors pipeline
├── rag/                  # coming: retrieval + LLM answer service
├── api/                  # coming: FastAPI REST layer
├── docker/               # coming: Dockerfile + docker-compose.yml
├── notebooks/            # exploration and learning
├── .env.example          # API key template (copy to .env, never commit .env)
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

**Why three layers?**
- Bronze is your safety net — if a transform breaks, the raw data is always there
- Silver is what most queries run against — clean and trustworthy
- Gold is what the API and RAG service expose — ready for decisions

---

## Datasets

### NEO — Near Earth Objects (`ingestion/nasa_api.py`)

Pulls asteroid close-approach data from NASA's NeoWs API.

**Bronze fields (raw):**
| Field | Type | Description |
|---|---|---|
| id | string | NASA catalog ID |
| name | string | asteroid designation e.g. `374038 (2004 HW)` |
| date | string | observation date |
| is_potentially_hazardous | bool | NASA hazard flag |
| estimated_diameter_km_min | float | minimum diameter estimate |
| estimated_diameter_km_max | float | maximum diameter estimate |
| close_approach_date | string | date of closest approach |
| relative_velocity_km_per_s | float | speed relative to Earth |
| miss_distance_km | float | closest distance to Earth in km |
| orbiting_body | string | which body it orbits (usually Earth) |

**Silver additions (`ingestion/transform.py`):**
| Field | Type | Description |
|---|---|---|
| estimated_diameter_km_avg | float | average of min/max diameter |
| miss_distance_lunar | float | miss distance in lunar distances (1 LD = 384,400 km) |

**Why lunar distances?** More intuitive than km for space scales. The Moon is 1 LD away. A pass at 44 LD is much easier to reason about than 1.7 × 10⁷ km.

**Gold (planned):**
- `risk_score` — composite score from distance, velocity, size
- `size_classification` — small / medium / large / major
- `miss_distance_percentile` — how close relative to historical passes
- `is_named` — has a proper name vs just a catalog designation

---

## Querying with DuckDB

DuckDB reads Parquet files directly with SQL — no database server needed.

```python
import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT name, miss_distance_lunar, velocity_km_per_s
    FROM read_parquet('storage/silver/neo_*.parquet')
    WHERE is_potentially_hazardous = true
    ORDER BY miss_distance_lunar ASC
""").df()
```

Run the example queries:
```bash
python query/duckdb_engine.py
```

---

## Setup

**1. Clone and create environment**
```bash
git clone https://github.com/YOUR_USERNAME/nasa-data-lakehouse.git
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

**4. Run the pipeline**
```bash
# pull raw data → bronze
python ingestion/nasa_api.py

# clean → silver
python ingestion/transform.py

# query with SQL
python query/duckdb_engine.py
```

---

## Requirements

```
requests
pandas
pyarrow
duckdb
python-dotenv
```

---

## Roadmap

- [x] NEO ingestion pipeline (bronze + silver)
- [x] DuckDB SQL query layer
- [ ] Gold enrichment layer (risk scoring, size classification)
- [ ] APOD ingestion (text-rich data for RAG)
- [ ] Embedding pipeline (sentence-transformers + Chroma)
- [ ] RAG service
- [ ] FastAPI REST layer (`/query`, `/search`, `/rag`, `/datasets`)
- [ ] Containerize with Podman
- [ ] Deploy to Red Hat OpenShift

---

## Notes on naming

Asteroid designations like `2004 HW` follow the Minor Planet Center convention — the year of discovery, a letter for the half-month, and a sequential letter. Numbered prefixes like `374038` are permanent catalog IDs assigned once the orbit is confirmed. Some get proper names (e.g. `136818 Selqet`).
