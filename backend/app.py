"""
DocMind AI — FastAPI application (MVP).

Pipeline:
- Upload PDF → save → extract text → chunk → **embed + FAISS index** (Phase 4)
- Ask a question → **retrieve chunks** → **OpenAI chat** with context (Phase 5)

Run from the project root:
    uvicorn backend.app:app --reload

Loads `.env` from the project root (via `backend.vector_store` import side effects).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

# Importing vector_store runs load_dotenv() so OPENAI_* vars exist before requests.
from backend.chunker import chunk_text
from backend.parser import extract_text_from_pdf
from backend.vector_store import (
    build_vector_index,
    get_openai_client,
    has_index,
    search_similar_chunks,
)


class UploadProcessResponse(BaseModel):
    """Returned after upload, parse, chunk, and vector index build."""

    message: str = Field(..., description="Human-readable status")
    document_id: str = Field(..., description="Use this id with POST /ask")
    saved_as: str = Field(..., description="Filename under uploads/")
    text_preview: str = Field(..., description="First 500 characters of extracted text")
    total_characters: int = Field(..., description="Length of full extracted text")
    total_chunks: int = Field(..., description="Chunks indexed (non-empty only)")


class AskRequest(BaseModel):
    """Body for document Q&A."""

    document_id: str = Field(..., description="id returned from POST /upload")
    question: str = Field(..., min_length=1, description="Natural language question about the PDF")


class AskResponse(BaseModel):
    """Model answer plus the text chunks used as context (RAG-style transparency)."""

    answer: str = Field(..., description="Model reply grounded in source chunks")
    source_chunks: list[str] = Field(
        default_factory=list,
        description="Retrieved passages sent to the model as context",
    )


# --- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"

# Allowed MIME type for PDF uploads (browsers usually send this for .pdf files).
ALLOWED_PDF_CONTENT_TYPES = frozenset({"application/pdf"})

# --- In-memory document registry (MVP: lost on server restart) --------------
# Maps document_id → metadata plus the same chunk texts we indexed (non-empty only).
DOCUMENTS: dict[str, dict[str, Any]] = {}


def _chat_model() -> str:
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


# --- App -------------------------------------------------------------------
app = FastAPI(
    title="DocMind AI",
    description="PDF upload, chunking, embeddings + FAISS, and simple RAG Q&A (MVP).",
    version="0.3.0",
)


@app.on_event("startup")
def ensure_upload_dir() -> None:
    """Create the uploads folder on disk if it does not exist yet."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for load balancers and quick manual tests."""
    return {"status": "ok"}


@app.post("/upload", response_model=UploadProcessResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadProcessResponse:
    """
    Accept a PDF, save it, extract text, chunk, build embeddings + FAISS index.

    Returns a **document_id** — pass it to POST /ask to query that file only.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    original_name = file.filename or "document.pdf"

    ext_ok = original_name.lower().endswith(".pdf")
    type_ok = content_type in ALLOWED_PDF_CONTENT_TYPES
    if not (type_ok or ext_ok):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Send a file with content-type application/pdf or a .pdf name.",
        )

    suffix = ".pdf" if not original_name.lower().endswith(".pdf") else ""
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_path = UPLOAD_DIR / unique_name

    try:
        with dest_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                out.write(chunk)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not save file: {exc}") from exc
    finally:
        await file.close()

    try:
        full_text = extract_text_from_pdf(str(dest_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    text_chunks = chunk_text(full_text)
    # Only non-empty strings get embeddings (matches vector_store.build_vector_index).
    indexed_chunks = [c for c in text_chunks if c.strip()]

    document_id = str(uuid.uuid4())

    # Phase 4: OpenAI embeddings + FAISS (may raise if API key missing / API error).
    try:
        build_vector_index(document_id, text_chunks)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 — MVP: surface embedding API failures
        raise HTTPException(
            status_code=502,
            detail=f"Embedding or index build failed: {exc}",
        ) from exc

    DOCUMENTS[document_id] = {
        "saved_as": unique_name,
        "original_filename": original_name,
        "chunks": indexed_chunks,
        "text_preview": full_text[:500],
        "total_characters": len(full_text),
        "total_chunks": len(indexed_chunks),
    }

    return UploadProcessResponse(
        message="File uploaded and processed successfully",
        document_id=document_id,
        saved_as=unique_name,
        text_preview=full_text[:500],
        total_characters=len(full_text),
        total_chunks=len(indexed_chunks),
    )


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    """
    Retrieve top similar chunks for `question`, then ask OpenAI chat to answer using them.

    This is a minimal RAG loop: **search** (FAISS) → **generate** (chat completion).
    """
    if body.document_id not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Unknown document_id. Upload a PDF first.")

    try:
        client = get_openai_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # If upload produced no embeddable chunks, retrieval returns nothing useful.
    if not has_index(body.document_id) or not DOCUMENTS[body.document_id].get("chunks"):
        return AskResponse(
            answer="This document has no indexed text chunks (empty PDF or no extractable text).",
            source_chunks=[],
        )

    source_chunks = search_similar_chunks(body.document_id, body.question, top_k=4)

    # Build a single user message: retrieved passages + the user's question.
    context_parts = [f"[Passage {i + 1}]\n{text}" for i, text in enumerate(source_chunks)]
    context_block = "\n\n".join(context_parts) if context_parts else "(no passages retrieved)"

    system_prompt = (
        "You are DocMind AI, a careful assistant. Answer using ONLY the provided passages. "
        "If the passages do not contain enough information, say you do not know based on the document. "
        "Do not invent facts beyond the passages."
    )
    user_prompt = f"Passages from the document:\n{context_block}\n\nQuestion: {body.question}"

    try:
        completion = client.chat.completions.create(
            model=_chat_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001 — MVP: pass through a readable error
        raise HTTPException(status_code=502, detail=f"OpenAI chat completion failed: {exc}") from exc

    choice = completion.choices[0].message
    answer_text = (choice.content or "").strip() or "(empty model response)"

    return AskResponse(answer=answer_text, source_chunks=source_chunks)
