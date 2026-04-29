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

## Publish to GitHub

GitHub CLI (`gh`) should be installed. From this folder, sign in once (browser or token), then create the remote repo and push:

```powershell
gh auth login
cd "e:\Projects\DocMind AI"
gh repo create docmind-ai --public --source=. --remote=origin --push
```

Use another repo name instead of `docmind-ai` if you prefer. If the repo already exists on GitHub, add the remote and push:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/docmind-ai.git
git push -u origin main
```
