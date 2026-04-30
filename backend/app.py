"""
DocMind AI — FastAPI application (MVP).

Pipeline:
- Upload PDF → extract → chunk → embed + FAISS
- Ask, summarize, and quiz from stored chunks + OpenAI

Run from the project root:
    uvicorn backend.app:app --reload
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from backend.chunker import chunk_text
from backend.parser import extract_text_from_pdf
from backend.vector_store import (
    build_vector_index,
    get_openai_client,
    has_index,
    search_similar_chunks,
)


# --- Shared API models -------------------------------------------------------
class UploadProcessResponse(BaseModel):
    """Returned after upload, parse, chunk, and vector index build."""

    message: str = Field(..., description="Human-readable status")
    document_id: str = Field(..., description="Use with /ask, /summary, and /quiz")
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


class SummaryRequest(BaseModel):
    """Body to generate a structured study summary for one document."""

    document_id: str = Field(..., description="id returned from POST /upload")


class SummaryResponse(BaseModel):
    """Concise summary plus bullet-style study aids."""

    summary: str = Field(..., description="Short overview of the document")
    key_points: list[str] = Field(..., description="Main takeaways as a list")
    important_concepts: list[str] = Field(..., description="Terms or ideas worth remembering")


class QuizRequest(BaseModel):
    """Body to auto-generate a study quiz from document chunks."""

    document_id: str = Field(..., description="id returned from POST /upload")
    num_questions: int = Field(
        default=5,
        ge=1,
        le=25,
        description="How many question/answer pairs to generate",
    )


class QuizItem(BaseModel):
    """One quiz question with its model-written answer (check against your materials)."""

    question: str
    answer: str


class QuizResponse(BaseModel):
    """Structured quiz for self-study."""

    questions: list[QuizItem] = Field(..., description="Generated questions with answers")


# --- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"

ALLOWED_PDF_CONTENT_TYPES = frozenset({"application/pdf"})

# --- In-memory document registry (MVP: lost on server restart) --------------
DOCUMENTS: dict[str, dict[str, Any]] = {}


def _chat_model() -> str:
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


def _get_nonempty_document(document_id: str) -> tuple[dict[str, Any], list[str]]:
    """
    Resolve a document that exists, has chunks, and has a FAISS index.

    Raises HTTPException with stable messages for common client mistakes.
    """
    if document_id not in DOCUMENTS:
        raise HTTPException(
            status_code=404,
            detail="Unknown document_id. Upload a PDF first to obtain a valid document_id.",
        )
    doc = DOCUMENTS[document_id]
    chunks = doc.get("chunks") or []
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="This document has no indexed text. The PDF may be empty, image-only, or contain no extractable text.",
        )
    if not has_index(document_id):
        raise HTTPException(
            status_code=400,
            detail="This document has no search index. Re-upload after fixing your OpenAI API key or embedding errors.",
        )
    return doc, chunks


def _study_context_chunks(document_id: str, retrieval_query: str, top_k: int) -> list[str]:
    """Pull the most relevant stored passages for study-style prompts (semantic search)."""
    _, chunks = _get_nonempty_document(document_id)
    k = min(top_k, len(chunks))
    retrieved = search_similar_chunks(document_id, retrieval_query, top_k=k)
    if not retrieved:
        # Rare fallback: first chunks in document order.
        return chunks[:k]
    return retrieved


def _openai_json_completion(*, system: str, user: str, temperature: float = 0.35) -> dict[str, Any]:
    """
    Call chat completions with JSON mode and return parsed dict.

    Maps auth / transport / parse issues to HTTP errors for consistent API behavior.
    """
    try:
        client = get_openai_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        completion = client.chat.completions.create(
            model=_chat_model(),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001 — MVP: readable upstream errors
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed: {exc}",
        ) from exc

    raw = (completion.choices[0].message.content or "").strip()
    if not raw:
        raise HTTPException(status_code=502, detail="OpenAI returned an empty response.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned invalid JSON.",
        ) from exc


# --- App -------------------------------------------------------------------
app = FastAPI(
    title="DocMind AI",
    description="PDF upload, embeddings + FAISS, Q&A, summaries, and quizzes (MVP).",
    version="0.4.0",
)

# Allow the Vite dev server (and localhost variants) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_upload_dir() -> None:
    """Create the uploads folder on disk if it does not exist yet."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload", response_model=UploadProcessResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadProcessResponse:
    """Accept a PDF, save, extract, chunk, embed + index; return document_id."""
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
                chunk = await file.read(1024 * 1024)
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
    indexed_chunks = [c for c in text_chunks if c.strip()]

    document_id = str(uuid.uuid4())

    try:
        build_vector_index(document_id, text_chunks)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
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
    """Retrieve top chunks for the question, then answer with OpenAI chat."""
    _get_nonempty_document(body.document_id)

    try:
        client = get_openai_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    source_chunks = search_similar_chunks(body.document_id, body.question, top_k=4)

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
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"OpenAI chat completion failed: {exc}") from exc

    choice = completion.choices[0].message
    answer_text = (choice.content or "").strip() or "(empty model response)"

    return AskResponse(answer=answer_text, source_chunks=source_chunks)


@app.post("/summary", response_model=SummaryResponse)
def summary(body: SummaryRequest) -> SummaryResponse:
    """
    Build a short study summary from the most important retrieved chunks.

    Uses semantic search to pick passages likely to contain thesis, definitions,
    examples, and conclusions, then asks the model for structured JSON.
    """
    _get_nonempty_document(body.document_id)

    retrieval_query = (
        "Main purpose, thesis, key arguments, definitions, examples, data, "
        "and conclusions of the document."
    )
    context_chunks = _study_context_chunks(body.document_id, retrieval_query, top_k=12)
    context_block = "\n\n".join(
        f"[Passage {i + 1}]\n{text}" for i, text in enumerate(context_chunks)
    )

    system_prompt = (
        "You are DocMind AI. Read the passages and respond with a single JSON object ONLY. "
        'Schema: {"summary": string, "key_points": string[], "important_concepts": string[]}. '
        "summary: 2–5 clear sentences. key_points: 4–8 bullets as strings. "
        "important_concepts: 5–12 short concept or term strings. "
        "Ground everything strictly in the passages; if content is thin, say so in summary and use fewer items."
    )
    user_prompt = f"Passages:\n{context_block}\n\nProduce the JSON object now."

    data = _openai_json_completion(system=system_prompt, user=user_prompt, temperature=0.25)

    try:
        return SummaryResponse.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI JSON did not match the expected summary shape: {exc}",
        ) from exc


@app.post("/quiz", response_model=QuizResponse)
def quiz(body: QuizRequest) -> QuizResponse:
    """
    Generate a multiple short-answer style quiz from document content.

    Answers are model-generated from the same passages—treat them as study aids
    and verify against the original PDF when accuracy matters.
    """
    _, all_chunks = _get_nonempty_document(body.document_id)

    retrieval_query = (
        "Facts, definitions, steps, dates, names, cause-effect relationships, "
        "and details suitable for examination questions."
    )
    context_chunks = _study_context_chunks(body.document_id, retrieval_query, top_k=min(16, len(all_chunks)))
    context_block = "\n\n".join(
        f"[Passage {i + 1}]\n{text}" for i, text in enumerate(context_chunks)
    )

    system_prompt = (
        "You are DocMind AI. Create a study quiz from the passages. "
        "Respond with ONE JSON object ONLY. "
        'Schema: {"questions": [{"question": string, "answer": string}, ...]}. '
        "Each answer should be 1–4 sentences, grounded in the passages. "
        "Do not include multiple-choice letters unless the passage itself does. "
        "Vary question style (what/why/how/when/define/compare)."
    )
    user_prompt = (
        f"Passages:\n{context_block}\n\n"
        f"Generate exactly {body.num_questions} question/answer pairs in the JSON object."
    )

    data = _openai_json_completion(system=system_prompt, user=user_prompt, temperature=0.45)

    try:
        parsed = QuizResponse.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI JSON did not match the expected quiz shape: {exc}",
        ) from exc

    if not parsed.questions:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned no quiz questions. Try again or use a richer PDF.",
        )

    # Cap extras; fewer than requested is still useful for study (model may hit context limits).
    if len(parsed.questions) > body.num_questions:
        parsed = QuizResponse(questions=parsed.questions[: body.num_questions])

    return parsed
