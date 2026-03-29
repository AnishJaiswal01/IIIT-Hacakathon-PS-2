import { useState } from "react";
import { analyzePlan } from "./api/client";
import UploadPanel from "./components/UploadPanel";
import PipelineSteps from "./components/PipelineSteps";
import ResultsTabs from "./components/ResultsTabs";
import JsonViewer from "./components/JsonViewer";

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true); setError(null); setAnalysis(null);
    try {
      const data = await analyzePlan(file, "plan_" + Date.now());
      setAnalysis(data);
    } catch (err) {
      setError(err.message || "Failed to analyze floor plan.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: "100vh", 
      // Modern sleek radial gradient background
      background: "radial-gradient(circle at 50% -20%, #1e1b4b 0%, #020617 80%)", 
      color: "#f8fafc", 
      fontFamily: "system-ui, -apple-system, sans-serif" 
    }}>
      {/* Glassmorphism Header */}
      <header style={{ 
        padding: "16px 32px", 
        borderBottom: "1px solid rgba(255,255,255,0.05)", 
        background: "rgba(15, 23, 42, 0.4)",
        backdropFilter: "blur(12px)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        position: "sticky", top: 0, zIndex: 50
      }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: "-0.5px", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ 
            background: "linear-gradient(135deg, #818cf8 0%, #c084fc 100%)", 
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" 
          }}>PS2</span> 
          <span style={{ color: "#e2e8f0", fontWeight: 600 }}>Autonomous Structural Intelligence</span>
        </h1>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#a78bfa", background: "rgba(167, 139, 250, 0.1)", border: "1px solid rgba(167, 139, 250, 0.2)", padding: "6px 14px", borderRadius: 99, letterSpacing: "0.5px", textTransform: "uppercase" }}>
          Hackathon Build Live
        </div>
      </header>

      <main style={{ maxWidth: 1300, margin: "0 auto", padding: "32px 24px", display: "grid", gridTemplateColumns: "340px 1fr", gap: 32 }}>
        
        {/* Left Sidebar */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <UploadPanel file={file} setFile={setFile} loading={loading} error={error} onUpload={handleUpload} />
          <PipelineSteps loading={loading} analysis={analysis} />
          <JsonViewer data={analysis} />
        </aside>

        {/* Right Content Area */}
        <section style={{ 
          minHeight: 650, 
          background: "rgba(15, 23, 42, 0.6)", 
          border: "1px solid rgba(255,255,255,0.08)", 
          borderRadius: 16, 
          padding: 24,
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
        }}>
          {!analysis && !loading && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#64748b" }}>
              <div style={{ fontSize: 64, marginBottom: 24, opacity: 0.5 }}>🏗️</div>
              <h3 style={{ margin: "0 0 8px 0", color: "#e2e8f0" }}>Awaiting Floor Plan</h3>
              <p style={{ margin: 0, fontSize: 14 }}>Upload a 2D blueprint to generate the 3D structural model.</p>
            </div>
          )}

          {loading && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#818cf8" }}>
              <div style={{ fontSize: 56, marginBottom: 24, animation: "spin 2s linear infinite" }}>⚙️</div>
              <h3 style={{ margin: "0 0 8px 0", color: "#e2e8f0" }}>Analyzing Geometry...</h3>
              <p style={{ margin: 0, fontSize: 14, color: "#94a3b8" }}>Running AI vision models and extracting architectural nodes.</p>
              <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {analysis && !loading && <ResultsTabs analysis={analysis} />}
        </section>
        
      </main>
    </div>
  );
}