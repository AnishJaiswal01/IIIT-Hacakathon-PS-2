export default function UploadPanel({ file, setFile, loading, error, onUpload }) {
  return (
    <div style={{ 
      background: "rgba(15, 23, 42, 0.6)", 
      border: "1px solid rgba(255,255,255,0.08)", 
      borderRadius: 16, 
      padding: 24,
      boxShadow: "0 10px 30px -10px rgba(0,0,0,0.5)"
    }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "#94a3b8", margin: "0 0 20px 0", display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#818cf8", display: "inline-block" }}></span>
        Input Parameters
      </h2>
      <form onSubmit={onUpload} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        
        {/* Enhanced Drop Zone */}
        <label style={{
          border: `2px dashed ${file ? "#818cf8" : "rgba(255,255,255,0.15)"}`, 
          borderRadius: 12, padding: "32px 16px", textAlign: "center",
          cursor: "pointer", 
          background: file ? "rgba(99, 102, 241, 0.05)" : "rgba(0,0,0,0.2)", 
          transition: "all 0.3s ease"
        }}>
          <span style={{ fontSize: 28, display: "block", marginBottom: 12, opacity: file ? 1 : 0.6 }}>
            {file ? "📝" : "📂"}
          </span>
          <span style={{ fontSize: 14, color: file ? "#e2e8f0" : "#94a3b8", fontWeight: 500, display: "block" }}>
            {file ? file.name : "Click to browse files"}
          </span>
          {!file && <span style={{ fontSize: 12, color: "#64748b", marginTop: 8, display: "block" }}>PNG, JPG, or PDF</span>}
          <input 
            type="file" accept="image/*" 
            onChange={(e) => setFile(e.target.files[0])} 
            style={{ display: "none" }} 
          />
        </label>

        {/* Premium Gradient Button */}
        <button 
          type="submit" disabled={loading || !file}
          style={{
            background: loading ? "#334155" : "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)", 
            color: "white",
            border: "none", 
            borderRadius: 10, 
            padding: "14px", 
            fontSize: 15, 
            fontWeight: 700,
            cursor: loading || !file ? "not-allowed" : "pointer",
            boxShadow: loading || !file ? "none" : "0 4px 14px 0 rgba(99, 102, 241, 0.39)",
            transition: "transform 0.1s, box-shadow 0.2s",
            textShadow: "0 1px 2px rgba(0,0,0,0.2)"
          }}
          onMouseOver={(e) => { if(!loading && file) e.currentTarget.style.transform = "translateY(-1px)"; }}
          onMouseOut={(e) => { if(!loading && file) e.currentTarget.style.transform = "translateY(0)"; }}
        >
          {loading ? "Processing..." : "Run AI Pipeline ✨"}
        </button>
      </form>
      
      {error && (
        <div style={{ marginTop: 20, padding: 14, background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 10, color: "#fca5a5", fontSize: 13, lineHeight: 1.5 }}>
          <strong style={{ display: "block", marginBottom: 4 }}>Error Output:</strong>
          {error}
        </div>
      )}
    </div>
  );
}