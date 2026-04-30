import { useState } from "react";
import { generateQuiz, formatApiError } from "../services/api.js";

/**
 * Calls POST /quiz and displays each generated question with its answer underneath.
 * Answers are model-written — treat as study aids and verify against the PDF when needed.
 */
export default function Quiz({ documentId, disabled }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState([]);

  async function handleGenerate() {
    setError("");
    setItems([]);
    if (!documentId) {
      setError("Upload a PDF first — there is no document_id yet.");
      return;
    }
    setLoading(true);
    try {
      // Uses default num_questions=5 on the API unless you extend this UI.
      const res = await generateQuiz(documentId, 5);
      setItems(res.questions || []);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  const blocked = disabled || !documentId;

  return (
    <section className="card" aria-labelledby="quiz-heading">
      <h2 id="quiz-heading">Quiz</h2>
      <p className="muted">Step 5: auto-generate study questions (with answers) from your document.</p>

      <button type="button" className="btn secondary" disabled={blocked || loading} onClick={handleGenerate}>
        {loading ? "Generating..." : "Generate Quiz"}
      </button>

      {error ? <p className="error">{error}</p> : null}

      {items.length ? (
        <ol className="quiz-list">
          {items.map((q, idx) => (
            <li key={idx} className="quiz-item">
              <p className="quiz-question">
                <strong>Q{idx + 1}.</strong> {q.question}
              </p>
              <p className="quiz-answer">
                <strong>Answer:</strong> {q.answer}
              </p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
