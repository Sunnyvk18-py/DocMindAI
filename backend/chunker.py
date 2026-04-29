"""
Text chunking for DocMind AI (Phase 3).

Why chunking matters for LLM / RAG:
- Models have a **context window** (max tokens they can see at once). Long
  documents must be split into smaller pieces that fit inside that window.
- **Retrieval** (RAG) works on chunks: the system embeds or indexes each chunk,
  then retrieves the most relevant chunks for a user question instead of
  stuffing the whole book into the prompt every time.
- **Overlap** between chunks helps preserve sentences or terms that would
  otherwise be cut in half at a boundary, so context is less likely to be lost.
"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Split a long string into overlapping segments for downstream LLM/RAG use.

    Args:
        text: Full document text (e.g. output of extract_text_from_pdf).
        chunk_size: Target maximum characters per chunk (must be positive).
        overlap: How many characters the next chunk shares with the previous
            one. Must be less than chunk_size so the window keeps moving forward.

    Returns:
        List of non-empty chunks (empty or whitespace-only segments are skipped).
    """
    if chunk_size <= 0:
        return []
    if overlap < 0:
        overlap = 0
    # If overlap >= chunk_size, the step size would be zero or negative → infinite loop.
    if overlap >= chunk_size:
        overlap = max(0, chunk_size - 1)

    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)
    # Step forward by (chunk_size - overlap) so consecutive chunks share `overlap` chars.
    step = chunk_size - overlap

    while start < length:
        end = min(start + chunk_size, length)
        piece = text[start:end]
        if piece.strip():
            chunks.append(piece)
        if end >= length:
            break
        start += step

    return chunks
