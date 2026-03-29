export default function WallCard({ wall }) {
  const color = wall.is_load_bearing ? "#ef4444" : "#22c55e";
  
  return (
    <div style={{
      background: "#0f172a", border: `1px solid ${color}33`,
      borderRadius: 10, padding: "12px 16px", marginBottom: 8
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0" }}>{wall.id}</span>
          <span style={{
            background: color + "22", color: color, border: `1px solid ${color}44`,
            borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600, textTransform: "uppercase"
          }}>
            {wall.type.replace(/_/g, " ")}
          </span>
        </div>
        <span style={{ fontSize: 12, color: "#64748b" }}>~{wall.estimated_length_m}m · {wall.thickness}</span>
      </div>
    </div>
  );
}