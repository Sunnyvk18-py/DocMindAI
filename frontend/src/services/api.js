/**
 * Central place for all HTTP calls to the DocMind AI FastAPI backend.
 * Axios is configured once with the base URL so components stay simple.
 */
import axios from "axios";

/** Backend base URL — must match `uvicorn` host/port. */
const API_BASE = "http://127.0.0.1:8000";

const client = axios.create({
  baseURL: API_BASE,
  // PDF upload + OpenAI can take a while; avoid aborting too early.
  timeout: 120_000,
});

/**
 * Turn FastAPI / Axios errors into a short string for the UI.
 * FastAPI often sends `{ "detail": "..." }` or `{ "detail": [...] }`.
 */
export function formatApiError(error) {
  if (axios.isAxiosError(error)) {
    const d = error.response?.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
    }
    if (d && typeof d === "object") return JSON.stringify(d);
    if (error.response?.status) {
      return `Request failed (${error.response.status})`;
    }
  }
  return error?.message || "Something went wrong.";
}

/**
 * POST /upload — multipart form with field name "file" (matches FastAPI).
 * @param {File} file — browser File from <input type="file">
 */
export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/**
 * POST /ask — RAG-style question about one uploaded document.
 */
export async function askQuestion(documentId, question) {
  const { data } = await client.post("/ask", {
    document_id: documentId,
    question,
  });
  return data;
}

/**
 * POST /summary — structured summary for one document.
 */
export async function generateSummary(documentId) {
  const { data } = await client.post("/summary", {
    document_id: documentId,
  });
  return data;
}

/**
 * POST /quiz — generate multiple choice-style Q&A from the document.
 * @param {string} documentId
 * @param {number} [numQuestions=5] — backend allows 1–25
 */
export async function generateQuiz(documentId, numQuestions = 5) {
  const { data } = await client.post("/quiz", {
    document_id: documentId,
    num_questions: numQuestions,
  });
  return data;
}

/** GET /health — optional connectivity check. */
export async function checkHealth() {
  const { data } = await client.get("/health");
  return data;
}
