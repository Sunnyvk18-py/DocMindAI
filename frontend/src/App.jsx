import { useEffect, useState } from "react";
import Upload from "./components/Upload.jsx";
import Chat from "./components/Chat.jsx";
import Summary from "./components/Summary.jsx";
import Quiz from "./components/Quiz.jsx";
import { checkHealth, formatApiError } from "./services/api.js";

/**
 * Top-level layout:
 * - Keeps `documentId` in React state after a successful upload.
 * - Passes that id into Chat / Summary / Quiz so every API call targets the same PDF.
 * - Optional /health ping on load to surface backend connectivity early.
 */
export default function App() {
  const [documentId, setDocumentId] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await checkHealth();
        if (!cancelled && h?.status === "ok") setBackendStatus("ok");
        else if (!cancelled) setBackendStatus("unknown");
      } catch (e) {
        if (!cancelled) setBackendStatus(`error: ${formatApiError(e)}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // After a new upload, parent stores the latest id; child components read it from props.
  function handleDocumentReady(id) {
    setDocumentId(id || null);
  }

  const hasDoc = Boolean(documentId);
  const sectionsDisabled = !hasDoc;

  return (
    <div className="page">
      <header className="hero">
        <h1>DocMind AI</h1>
        <p className="tagline">Upload a PDF, then ask questions, summarize, and quiz yourself.</p>
        <p className={`backend-pill ${backendStatus === "ok" ? "ok" : "warn"}`}>
          Backend:{" "}
          {backendStatus === "checking"
            ? "Checking..."
            : backendStatus === "ok"
              ? "Connected (GET /health)"
              : backendStatus}
        </p>
      </header>

      <main className="layout">
        <Upload documentId={documentId} onDocumentReady={handleDocumentReady} disabled={false} />

        <Chat documentId={documentId} disabled={sectionsDisabled} />
        <Summary documentId={documentId} disabled={sectionsDisabled} />
        <Quiz documentId={documentId} disabled={sectionsDisabled} />

        {sectionsDisabled ? (
          <p className="hint card">Upload a PDF above to enable Ask, Summary, and Quiz for this session.</p>
        ) : null}
      </main>

      <footer className="footer muted">
        API base: <code>http://127.0.0.1:8000</code> — start the FastAPI server before using this UI.
      </footer>
    </div>
  );
}
