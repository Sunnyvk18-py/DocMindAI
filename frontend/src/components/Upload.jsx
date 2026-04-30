import { useRef, useState } from "react";
import { uploadFile, formatApiError } from "../services/api.js";

/**
 * Lets the user pick a PDF, upload it to POST /upload, and notifies the parent
 * with the new document_id so Chat / Summary / Quiz can run.
 */
export default function Upload({ documentId, onDocumentReady, disabled }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleUpload() {
    setError("");
    setMessage("");
    const input = inputRef.current;
    if (!input?.files?.length) {
      setError("Please choose a PDF file first.");
      return;
    }
    const file = input.files[0];
    // Client-side guard: only .pdf (MIME types vary by OS/browser).
    // Many browsers send application/pdf; some send octet-stream — rely on .pdf name.
    const nameOk = file.name.toLowerCase().endsWith(".pdf");
    if (!nameOk) {
      setError("Only PDF files are allowed. Pick a file that ends with .pdf.");
      return;
    }

    setUploading(true);
    try {
      const data = await uploadFile(file);
      // FastAPI returns document_id after processing (embeddings + index).
      onDocumentReady(data.document_id);
      setMessage(data.message || "Upload complete.");
    } catch (e) {
      onDocumentReady(null);
      setError(formatApiError(e));
    } finally {
      setUploading(false);
    }
  }

  const busy = uploading || disabled;

  return (
    <section className="card" aria-labelledby="upload-heading">
      <h2 id="upload-heading">Upload PDF</h2>
      <p className="muted">
        Step 1: choose a PDF, then upload. The backend returns a{" "}
        <code>document_id</code> used for Ask, Summary, and Quiz.
      </p>

      <div className="row">
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          disabled={busy}
          className="file-input"
        />
        <button type="button" className="btn primary" disabled={busy} onClick={handleUpload}>
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </div>

      {documentId ? (
        <p className="success">
          Active <code>document_id</code>: <strong>{documentId}</strong>
        </p>
      ) : null}
      {message ? <p className="success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}
