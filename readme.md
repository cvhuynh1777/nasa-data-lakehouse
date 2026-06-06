# NASA Data Lakehouse

A local data lakehouse for NASA datasets with a RAG service and REST API. Built to run on a MacBook, containerizable with Podman, and deployable to Red Hat OpenShift.

---

## What it does

Pulls live NASA data, cleans and enriches it through a medallion storage architecture (bronze → silver → gold), makes it queryable with SQL, and exposes it through a REST API with two AI-powered query interfaces — a natural language SQL interface for structured data and a RAG service for semantic search over astronomy text.

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11 | — |
| Environment | conda | isolated dependencies |
| Data format | Parquet | columnar, compressed, fast |
| Query engine | DuckDB | SQL directly on Parquet files, no server needed |
| Vector DB | Chroma | local vector store for RAG embeddings |
| Embeddings | sentence-transformers | converts text to vectors locally |
| LLM | Claude (Anthropic) | NL query + RAG answer generation |
| API | FastAPI | async, auto-docs, OpenShift-ready |
| Object store | local folders → MinIO (coming) | S3-compatible, containerizable |
| Containers | Podman | rootless, Red Hat native |

---

## Project structure

```
nasa-data-lakehouse/
├── ingestion/
│   ├── neo/
│   │   ├── extract.py        # pulls raw NEO data → bronze
│   │   └── transform.py      # unpacks raw JSON, fixes types → silver
│   └── apod/
│       ├── extract.py        # pulls raw APOD data → bronze
│       └── transform.py      # unpacks raw JSON, fixes types → silver
├── gold/
│   ├── neo/
│   │   └── enrich.py         # risk scoring, size classification → gold
│   └── apod/
│       └── enrich.py         # word count, rag_text, media flags → gold
├── embeddings/
│   └── pipeline.py           # embeds APOD rag_text → Chroma vector store
├── rag/
│   └── service.py            # semantic search + Claude answer generation
├── storage/
│   ├── bronze/neo/           # raw JSON exactly as received (gitignored)
│   ├── bronze/apod/          # raw JSON exactly as received (gitignored)
│   ├── silver/neo/           # cleaned, typed (gitignored)
│   ├── silver/apod/          # cleaned, typed (gitignored)
│   ├── gold/neo/             # enriched asteroid data (gitignored)
│   ├── gold/apod/            # enriched APOD data (gitignored)
│   └── chroma/               # vector embeddings (gitignored)
├── query/
│   └── duckdb_engine.py      # SQL queries directly on Parquet files
├── api/
│   └── main.py               # FastAPI app
├── docker/                   # coming: Dockerfile + docker-compose.yml
├── notebooks/
│   ├── neo/
│   │   ├── 01_neo_discovery.ipynb   # API exploration, data structure
│   │   └── 02_neo_enrich.ipynb      # EDA, gold layer design
│   └── apod/
│       ├── 01_apod_discovery.ipynb  # API exploration
│       └── 02_apod_rag.ipynb        # RAG pipeline built step by step
├── .env.example
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
| critical_alert | bool | True when both hazardous AND sentry (extremely rare) |
| miss_distance_percentile | float | how close relative to 5yr history |
| velocity_percentile | float | how fast relative to 5yr history |
| size_percentile | float | how large relative to 5yr history |

Key finding from EDA: `is_potentially_hazardous` and `is_sentry_object` measure completely different risk profiles and never overlap in 5 years of data. Hazardous objects are large and close. Sentry objects are tiny but on mathematically intersecting orbital trajectories.

---

### APOD — Astronomy Picture of the Day

Pulls NASA's daily astronomy image and explanation. 5 years of data (2021-2026), 1,289 entries.

**Bronze** (`ingestion/apod/extract.py`) — raw storage:

| Field | Type | Description |
|---|---|---|
| hash_id | string | stable unique ID hashed from date |
| date | string | publication date |
| raw | string | full JSON object exactly as NASA returned it |

**Silver** (`ingestion/apod/transform.py`) — cleaned and typed:

| Field | Type | Description |
|---|---|---|
| title | string | entry title |
| explanation | string | full astronomy explanation text |
| media_type | string | image / video / other |
| url | string | standard resolution image or video URL |
| hdurl | string | high resolution image URL |
| copyright | string | photographer credit (null for NASA/public domain) |

**Gold** (`gold/apod/enrich.py`) — enriched for RAG:

| Field | Type | Description |
|---|---|---|
| rag_text | string | title + explanation combined for embedding |
| word_count | int | explanation length |
| has_image | bool | True if media_type is image |
| year | int | extracted from date |
| month | int | extracted from date |

Entries with fewer than 50 words are filtered out before embedding (removes thin content like tweet links).

---

## RAG pipeline

APOD explanations are embedded using `sentence-transformers` and stored in Chroma. At query time the user's question is embedded and the most semantically similar APOD entries are retrieved and passed to Claude as context.

```
user question
     ↓
sentence-transformers embeds the question → vector
     ↓
Chroma finds nearest APOD entry vectors
     ↓
retrieved entries passed to Claude as context
     ↓
Claude answers grounded in real APOD content
```

Example:

```
Q: "tell me about interstellar objects visiting our solar system"

Retrieved:
  [0.17] 2025-08-09 — Interstellar Interloper 3I/ATLAS from Hubble
  [0.12] 2025-07-07 — Interstellar Comet 3I/ATLAS

Answer: Based on the APOD entries, three interstellar objects have been
        detected passing through our solar system: 1I/Oumuamua (2017),
        2I/Borisov (2019), and 3I/ATLAS (2025)...
```

---

## Natural language query

A separate text-to-SQL interface for the NEO structured dataset. Claude generates DuckDB SQL from natural language and queries the gold lakehouse directly.

```
Q: "what asteroids came closest this week?"
→ Claude generates SQL with correct date range
→ DuckDB queries gold parquet
→ returns ranked results + the generated SQL
```

---

## API

```bash
python -m uvicorn api.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`

| Endpoint | Description |
|---|---|
| `GET /` | Health check |
| `GET /datasets` | Available datasets and stats |
| `GET /query` | Query NEO gold data with optional filters |
| `GET /hazardous` | Highest risk asteroid passes |
| `GET /sentry` | Objects on NASA's Sentry impact watch list |
| `GET /nl-query?question=...` | Natural language SQL on NEO data via Claude |
| `GET /rag?question=...` | Semantic search + grounded answer on APOD data |

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

**2. Get API keys**

NASA API key (free, instant): [api.nasa.gov](https://api.nasa.gov)
Anthropic API key: [console.anthropic.com](https://console.anthropic.com)

**3. Add your keys**

```bash
cp .env.example .env
# edit .env and add NASA_API_KEY and ANTHROPIC_API_KEY
```

**4. Run the NEO pipeline**

```bash
python ingestion/neo/extract.py
python ingestion/neo/transform.py
python gold/neo/enrich.py
```

**5. Run the APOD pipeline**

```bash
python ingestion/apod/extract.py
python ingestion/apod/transform.py
python gold/apod/enrich.py
```

**6. Build embeddings**

```bash
python embeddings/pipeline.py
```

**7. Start MinIO**

```bash
podman machine start
podman start minio
```

**8. Sync to MinIO**

```bash
python storage/sync.py
```

**9. Run the API**

```bash
python -m uvicorn api.main:app --reload
```