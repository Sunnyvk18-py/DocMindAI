"""
In-memory vector index per document (Phase 4).

Embeddings come from OpenAI; similarity search uses FAISS (inner product on
L2-normalized vectors ≈ cosine similarity). This MVP keeps indexes in RAM only —
restarting the server clears all indexes.
"""

from __future__ import annotations

import os
from typing import Any

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Load variables from project root .env (works even if cwd is elsewhere).
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# --- OpenAI client -----------------------------------------------------------
# The key is read on first use; missing key surfaces as a clear RuntimeError.
_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Return a shared OpenAI client (embeddings + chat use the same API key)."""
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key or key.strip() == "" or key == "your_api_key_here":
            raise RuntimeError(
                "OPENAI_API_KEY is missing or placeholder. Copy .env.example to .env and set your key."
            )
        _client = OpenAI(api_key=key)
    return _client


def _embedding_model() -> str:
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _embed_texts(texts: list[str]) -> np.ndarray:
    """
    Call OpenAI embeddings API and return a float32 matrix (n, dim).

    Large documents are batched to stay within reasonable request sizes.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    client = get_openai_client()
    model = _embedding_model()
    batch_size = 100
    all_embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        # Order vectors by index within this batch (OpenAI returns sorted by index).
        batch_vectors: list[list[float]] = [[] for _ in batch]
        for item in response.data:
            batch_vectors[item.index] = list(item.embedding)
        all_embeddings.extend(batch_vectors)

    return np.array(all_embeddings, dtype=np.float32)


# Per-document storage: chunks + FAISS index (None if no embeddable chunks).
_STORE: dict[str, dict[str, Any]] = {}


def build_vector_index(document_id: str, chunks: list[str]) -> None:
    """
    Embed each text chunk and build a FAISS index for this document_id.

    Empty or whitespace-only chunks are skipped. If nothing remains, we still
    record the document with an empty chunk list and no index (search returns []).
    """
    # Keep only chunks that actually carry text (embedding empty strings is useless).
    usable = [c for c in chunks if c.strip()]
    if not usable:
        _STORE[document_id] = {"chunks": [], "index": None, "dim": 0}
        return

    vectors = _embed_texts(usable)
    if vectors.size == 0:
        _STORE[document_id] = {"chunks": [], "index": None, "dim": 0}
        return

    dim = int(vectors.shape[1])
    # Normalize so inner product equals cosine similarity between unit vectors.
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    _STORE[document_id] = {"chunks": usable, "index": index, "dim": dim}


def search_similar_chunks(document_id: str, query: str, top_k: int = 4) -> list[str]:
    """
    Embed the query, find the top_k most similar stored chunks, return their text.

    Returns fewer than top_k if the document has fewer chunks. Unknown id → [].
    """
    record = _STORE.get(document_id)
    if not record or record["index"] is None or not record["chunks"]:
        return []

    index: faiss.Index = record["index"]
    chunks: list[str] = record["chunks"]
    dim: int = record["dim"]

    query_vec = _embed_texts([query])
    if query_vec.shape != (1, dim):
        # Model/dimension mismatch (e.g. changed embedding model) — fail safe.
        return []

    faiss.normalize_L2(query_vec)
    k = min(top_k, len(chunks))
    scores, indices = index.search(query_vec, k)

    out: list[str] = []
    for idx in indices[0]:
        if idx < 0 or idx >= len(chunks):
            continue
        out.append(chunks[idx])
    return out


def has_index(document_id: str) -> bool:
    """True if this document_id has a FAISS index (at least one embedded chunk)."""
    rec = _STORE.get(document_id)
    return bool(rec and rec.get("index") is not None)
