export default function RoomCard({ room, index }) {
  const genericName = `Room ${index !== undefined ? index + 1 : room.id.split('_').pop()}`;
  return (
    <div style={{
      background: "#0f172a", border: "1px solid #1e293b", borderRadius: 10,
      padding: "14px 16px", marginBottom: 8
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9" }}>{genericName}</span>
          <span style={{ fontSize: 11, color: "#64748b", marginLeft: 8 }}>#{room.id}</span>
        </div>
        <span style={{
          background: "#33415522", color: "#94a3b8", border: "1px solid #334155",
          borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600, letterSpacing: "1px"
        }}>
          ROOM
        </span>
      </div>
      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#94a3b8" }}>
        <span>📐 {room.estimated_area_sqm} m²</span>
        {room.dimensions && (
          <span>📏 {room.dimensions.width_m}m × {room.dimensions.length_m}m</span>
        )}
      </div>
    </div>
  );
}