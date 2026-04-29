# DocMind AI

FastAPI service: **PDF upload**, **text extraction** (pypdf), and **overlapping chunks** (for future embeddings / RAG). No OpenAI or embeddings yet.

## Project layout

| Path | Role |
|------|------|
| `backend/app.py` | FastAPI app: `/health`, `/upload` |
| `backend/parser.py` | `extract_text_from_pdf()` — reads all pages with pypdf |
| `backend/chunker.py` | `chunk_text()` — sliding windows for LLM-sized pieces |
| `uploads/` | Saved PDF files |
| `requirements.txt` | Python dependencies |

## Setup

1. Create a virtual environment (recommended):

   ```bash
   python -m venv .venv
   ```

2. Activate it:

   - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   - **macOS / Linux:** `source .venv/bin/activate`

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run the server

From the **project root** (the folder that contains `backend/` and `uploads/`):

```bash
uvicorn backend.app:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for Swagger UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status": "ok"}` |
| POST | `/upload` | Multipart field **`file`**: validate PDF → save → extract text → chunk → JSON summary |

### `POST /upload` response

After a successful upload you get:

- `message` — status text  
- `saved_as` — unique filename in `uploads/`  
- `text_preview` — first 500 characters of extracted text  
- `total_characters` — full extracted length  
- `total_chunks` — count of non-empty overlapping chunks (defaults: 1000 chars, 200 overlap in `chunk_text`)

Invalid or unreadable PDFs after save return **400** with a `detail` string from the parser.

## Publish to GitHub

Sign in once:

```powershell
gh auth login
```

From this project folder (adjust path if yours differs):

```powershell
cd "e:\Projects\DocMind AI"
git remote add origin https://github.com/Sunnyvk18-py/DocMindAI.git
git push -u origin main
```

If `origin` already exists, use `git remote set-url origin https://github.com/Sunnyvk18-py/DocMindAI.git` then `git push`.

To create a **new** repo and push in one step:

```powershell
gh repo create docmind-ai --public --source=. --remote=origin --push
```
