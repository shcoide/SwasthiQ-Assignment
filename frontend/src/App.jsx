import { useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import ReconciliationDashboard from "./components/ReconciliationDashboard.jsx";
import Analytics from "./components/Analytics.jsx";
import NarrativePanel from "./components/NarrativePanel.jsx";
import { ingestBillingLog } from "./api/client.js";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function App() {
  const [clinicId, setClinicId] = useState("clinic-1");
  const [date, setDate] = useState(todayISO());
  const [uploadStatus, setUploadStatus] = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const fileInputRef = useRef(null);

  async function handleFileSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploadStatus({ type: "loading", message: "Uploading billing log…" });
    try {
      const text = await file.text();
      const rows = JSON.parse(text);
      const result = await ingestBillingLog(rows);
      setClinicId(result.clinic_id);
      setDate(result.date);
      setUploadStatus({
        type: "success",
        message: `Ingested ${result.rows_ingested} rows for ${result.clinic_id} on ${result.date}.`,
      });
      setRefreshToken((n) => n + 1);
    } catch (err) {
      setUploadStatus({ type: "error", message: err.message || "Upload failed." });
    }
  }

  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <div className="main">
          <div className="topbar">
            <div className="topbar-field">
              <label htmlFor="clinic-id-input">Clinic ID</label>
              <input
                id="clinic-id-input"
                value={clinicId}
                onChange={(e) => setClinicId(e.target.value)}
              />
            </div>
            <div className="topbar-field">
              <label htmlFor="date-input">Date</label>
              <input
                id="date-input"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="topbar-spacer" />
            {uploadStatus && (
              <span
                className={`topbar-status${
                  uploadStatus.type === "error"
                    ? " is-error"
                    : uploadStatus.type === "success"
                      ? " is-success"
                      : ""
                }`}
              >
                {uploadStatus.message}
              </span>
            )}
            <button className="upload-button" onClick={() => fileInputRef.current?.click()}>
              Upload billing log (JSON)
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json"
              hidden
              onChange={handleFileSelected}
            />
          </div>

          <Routes>
            <Route path="/" element={<Navigate to="/reconciliation" replace />} />
            <Route
              path="/reconciliation"
              element={<ReconciliationDashboard clinicId={clinicId} date={date} refreshToken={refreshToken} />}
            />
            <Route
              path="/analytics"
              element={<Analytics clinicId={clinicId} date={date} refreshToken={refreshToken} />}
            />
            <Route
              path="/narrative"
              element={<NarrativePanel clinicId={clinicId} date={date} refreshToken={refreshToken} />}
            />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
