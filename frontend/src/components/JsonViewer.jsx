import { useState } from "react";

export default function JsonViewer({ data }) {
  const [open, setOpen] = useState(false);
  
  if (!data) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <button onClick={() => setOpen(!open)} style={{
        background: "none", border: "1px solid #1e293b", borderRadius: 8,
        color: "#94a3b8", padding: "8px 12px", fontSize: 12, cursor: "pointer", width: "100%"
      }}>
        {open ? "▼ Hide Raw JSON" : "▶ Show Raw JSON"}
      </button>
      {open && (
        <pre style={{
          background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8,
          padding: 16, fontSize: 11, color: "#38bdf8", overflowX: "auto", marginTop: 8
        }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}