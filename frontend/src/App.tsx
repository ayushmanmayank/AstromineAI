import { useState } from "react";

interface PredictResponse {
  prediction: string;
  confidence: number;
  heatmap_png_base64: string;
  disclaimer: string;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handlePredict() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/predict", { method: "POST", body: formData });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? `Request failed: ${response.status}`);
      }
      setResult(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "system-ui, sans-serif" }}>
      <h1>AstroMineAI</h1>
      <p>Upload a Dawn FC image crop to get a preliminary composition estimate.</p>

      <input
        type="file"
        accept="image/*"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <button onClick={handlePredict} disabled={!file || loading} style={{ marginLeft: "1rem" }}>
        {loading ? "Predicting..." : "Predict"}
      </button>

      {error && (
        <p style={{ color: "#b00020", marginTop: "1rem" }}>
          <strong>Not available:</strong> {error}
        </p>
      )}

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <p>
            <strong>Prediction:</strong> {result.prediction} (
            {(result.confidence * 100).toFixed(1)}% confidence)
          </p>
          <img
            src={`data:image/png;base64,${result.heatmap_png_base64}`}
            alt="Grad-CAM heatmap"
            style={{ maxWidth: "100%", border: "1px solid #ccc" }}
          />
          <p style={{ fontSize: "0.85rem", color: "#555" }}>{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
