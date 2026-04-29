"""
DocMind AI — FastAPI application (Phase 1: file upload).

Run from the project root:
    uvicorn backend.app:app --reload
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

# --- Paths -----------------------------------------------------------------
# This file lives in backend/, so the project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"

# Allowed MIME type for PDF uploads (browsers usually send this for .pdf files).
ALLOWED_PDF_CONTENT_TYPES = frozenset({"application/pdf"})

# --- App -------------------------------------------------------------------
app = FastAPI(
    title="DocMind AI",
    description="Phase 1: PDF upload API. Embeddings and parsing come later.",
    version="0.1.0",
)


@app.on_event("startup")
def ensure_upload_dir() -> None:
    """Create the uploads folder on disk if it does not exist yet."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for load balancers and quick manual tests."""
    return {"status": "ok"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Accept a single PDF file, validate it, save under uploads/, return a message.

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

    return {
        "message": "File uploaded successfully",
        "saved_as": unique_name,
    }
