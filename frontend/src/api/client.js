const API_BASE = "http://localhost:8000";

export async function analyzePlan(file, planId) {
  const form = new FormData();
  form.append("file", file);
  
  const res = await fetch(`${API_BASE}/analyse?plan_id=${planId}`, {
    method: "POST", 
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || "Server error during analysis");
  }
  
  return await res.json();
}