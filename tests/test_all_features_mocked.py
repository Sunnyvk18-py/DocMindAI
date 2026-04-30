"""
End-to-end smoke test for DocMind AI (all HTTP features) with mocks.

- Patches PDF text extraction and embedding API calls so no real OpenAI key is needed.
- Uses FastAPI TestClient to hit /health, /upload, /ask, /summary, /quiz once each.

Run from project root:
    pip install -r requirements.txt -r requirements-dev.txt
    pytest tests/test_all_features_mocked.py -v
"""

from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock

import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import vector_store


def _fake_embed_texts(texts: list[str]) -> np.ndarray:
    """Deterministic fake embeddings (same dim for every call) — keeps FAISS happy."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    dim = 32
    rng = np.random.default_rng(abs(hash(texts[0])) % (2**31))
    vectors = rng.standard_normal((len(texts), dim)).astype(np.float32)
    faiss.normalize_L2(vectors)
    return vectors


def _fake_extract(_path: str) -> str:
    """Long enough text to produce multiple real chunks from chunk_text()."""
    return (
        "Photosynthesis converts light energy into chemical energy in plants. "
        "Chlorophyll absorbs mostly blue and red wavelengths. "
        "The Calvin cycle fixes carbon dioxide into sugars. "
        "Stomata regulate gas exchange and water loss. "
        * 40
    )


def _make_fake_openai_client() -> MagicMock:
    """Return a mock OpenAI client whose chat.completions.create returns valid shapes."""

    def fake_create(
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        system = messages[0]["content"]
        user = messages[-1]["content"]

        class Msg:
            def __init__(self, content: str) -> None:
                self.content = content

        class Choice:
            def __init__(self, content: str) -> None:
                self.message = Msg(content)

        class Resp:
            def __init__(self, content: str) -> None:
                self.choices = [Choice(content)]

        if response_format and response_format.get("type") == "json_object":
            if "quiz" in system.lower() or "question/answer" in system.lower():
                match = re.search(r"Generate exactly (\d+) question", user)
                n = int(match.group(1)) if match else 5
                n = max(1, min(n, 25))
                questions = [
                    {"question": f"Question {i + 1} about the passage?", "answer": f"Answer {i + 1}."}
                    for i in range(n)
                ]
                payload = {"questions": questions}
                return Resp(json.dumps(payload))

            payload = {
                "summary": "This document explains photosynthesis and related plant biology.",
                "key_points": [
                    "Light energy drives photosynthesis.",
                    "Chlorophyll captures specific wavelengths.",
                    "The Calvin cycle produces sugars.",
                ],
                "important_concepts": ["photosynthesis", "chlorophyll", "Calvin cycle", "stomata"],
            }
            return Resp(json.dumps(payload))

        return Resp("Photosynthesis is how plants turn light into chemical energy, per the passages.")

    client = MagicMock()
    client.chat.completions.create.side_effect = fake_create
    return client


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fresh app client with in-memory stores cleared and OpenAI/embeddings mocked."""
    app_module.DOCUMENTS.clear()
    vector_store._STORE.clear()
    vector_store._client = None  # noqa: SLF001 — reset singleton between tests

    monkeypatch.setattr(vector_store, "_embed_texts", _fake_embed_texts)
    monkeypatch.setattr(app_module, "extract_text_from_pdf", _fake_extract)
    monkeypatch.setattr(app_module, "get_openai_client", _make_fake_openai_client)

    with TestClient(app_module.app) as c:
        yield c

    app_module.DOCUMENTS.clear()
    vector_store._STORE.clear()
    vector_store._client = None  # noqa: SLF001


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_upload_ask_summary_quiz_flow(client: TestClient) -> None:
    # Minimal PDF header so the file looks like a PDF on disk (parser is mocked anyway).
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

    up = client.post(
        "/upload",
        files={"file": ("biology_notes.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert "document_id" in body
    assert body["total_chunks"] > 0
    doc_id = body["document_id"]

    ask = client.post("/ask", json={"document_id": doc_id, "question": "What is photosynthesis?"})
    assert ask.status_code == 200, ask.text
    ask_j = ask.json()
    assert "answer" in ask_j and ask_j["answer"]
    assert isinstance(ask_j.get("source_chunks"), list)

    summ = client.post("/summary", json={"document_id": doc_id})
    assert summ.status_code == 200, summ.text
    sj = summ.json()
    assert sj["summary"]
    assert len(sj["key_points"]) >= 1
    assert len(sj["important_concepts"]) >= 1

    quiz = client.post("/quiz", json={"document_id": doc_id, "num_questions": 3})
    assert quiz.status_code == 200, quiz.text
    qj = quiz.json()
    assert "questions" in qj
    assert len(qj["questions"]) == 3
    assert all("question" in q and "answer" in q for q in qj["questions"])


def test_unknown_document_errors(client: TestClient) -> None:
    r = client.post("/ask", json={"document_id": "00000000-0000-0000-0000-000000000000", "question": "Hi?"})
    assert r.status_code == 404
