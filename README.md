# DocMind AI

Phase 1: PDF file upload API built with FastAPI.

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

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive API (Swagger UI).

## Endpoints

| Method | Path      | Description                    |
| ------ | --------- | ------------------------------ |
| GET    | `/health` | Returns `{"status": "ok"}`     |
| POST   | `/upload` | Upload a PDF (multipart form)  |

Uploaded PDFs are stored under the `uploads/` directory.
