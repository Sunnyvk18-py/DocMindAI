import { useState } from "react";
import { askQuestion, formatApiError } from "../services/api.js";

/**
 * Simple Q&A UI: each question is sent to POST /ask with the current document_id.
 * We keep an array of past turns so the user sees a short conversation history.
 */
export default function Chat({ documentId, disabled }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAsk(e) {
    e.preventDefault();
    setError("");
    if (!documentId) {
      setError("Upload a PDF first — there is no document_id yet.");
      return;
    }
    const q = question.trim();
    if (!q) {
      setError("Please type a question.");
      return;
    }

    setLoading(true);
    try {
      const data = await askQuestion(documentId, q);
      // Stable id for React keys (crypto.randomUUID is missing in some older browsers).
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      // Show the model answer; source_chunks are optional context for power users.
      setHistory((prev) => [
        ...prev,
        {
          id,
          question: q,
          answer: data.answer,
          sources: data.source_chunks || [],
        },
      ]);
      setQuestion("");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }

  const blocked = disabled || !documentId;

  return (
    <section className="card" aria-labelledby="chat-heading">
      <h2 id="chat-heading">Ask questions</h2>
      <p className="muted">
        Step 3: ask about the uploaded PDF. Answers use retrieved passages from your document.
      </p>

      <form onSubmit={handleAsk} className="stack">
        <label className="label" htmlFor="question-input">
          Your question
        </label>
        <textarea
          id="question-input"
          className="textarea"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What is the main conclusion?"
          disabled={blocked || loading}
        />
        <button type="submit" className="btn primary" disabled={blocked || loading}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error ? <p className="error">{error}</p> : null}

      <div className="chat-log" aria-live="polite">
        {history.length === 0 ? (
          <p className="muted">No messages yet.</p>
        ) : (
          history.map((item) => (
            <article key={item.id} className="chat-turn">
              <p className="chat-q">
                <strong>You:</strong> {item.question}
              </p>
              <p className="chat-a">
                <strong>DocMind:</strong> {item.answer}
              </p>
              {item.sources?.length ? (
                <details className="sources">
                  <summary>Source passages used</summary>
                  <ol>
                    {item.sources.map((s, i) => (
                      <li key={i} className="source-snippet">
                        {s}
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
