// ── STATIC MATERIAL DATABASE ───────────────────────────────────────────
const MATERIAL_DB = {
  "Brick Masonry": { description: "Traditional load-bearing structural brick. Excellent thermal mass, high fire resistance, but highly susceptible to severe seismic sheer forces.", properties: { density: "1900 kg/m³", embodied_carbon: "240 kgCO2/t", cost: "$$ Medium", strength: "High", durability: "Medium" } },
  "Fly Ash Brick": { description: "Eco-friendly alternative to traditional clay bricks. Provides excellent thermal insulation and utilizes industrial byproducts.", properties: { density: "1750 kg/m³", embodied_carbon: "110 kgCO2/t", cost: "$ Low", strength: "Medium-High", durability: "High" } },
  "Concrete Block": { description: "Hollow concrete masonry units (CMU), often reinforced with steel rebar and grouted. High compressive strength and facilitates rapid construction timelines.", properties: { density: "2100 kg/m³", embodied_carbon: "180 kgCO2/t", cost: "$ Low-Med", strength: "Medium", durability: "Medium" } },
  "Reinforced Concrete": { description: "Cast-in-place concrete reinforced with steel rebar (RCC). Exceptionally high strength-to-weight ratio, ideal for multi-story load-bearing structural walls.", properties: { density: "2400 kg/m³", embodied_carbon: "350 kgCO2/t", cost: "$$$ High", strength: "Very High", durability: "Very High" } },
  "Steel Frame": { description: "Structural steel columns and I-beams. Extremely high tensile strength, making it ideal for large non-load-bearing open spans and high-risk seismic zones.", properties: { density: "7850 kg/m³", embodied_carbon: "1460 kgCO2/t", cost: "$$$$ Premium", strength: "Very High", durability: "Very High" } },
  "Timber Frame": { description: "Wood-framed construction. Highly sustainable, lightweight, and fast to assemble, but requires extensive fire, moisture, and pest treatment algorithms.", properties: { density: "550 kg/m³", embodied_carbon: "Negative", cost: "$ Low", strength: "Medium", durability: "Medium" } },
  "Glass / Glazing": { description: "Architectural tempered glass panes for fenestration. Provides maximum daylighting but offers minimal structural support and very poor thermal insulation.", properties: { density: "2500 kg/m³", embodied_carbon: "850 kgCO2/t", cost: "$$$ High", strength: "Low", durability: "Medium" } },
  "default": { description: "Standard architectural material selected for baseline structural integrity.", properties: { density: "N/A", embodied_carbon: "N/A", cost: "Varies", strength: "Medium", durability: "Medium" } }
};

const resolveMaterialDb = (name) => {
  const norm = (name || "").toLowerCase();
  if (norm.includes("fly ash")) return MATERIAL_DB["Fly Ash Brick"];
  if (norm.includes("brick")) return MATERIAL_DB["Brick Masonry"];
  if (norm.includes("block") || norm.includes("cmu")) return MATERIAL_DB["Concrete Block"];
  if (norm.includes("concrete") || norm.includes("rcc") || norm.includes("cement")) return MATERIAL_DB["Reinforced Concrete"];
  if (norm.includes("steel") || norm.includes("metal") || norm.includes("aluminum")) return MATERIAL_DB["Steel Frame"];
  if (norm.includes("timber") || norm.includes("wood")) return MATERIAL_DB["Timber Frame"];
  if (norm.includes("glass") || norm.includes("window") || norm.includes("glazing")) return MATERIAL_DB["Glass / Glazing"];
  return MATERIAL_DB["default"];
};

export default function MaterialCard({ rec }) {
  return (
    <div style={{
      background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12,
      padding: 16, marginBottom: 12, boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    }}>
      <div style={{
        fontSize: 12, fontWeight: 700, color: "#22d3ee", textTransform: "uppercase",
        letterSpacing: "0.08em", marginBottom: 16, display: "flex", alignItems: "center", gap: 8
      }}>
        <span style={{ fontSize: 16 }}>⬢</span> {rec.element_type.replace(/_/g, " ")}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {rec.options?.map((opt) => {
          const dbData = resolveMaterialDb(opt.material);

          return (
            <div key={opt.rank} style={{
              background: "#1e293b", borderRadius: 8, padding: "12px 16px",
              borderLeft: `4px solid ${opt.rank === 1 ? "#22d3ee" : opt.rank === 2 ? "#3b82f6" : "#475569"}`
            }}>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span style={{
                    fontSize: 10, fontWeight: 800, background: opt.rank === 1 ? "#22d3ee" : "#334155",
                    color: opt.rank === 1 ? "#0f172a" : "white", borderRadius: 4, padding: "2px 8px"
                  }}>
                    RANK #{opt.rank}
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "#f8fafc" }}>{opt.material}</span>
                </div>
              </div>

              {/* Physical Properties Grid - BUG FIXED HERE */}
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px 8px",
                background: "#020617", padding: "12px", borderRadius: "6px", marginBottom: "12px"
              }}>
                <div>
                  <div style={{ fontSize: "9px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>Density</div>
                  <div style={{ fontSize: "11px", color: "#e2e8f0", fontWeight: 600 }}>{dbData.properties.density}</div>
                </div>
                <div>
                  <div style={{ fontSize: "9px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>Strength</div>
                  <div style={{ fontSize: "11px", color: "#e2e8f0", fontWeight: 600 }}>{dbData.properties.strength}</div>
                </div>
                <div>
                  <div style={{ fontSize: "9px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>Durability</div>
                  <div style={{ fontSize: "11px", color: "#e2e8f0", fontWeight: 600 }}>{dbData.properties.durability}</div>
                </div>
                <div>
                  <div style={{ fontSize: "9px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>Carbon Ftpt.</div>
                  <div style={{ fontSize: "11px", color: "#e2e8f0", fontWeight: 600 }}>{dbData.properties.embodied_carbon}</div>
                </div>
                <div>
                  <div style={{ fontSize: "9px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.5px" }}>Est. Cost</div>
                  <div style={{ fontSize: "11px", color: "#e2e8f0", fontWeight: 600 }}>{dbData.properties.cost}</div>
                </div>
              </div>

              {/* Static Description */}
              <p style={{ fontSize: 12, color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>
                {dbData.description}
              </p>

            </div>
          );
        })}
      </div>
    </div>
  );
}