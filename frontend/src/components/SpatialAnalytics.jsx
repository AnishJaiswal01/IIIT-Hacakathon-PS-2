import React from "react";

export default function SpatialAnalytics({ analysis }) {
  if (!analysis) return null;

  const SCALE = 20; // Ensure dimensions match the 3D model scaling

  // Flatten structures for the data table
  const wallsData = (analysis.model_3d?.walls_3d || []).map(w => ({
    id: w.id,
    type: "Wall",
    classification: w.wall_type,
    coords: `(${w.center_x.toFixed(2)}, ${w.center_y.toFixed(2)}, ${w.center_z.toFixed(2)})`,
    dimensions: `${w.length.toFixed(2)}m × ${w.height.toFixed(2)}m`,
    area: (w.length * w.height).toFixed(2) + " m²"
  }));

  const openingsData = (analysis.model_3d?.openings_3d || []).map(o => ({
    id: o.id,
    type: "Aperture",
    classification: o.opening_type,
    coords: `(${o.center_x.toFixed(2)}, ${o.center_y.toFixed(2)}, ${o.center_z.toFixed(2)})`,
    dimensions: `${o.width.toFixed(2)}m × ${o.height.toFixed(2)}m`,
    area: (o.width * o.height).toFixed(2) + " m²"
  }));

  const combinedData = [...wallsData, ...openingsData];

  return (
    <div style={{
      padding: "20px",
      background: "rgba(15, 23, 42, 0.6)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      borderRadius: "16px",
      border: "1px solid rgba(255, 255, 255, 0.1)",
      boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
      color: "#f8fafc",
      overflow: "hidden"
    }}>
      <h3 style={{ margin: "0 0 16px 0", color: "#38bdf8", display: "flex", alignItems: "center", gap: "8px" }}>
        ⛶ Spatial Analytics Map
      </h3>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.1)", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>Entity ID</th>
              <th style={{ padding: "12px 16px" }}>Category</th>
              <th style={{ padding: "12px 16px" }}>Classification</th>
              <th style={{ padding: "12px 16px" }}>Center Coord (X, Y, Z)</th>
              <th style={{ padding: "12px 16px" }}>Dimensions (W × H)</th>
              <th style={{ padding: "12px 16px" }}>Surface Area</th>
            </tr>
          </thead>
          <tbody>
            {combinedData.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ padding: "20px", textAlign: "center", color: "#64748b" }}>
                  No structural geometry parsed.
                </td>
              </tr>
            ) : (
              combinedData.map((row, idx) => (
                <tr key={row.id} style={{ 
                  borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                  background: idx % 2 === 0 ? "rgba(255, 255, 255, 0.02)" : "transparent",
                  transition: "background 0.2s"
                }}
                onMouseOver={(e) => e.currentTarget.style.background = "rgba(56, 189, 248, 0.08)"}
                onMouseOut={(e) => e.currentTarget.style.background = idx % 2 === 0 ? "rgba(255, 255, 255, 0.02)" : "transparent"}
                >
                  <td style={{ padding: "12px 16px", fontFamily: "monospace", color: "#cbd5e1" }}>{row.id}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{ 
                      padding: "4px 8px", 
                      borderRadius: "4px", 
                      fontSize: "11px", 
                      fontWeight: "bold",
                      textTransform: "uppercase",
                      background: row.type === "Wall" ? "rgba(52, 152, 219, 0.2)" : "rgba(231, 76, 60, 0.2)",
                      color: row.type === "Wall" ? "#3498db" : "#e74c3c"
                    }}>
                      {row.type}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#e2e8f0" }}>{row.classification.replace(/_/g, " ")}</td>
                  <td style={{ padding: "12px 16px", fontFamily: "monospace", color: "#38bdf8" }}>{row.coords}</td>
                  <td style={{ padding: "12px 16px", color: "#94a3b8" }}>{row.dimensions}</td>
                  <td style={{ padding: "12px 16px", color: "#10b981", fontWeight: "600" }}>{row.area}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
