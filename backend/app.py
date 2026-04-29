"""
DocMind AI — FastAPI application.

Phases implemented here:
- Upload PDFs to uploads/
- Extract text (parser) and chunk text (chunker) for later RAG / embeddings.

Run from the project root:
    uvicorn backend.app:app --reload
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.chunker import chunk_text
from backend.parser import extract_text_from_pdf


class UploadProcessResponse(BaseModel):
    """JSON shape returned after a PDF is saved, parsed, and chunked."""

    message: str = Field(..., description="Human-readable status")
    saved_as: str = Field(..., description="Filename under uploads/")
    text_preview: str = Field(..., description="First 500 characters of extracted text")
    total_characters: int = Field(..., description="Length of full extracted text")
    total_chunks: int = Field(..., description="Number of overlapping text chunks (for future RAG)")

# --- Paths -----------------------------------------------------------------
# This file lives in backend/, so the project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"

# Allowed MIME type for PDF uploads (browsers usually send this for .pdf files).
ALLOWED_PDF_CONTENT_TYPES = frozenset({"application/pdf"})

# --- App -------------------------------------------------------------------
app = FastAPI(
    title="DocMind AI",
    description="PDF upload, text extraction, and chunking. Embeddings and OpenAI are not wired yet.",
    version="0.2.0",
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
    Accept a PDF, save it, extract text, chunk text, return summary fields.

    - Rejects non-PDF content types.
    - Saves with a unique name to avoid collisions and unsafe filenames.
    """
    # FastAPI gives us the client's declared content type and original filename.
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    original_name = file.filename or "document.pdf"

    # Validate: must look like a PDF by MIME type or by file extension as a fallback.
    ext_ok = original_name.lower().endswith(".pdf")
    type_ok = content_type in ALLOWED_PDF_CONTENT_TYPES
    if not (type_ok or ext_ok):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Send a file with content-type application/pdf or a .pdf name.",
        )

    # Build a safe, unique filename (never trust raw user filenames for the path).
    suffix = ".pdf" if not original_name.lower().endswith(".pdf") else ""
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_path = UPLOAD_DIR / unique_name

    # Stream bytes to disk instead of loading the whole file into RAM at once.
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

    # --- Phase 2: read text from the saved PDF -----------------------------
    try:
        full_text = extract_text_from_pdf(str(dest_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        # Invalid PDF or per-page extraction failure — client can retry with a valid file.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- Phase 3: split into overlapping chunks (ready for future embeddings) ---
    text_chunks = chunk_text(full_text)

    # First 500 characters for a quick UI / API sanity check without sending the whole doc.
    preview_limit = 500
    text_preview = full_text[:preview_limit]

    return UploadProcessResponse(
        message="File uploaded and processed successfully",
        saved_as=unique_name,
        text_preview=text_preview,
        total_characters=len(full_text),
        total_chunks=len(text_chunks),
    )
