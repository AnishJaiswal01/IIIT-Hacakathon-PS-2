export default function PipelineSteps({ loading, analysis }) {
  const steps = [
    { id: 1, label: "Upload Image", active: true, done: !!analysis || loading },
    { id: 2, label: "Claude Vision Parse", active: loading, done: !!analysis },
    { id: 3, label: "Build 3D Model", active: !!analysis, done: !!analysis }
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
      {steps.map(s => (
        <div key={s.id} style={{
          display: "flex", gap: 10, alignItems: "center", padding: "10px 12px",
          background: s.active ? "#1e293b" : "transparent",
          border: `1px solid ${s.active ? "#6366f1" : s.done ? "#22c55e" : "#0f172a"}`,
          borderRadius: 8
        }}>
          <span style={{ color: s.done ? "#22c55e" : s.active ? "#818cf8" : "#475569" }}>
            {s.done ? "✓" : s.active ? "⚙" : "○"}
          </span>
          <span style={{ fontSize: 13, color: s.done || s.active ? "#e2e8f0" : "#475569" }}>
            {s.label}
          </span>
        </div>
      ))}
    </div>
  );
}