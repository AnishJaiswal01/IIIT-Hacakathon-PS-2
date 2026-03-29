export default function ConcernCard({ concern }) {
  const colors = { low: "#22c55e", medium: "#f59e0b", high: "#ef4444" };
  const color = colors[concern.severity] || "#64748b";
  
  return (
    <div style={{
      background: "#0f172a", border: `1px solid ${color}44`, borderRadius: 10,
      padding: "12px 16px", marginBottom: 8
    }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <span style={{
          background: color + "22", color: color, border: `1px solid ${color}44`,
          borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600, textTransform: "uppercase"
        }}>
          {concern.severity}
        </span>
        <span style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>{concern.description}</span>
      </div>
      <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>💡 {concern.recommendation}</p>
    </div>
  );
}