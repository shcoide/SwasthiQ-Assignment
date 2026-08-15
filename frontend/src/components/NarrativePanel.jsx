import { useEffect, useState } from "react";
import { getNarrative } from "../api/client.js";

export default function NarrativePanel({ clinicId, date, refreshToken }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    getNarrative(clinicId, date)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clinicId, date, refreshToken, generation]);

  const tracedEntries = result?.traced_figures ? Object.entries(result.traced_figures) : [];

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">AI Narrative Summary</h1>
        <p className="page-subtitle">
          {clinicId} · {date} · grounded strictly in the deterministic report
        </p>
      </div>

      <button
        className="generate-button"
        onClick={() => setGeneration((n) => n + 1)}
        disabled={loading}
      >
        {loading ? "Generating…" : "Regenerate narrative"}
      </button>

      {error && <div className="banner banner-error">{error}</div>}
      {loading && <div className="banner banner-loading">Asking Claude for a grounded summary…</div>}

      {result?.error && <div className="banner banner-error">{result.error}</div>}

      {result && (
        <div className="narrative-grid">
          <div>
            <div className="whatsapp-frame">
              {result.narrative ? (
                <div className="whatsapp-bubble">{result.narrative}</div>
              ) : (
                <div className="empty-state">
                  No narrative available — see the error above. The deterministic report
                  numbers are still accurate and shown in Reconciliation / Analytics.
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">Traced figures</h2>
            {tracedEntries.length === 0 ? (
              <div className="empty-state">
                {result.narrative
                  ? "No numeric figures were found in this narrative."
                  : "Nothing to trace — no narrative was generated."}
              </div>
            ) : (
              <div className="traced-figures-list">
                {tracedEntries.map(([number, source]) => (
                  <div className="traced-figure-row" key={`${number}-${source}`}>
                    <span className="traced-figure-number">{number}</span>
                    <span className="traced-figure-source">{source}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
