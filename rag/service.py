"""
RAG service for APOD data.
Retrieves relevant APOD entries using semantic search (Chroma + sentence-transformers)
and generates grounded answers using Claude.
"""

import anthropic
import os
from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb

load_dotenv()

CHROMA_PATH = Path("storage/chroma")
MODEL_NAME  = "all-MiniLM-L6-v2"

# load once at module level — expensive to reload on every request
_model      = None
_collection = None
_client     = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_collection():
    global _collection
    if _collection is None:
        chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = chroma.get_collection("apod")
    return _collection


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def search(question: str, n_results: int = 3) -> list:
    """Find most relevant APOD entries for a question."""
    model      = get_model()
    collection = get_collection()

    question_vector = model.encode(question).tolist()

    results = collection.query(
        query_embeddings=[question_vector],
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


def ask(question: str, n_results: int = 3) -> dict:
    """Full RAG pipeline: question → retrieve → Claude → answer."""
    hits    = search(question, n_results)
    client  = get_client()

    # build context from retrieved entries
    context_entries = []
    for hit in hits:
        meta = hit["metadata"]
        context_entries.append(
            f"Date: {meta['date']}\nTitle: {meta['title']}\n{hit['text']}"
        )
    context = "\n\n---\n\n".join(context_entries)

    prompt = f"""You are a NASA astronomy assistant. Answer the question
using ONLY the APOD entries provided below.
Cite specific entries by title and date in your answer.
If the entries don't contain enough information, say so.

APOD entries:
{context}

Question: {question}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        "question":  question,
        "retrieved": [
            {
                "date":  h["metadata"]["date"],
                "title": h["metadata"]["title"],
                "score": h["score"],
                "url":   h["metadata"].get("url", None)
            }
            for h in hits
        ],
        "answer": message.content[0].text
    }


if __name__ == "__main__":
    questions = [
        "tell me about black holes",
        "interstellar objects visiting our solar system",
        "asteroids close to Earth",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        result = ask(q)
        for r in result["retrieved"]:
            print(f"  [{r['score']}] {r['date']} — {r['title']}")
        print(f"Answer: {result['answer'][:200]}...")