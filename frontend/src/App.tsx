import { useState } from "react";

// In `npm run dev`, vite.config.ts's server.proxy forwards relative
// "/predict"/"/health" to the backend -- but that's a dev-server-only
// feature; the production build (docker/frontend.Dockerfile's `vite
// build` + `serve -s dist`) has no such proxy, so a relative fetch from
// that build 404s/gets the SPA's own index.html back instead of the
// backend's JSON (found and confirmed via a real docker-compose run,
// Month 2 engineering pipeline -- not a hypothetical). VITE_API_BASE_URL
// is a build-time env var (see docker/frontend.Dockerfile,
// docker-compose.yml) so the production build can point at the
// backend's real published URL; empty string (the dev-server default)
// preserves the existing relative-path/proxy behavior exactly.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

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
      const response = await fetch(`${API_BASE}/predict`, { method: "POST", body: formData });
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
