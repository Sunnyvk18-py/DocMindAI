# DocMind AI

**DocMind AI** is a small **study assistant API** for PDFs: you upload a document, it extracts text, splits it into overlapping chunks, builds **OpenAI embeddings** with a **FAISS** index in memory, then you can **ask questions**, get a **structured summary**, and generate a **quiz** — all scoped to one `document_id` at a time.

This is an **MVP**: data lives in RAM and is lost when the server stops. It is not hardened for production (no auth, no durable vector DB).

## Features

| Feature | What it does |
|--------|----------------|
| **PDF upload** | Validates PDF, saves under `uploads/`, extracts text with **pypdf** |
| **Chunking** | Overlapping text windows for LLM-sized segments |
| **Embeddings + search** | **OpenAI** embeddings + **FAISS** similarity search per document |
| **Q&A (`/ask`)** | Retrieves top chunks for your question, then **chat completion** |
| **Summary (`/summary`)** | Retrieves “important” passages, returns **summary**, **key points**, **concepts** (JSON from the model) |
| **Quiz (`/quiz`)** | Builds a **question + answer** list from document content (JSON) |

## Tech stack

- **Python**, **FastAPI**, **Uvicorn**
- **pypdf** — PDF text extraction
- **OpenAI API** — embeddings + chat (JSON mode for study endpoints)
- **faiss-cpu**, **numpy** — vector index and search
- **python-dotenv** — load `OPENAI_API_KEY` from `.env`

## Project layout

| Path | Role |
|------|------|
| `backend/app.py` | Routes, in-memory `DOCUMENTS` registry |
| `backend/parser.py` | `extract_text_from_pdf()` |
| `backend/chunker.py` | `chunk_text()` |
| `backend/vector_store.py` | Embeddings, FAISS, `search_similar_chunks()` |
| `uploads/` | Saved PDFs |
| `.env.example` | Copy to `.env` and set your API key |

## Setup

### 1. Virtual environment and dependencies

```bash
python -m venv .venv
```

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`  
- **macOS / Linux:** `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

### 2. OpenAI API key

1. Copy `.env.example` to `.env` in the **project root**:

   ```powershell
   copy .env.example .env
   ```

   On macOS/Linux: `cp .env.example .env`

2. Edit `.env`:

   ```env
   OPENAI_API_KEY=sk-...your-key...
   ```

   Optional:

   ```env
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   OPENAI_CHAT_MODEL=gpt-4o-mini
   ```

Do **not** commit `.env`. `.env.example` is safe to share.

## How to run

From the **project root** (folder that contains `backend/` and `uploads/`):

```bash
uvicorn backend.app:app --reload
```

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"status": "ok"}` |
| `POST` | `/upload` | Form field **`file`**: PDF → save → extract → chunk → embed + index |
| `POST` | `/ask` | JSON: `document_id`, `question` → answer + `source_chunks` |
| `POST` | `/summary` | JSON: `document_id` → `summary`, `key_points`, `important_concepts` |
| `POST` | `/quiz` | JSON: `document_id`, `num_questions` (1–25, default 5) → up to that many `questions[]` entries (`question` / `answer`; the model may return fewer on very short docs) |

### Error handling (common cases)

| Situation | Typical HTTP code | `detail` (summary) |
|-----------|-------------------|---------------------|
| Unknown `document_id` | **404** | Upload first; id not in server memory |
| Empty / unreadable PDF (no indexed text) | **400** | No extractable text or no chunks |
| Missing / placeholder API key | **503** | Set `OPENAI_API_KEY` in `.env` |
| OpenAI or JSON parse failures | **502** | Upstream or invalid JSON shape |

## Example workflow

1. **Upload a PDF**  
   `POST /upload` with multipart field **`file`**.  
   Response includes **`document_id`** (save it).

2. **Ask a question**  
   `POST /ask` with:

   ```json
   { "document_id": "<paste-id>", "question": "What is the main idea of section 2?" }
   ```

3. **Generate a summary**  
   `POST /summary` with:

   ```json
   { "document_id": "<paste-id>" }
   ```

4. **Generate a quiz**  
   `POST /quiz` with:

   ```json
   { "document_id": "<paste-id>", "num_questions": 5 }
   ```

5. Repeat **ask / summary / quiz** with the same `document_id` until you restart the server (in-memory state clears).

## Publish to GitHub

```powershell
gh auth login
cd "e:\Projects\DocMind AI"
git remote add origin https://github.com/Sunnyvk18-py/DocMindAI.git
git push -u origin main
```

If `origin` already exists: `git remote set-url origin https://github.com/Sunnyvk18-py/DocMindAI.git` then `git push`.
