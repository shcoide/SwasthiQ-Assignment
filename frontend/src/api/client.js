const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      body?.detail ? summarizeDetail(body.detail) : `Request failed (${response.status})`,
    );
    error.status = response.status;
    error.detail = body?.detail;
    throw error;
  }

  return body;
}

function summarizeDetail(detail) {
  if (typeof detail === "string") return detail;
  if (detail?.errors) {
    return detail.errors
      .map((e) => `row ${e.row_index}: ${e.message}`)
      .join("; ");
  }
  return JSON.stringify(detail);
}

export function ingestBillingLog(rows) {
  return request("/api/billing-log", {
    method: "POST",
    body: JSON.stringify(rows),
  });
}

export function getReconciliation(clinicId, date) {
  return request(`/api/reconciliation/${encodeURIComponent(clinicId)}/${date}`);
}

export function getAnalytics(clinicId, date) {
  return request(`/api/analytics/${encodeURIComponent(clinicId)}/${date}`);
}

export function getNarrative(clinicId, date) {
  return request(`/api/narrative/${encodeURIComponent(clinicId)}/${date}`);
}
