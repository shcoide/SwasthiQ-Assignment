import { useEffect, useState } from "react";
import { getReconciliation } from "../api/client.js";
import { formatPaiseAsRupees } from "../utils/money.js";

const MODE_LABELS = { cash: "Cash", card: "Card", upi: "UPI" };

export default function ReconciliationDashboard({ clinicId, date, refreshToken }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getReconciliation(clinicId, date)
      .then((data) => {
        if (!cancelled) setReport(data);
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
  }, [clinicId, date, refreshToken]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">EOD Reconciliation</h1>
        <p className="page-subtitle">
          {clinicId} · {date}
          {report ? ` · ${report.visit_count} visit${report.visit_count === 1 ? "" : "s"}` : ""}
        </p>
      </div>

      {error && <div className="banner banner-error">{error}</div>}
      {loading && <div className="banner banner-loading">Loading reconciliation…</div>}

      {report && (
        <>
          <div className="stat-grid">
            <StatCard variant="billed" label="Total Billed" paise={report.total_billed_paise} />
            <StatCard variant="collected" label="Total Collected" paise={report.total_collected_paise} />
            <StatCard variant="outstanding" label="Outstanding" paise={report.total_outstanding_paise} />
            <StatCard variant="refunds" label="Refunds" paise={report.total_refunds_paise} />
          </div>

          <div className="card">
            <h2 className="card-title">Payment mode breakdown</h2>
            {report.visit_count === 0 ? (
              <div className="empty-state">No visits recorded for this clinic-day.</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mode</th>
                    <th>Billed</th>
                    <th>Collected</th>
                    <th>Outstanding</th>
                    <th>Refunds</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.by_payment_mode).map(([mode, row]) => (
                    <tr key={mode}>
                      <td>{MODE_LABELS[mode] || mode}</td>
                      <td>{formatPaiseAsRupees(row.billed_paise)}</td>
                      <td>{formatPaiseAsRupees(row.collected_paise)}</td>
                      <td className={row.outstanding_paise < 0 ? "negative" : undefined}>
                        {formatPaiseAsRupees(row.outstanding_paise)}
                      </td>
                      <td>{formatPaiseAsRupees(row.refunds_paise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ variant, label, paise }) {
  return (
    <div className={`stat-card stat-card--${variant}`}>
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{formatPaiseAsRupees(paise)}</div>
    </div>
  );
}
