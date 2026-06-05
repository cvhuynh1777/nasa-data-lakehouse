import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from datetime import datetime

GOLD_PATH = Path("storage/gold/apod")
CHROMA_PATH = Path("storage/chroma")

# lightweight model — fast, good quality, runs locally
MODEL_NAME = "all-MiniLM-L6-v2"


def load_gold() -> pd.DataFrame:
    """Load latest APOD gold parquet."""
    files = sorted(GOLD_PATH.glob("apod_*.parquet"))
    if not files:
        raise FileNotFoundError("No APOD gold files found. Run gold/apod/enrich.py first.")
    df = pd.read_parquet(files[-1])
    print(f"Loaded {len(df)} APOD entries")
    return df


def get_chroma_collection():
    """Get or create Chroma collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name="apod",
        metadata={"description": "NASA Astronomy Picture of the Day embeddings"}
    )
    return collection


def build_embeddings(df: pd.DataFrame):
    """
    Embed APOD rag_text and store in Chroma.
    Uses sentence-transformers to convert text → vectors.
    """
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    collection = get_chroma_collection()

    # check if already populated
    existing = collection.count()
    if existing > 0:
        print(f"Collection already has {existing} embeddings — skipping")
        return collection

    print(f"Embedding {len(df)} entries...")
    texts = df["rag_text"].tolist()
    ids   = df["hash_id"].tolist()

    # metadata stored alongside vectors for retrieval
    metadatas = df[["date", "title", "media_type", "url", "word_count"]].copy()
    metadatas["date"] = metadatas["date"].dt.strftime("%Y-%m-%d")
    metadatas["word_count"] = metadatas["word_count"].astype(int)
    metadatas["url"] = metadatas["url"].fillna("").astype(str)
    metadata_list = metadatas.to_dict(orient="records")

    # embed in batches
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i:i+batch_size]
        batch_ids       = ids[i:i+batch_size]
        batch_metadata  = metadata_list[i:i+batch_size]

        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()

        collection.add(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_texts,
            metadatas=batch_metadata
        )
        print(f"  embedded {min(i+batch_size, len(texts))}/{len(texts)}")

    print(f"Done! {collection.count()} entries in Chroma")
    return collection


def search(question: str, n_results: int = 3) -> list:
    """
    Search Chroma for entries most relevant to a question.
    Returns top n_results with text and metadata.
    """
    model = SentenceTransformer(MODEL_NAME)
    collection = get_chroma_collection()

    question_embedding = model.encode([question]).tolist()

    results = collection.query(
        query_embeddings=question_embedding,
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id":       results["ids"][0][i],
            "text":     results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score":    round(1 - results["distances"][0][i], 4)
        })
    return hits


if __name__ == "__main__":
    df = load_gold()
    build_embeddings(df)

    # test a few searches
    print("\n--- Test searches ---")
    questions = [
        "black holes",
        "interstellar objects visiting our solar system",
        "asteroids close to Earth",
        "galaxies colliding",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        hits = search(q, n_results=2)
        for hit in hits:
            print(f"  [{hit['score']}] {hit['metadata']['date']} — {hit['metadata']['title']}")