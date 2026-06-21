// Override at build/deploy time with VITE_API_URL (e.g. your hosted backend).
export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function jsonOrThrow(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function analyze(payload) {
  const res = await fetch(`${API}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function generate(payload) {
  const res = await fetch(`${API}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function getJob(jobId) {
  const res = await fetch(`${API}/jobs/${jobId}`);
  return jsonOrThrow(res);
}

export async function getReview(shareToken) {
  const res = await fetch(`${API}/reviews/${shareToken}`);
  return jsonOrThrow(res);
}

export async function refinePlacement(payload) {
  const res = await fetch(`${API}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export const mediaUrl = (path) => (path ? `${API}${path}` : null);
