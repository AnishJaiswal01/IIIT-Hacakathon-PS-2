export default function MaterialCard({ rec }) {
  return (
    <div style={{
      background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12,
      padding: 16, marginBottom: 12
    }}>
      <div style={{
        fontSize: 12, fontWeight: 700, color: "#6366f1", textTransform: "uppercase",
        letterSpacing: "0.08em", marginBottom: 12
      }}>
        {rec.element_type.replace(/_/g, " ")}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {rec.options?.map((opt) => (
          <div key={opt.rank} style={{
            background: "#1e293b", borderRadius: 8, padding: "10px 14px",
            borderLeft: `3px solid ${opt.rank === 1 ? "#6366f1" : opt.rank === 2 ? "#3b82f6" : "#475569"}`
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, background: opt.rank === 1 ? "#6366f1" : "#334155",
                  color: "white", borderRadius: 4, padding: "1px 6px"
                }}>#{opt.rank}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9" }}>{opt.material}</span>
              </div>
            </div>
            <div style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, color: "#64748b", marginBottom: 3 }}>
                Score: {opt.tradeoff_score?.toFixed(1) || "–"} / 10
              </div>
            </div>
            <p style={{ fontSize: 12, color: "#94a3b8", margin: 0, lineHeight: 1.5 }}>
              {opt.justification}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}