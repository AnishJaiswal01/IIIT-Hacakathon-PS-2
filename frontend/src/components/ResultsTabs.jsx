import { useState } from "react";
import ThreeViewer from "./ThreeViewer";
import RoomCard from "./RoomCard";
import WallCard from "./WallCard";
import MaterialCard from "./MaterialCard";
import ConcernCard from "./ConcernCard";

export default function ResultsTabs({ analysis }) {
  const [activeTab, setActiveTab] = useState("3d");

  const tabs = [
    { id: "3d", label: "3D Viewer" },
    { id: "rooms", label: `Rooms (${analysis.rooms?.length || 0})` },
    { id: "walls", label: `Walls (${analysis.walls?.length || 0})` },
    { id: "materials", label: "Materials" },
    { id: "concerns", label: "Concerns" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid #1e293b", paddingBottom: 16, overflowX: "auto" }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: activeTab === tab.id ? "#1e293b" : "transparent",
              color: activeTab === tab.id ? "#f8fafc" : "#64748b",
              border: "none", borderRadius: 6, padding: "8px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer"
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto", paddingRight: 8 }}>
        {activeTab === "3d" && <ThreeViewer analysis={analysis} />}
        {activeTab === "rooms" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 12 }}>
            {analysis.rooms?.map(room => <RoomCard key={room.id} room={room} />)}
          </div>
        )}
        {activeTab === "walls" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {analysis.walls?.map(wall => <WallCard key={wall.id} wall={wall} />)}
          </div>
        )}
        {activeTab === "materials" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
            {analysis.material_recommendations?.map((rec, i) => <MaterialCard key={i} rec={rec} />)}
          </div>
        )}
        {activeTab === "concerns" && (
          <div>
            {analysis.structural_concerns?.length === 0 ? (
              <div style={{ padding: 20, textAlign: "center", color: "#22c55e", background: "#0f172a", borderRadius: 12 }}>
                ✓ No critical structural concerns detected.
              </div>
            ) : (
              analysis.structural_concerns?.map((concern, i) => <ConcernCard key={i} concern={concern} />)
            )}
          </div>
        )}
      </div>
    </div>
  );
}