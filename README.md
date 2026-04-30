# DocMind AI

FastAPI **MVP**: upload a PDF, extract text, chunk it, build **OpenAI embeddings + FAISS** in memory, then **ask questions** with a small RAG loop (retrieve → chat). Data is lost when the server stops.

## Project layout

| Path | Role |
|------|------|
| `backend/app.py` | FastAPI: `/health`, `/upload`, `/ask` + in-memory `DOCUMENTS` registry |
| `backend/parser.py` | `extract_text_from_pdf()` — pypdf |
| `backend/chunker.py` | `chunk_text()` — overlapping windows |
| `backend/vector_store.py` | Embeddings, FAISS index, `search_similar_chunks()` |
| `uploads/` | Saved PDF files |
| `requirements.txt` | Dependencies |
| `.env.example` | Template for secrets (copy to `.env`) |

## Setup

### 1. Virtual environment and packages

```bash
python -m venv .venv
```

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

### 2. OpenAI API key (`.env`)

1. Copy the example env file to `.env` in the **project root** (same folder as `requirements.txt`):

   ```bash
   copy .env.example .env
   ```

   On macOS/Linux: `cp .env.example .env`

2. Edit `.env` and set your real key:

   ```env
   OPENAI_API_KEY=sk-...your-key...
   ```

   Optional overrides:

   ```env
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   OPENAI_CHAT_MODEL=gpt-4o-mini
   ```

3. **Never commit `.env`** — it is listed in `.gitignore`. Only `.env.example` is safe to share.

Without a valid key, `/upload` (embedding step) and `/ask` return **503** with a short message.

## Run the server

From the **project root**:

```bash
uvicorn backend.app:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status": "ok"}` |
| POST | `/upload` | Multipart **`file`**: PDF → save → extract → chunk → embed + FAISS |
| POST | `/ask` | JSON: `document_id`, `question` → retrieve top chunks → OpenAI chat |

### `POST /upload` response

- `message`, `document_id` (use with `/ask`), `saved_as`, `text_preview`, `total_characters`, `total_chunks`

### `POST /ask` body

```json
{
  "document_id": "uuid-from-upload-response",
  "question": "What is the main topic?"
}
```

### `POST /ask` response

- `answer` — model reply  
- `source_chunks` — passages retrieved as context (transparency / debugging)

## Publish to GitHub

```powershell
gh auth login
cd "e:\Projects\DocMind AI"
git remote add origin https://github.com/Sunnyvk18-py/DocMindAI.git
git push -u origin main
```

If `origin` exists: `git remote set-url origin https://github.com/Sunnyvk18-py/DocMindAI.git` then `git push`.
