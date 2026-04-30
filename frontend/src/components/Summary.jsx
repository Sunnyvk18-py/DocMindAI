import { useState } from "react";
import { generateSummary, formatApiError } from "../services/api.js";

/**
 * Calls POST /summary once when the user clicks the button, then renders
 * the structured JSON: summary, key_points, important_concepts.
 */
export default function Summary({ documentId, disabled }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  async function handleGenerate() {
    setError("");
    setData(null);
    if (!documentId) {
      setError("Upload a PDF first — there is no document_id yet.");
      return;
    }
    setLoading(true);
    try {
      const res = await generateSummary(documentId);
      setData(res);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  const blocked = disabled || !documentId;

  return (
    <section className="card" aria-labelledby="summary-heading">
      <h2 id="summary-heading">Summary</h2>
      <p className="muted">Step 4: generate a concise study summary from your PDF chunks.</p>

      <button type="button" className="btn secondary" disabled={blocked || loading} onClick={handleGenerate}>
        {loading ? "Generating..." : "Generate Summary"}
      </button>

      {error ? <p className="error">{error}</p> : null}

      {data ? (
        <div className="summary-output stack">
          <div>
            <h3>Summary</h3>
            <p>{data.summary}</p>
          </div>
          <div>
            <h3>Key points</h3>
            <ul>
              {(data.key_points || []).map((pt, i) => (
                <li key={i}>{pt}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Important concepts</h3>
            <ul className="pill-list">
              {(data.important_concepts || []).map((c, i) => (
                <li key={i}>
                  <span className="pill">{c}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
