import { useEffect, useState } from "react";
import { getAnalytics } from "../api/client.js";
import { formatHour, formatPaiseAsRupees } from "../utils/money.js";

export default function Analytics({ clinicId, date, refreshToken }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAnalytics(clinicId, date)
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
        <h1 className="page-title">Analytics</h1>
        <p className="page-subtitle">
          {clinicId} · {date}
        </p>
      </div>

      {error && <div className="banner banner-error">{error}</div>}
      {loading && <div className="banner banner-loading">Loading analytics…</div>}

      {report && (
        <>
          <RevenueByHourChart data={report.revenue_by_hour} />

          <div className="rankings-grid">
            <MedicineRanking
              title="Top medicines by quantity"
              rows={report.top_medicines_by_quantity}
              valueKey="total_qty"
              formatValue={(v) => `${v} unit${v === 1 ? "" : "s"}`}
            />
            <MedicineRanking
              title="Top medicines by revenue"
              rows={report.top_medicines_by_revenue}
              valueKey="total_revenue_paise"
              formatValue={formatPaiseAsRupees}
            />
          </div>
        </>
      )}
    </div>
  );
}

function RevenueByHourChart({ data }) {
  const buckets = data.buckets;
  const max = Math.max(1, ...buckets.map((b) => Math.abs(b.revenue_paise)));

  return (
    <div className="card">
      <h2 className="card-title">
        Revenue by hour of day
        {data.peak_hour !== null && (
          <span className="peak-hour-badge">Peak: {formatHour(data.peak_hour)}</span>
        )}
      </h2>
      {buckets.every((b) => b.revenue_paise === 0) ? (
        <div className="empty-state">No revenue recorded for this clinic-day.</div>
      ) : (
        <div className="bar-chart">
          {buckets.map((bucket) => {
            const heightPct = Math.max(2, (Math.abs(bucket.revenue_paise) / max) * 100);
            return (
              <div className="bar-chart-col" key={bucket.hour}>
                <div className="bar-chart-tooltip">
                  {formatHour(bucket.hour)} · {formatPaiseAsRupees(bucket.revenue_paise)}
                </div>
                <div
                  className={`bar-chart-bar${bucket.revenue_paise !== 0 ? " has-value" : ""}${
                    bucket.hour === data.peak_hour ? " is-peak" : ""
                  }`}
                  style={{ height: `${heightPct}%` }}
                />
                {bucket.hour % 3 === 0 && <div className="bar-chart-label">{bucket.hour}</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MedicineRanking({ title, rows, valueKey, formatValue }) {
  return (
    <div className="card">
      <h2 className="card-title">{title}</h2>
      {rows.length === 0 ? (
        <div className="empty-state">No medicine sales recorded.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th></th>
              <th style={{ textAlign: "left" }}>Medicine</th>
              <th>{title.includes("quantity") ? "Quantity" : "Revenue"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.drug_name}>
                <td className="rank">{index + 1}</td>
                <td style={{ textAlign: "left" }}>{row.drug_name}</td>
                <td>{formatValue(row[valueKey])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
