import { useEffect, useRef, useState } from "react";

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

// Honesty note (see docs/handoff/STATUS.md for the full account): backend/main.py's
// /predict takes only a `file` upload -- no model-selection parameter, and the
// active model is fixed for the life of the backend process via the
// ASTROMINE_MODEL_TYPE environment variable. The toggle below is therefore
// rendered disabled with an explanatory tooltip rather than pretending a
// per-request model choice exists. Because the toggle has no effect on
// which model actually runs, the explanation method name is NOT derived
// from it (that would misrepresent what ran) -- a generic, honest label is
// shown instead. If a future backend change adds real per-request model
// selection, this is the one place to wire it up.
type ModelChoice = "resnet50" | "vit_b";
const BACKEND_HONORS_MODEL_CHOICE = false;

function LogoMark() {
  return (
    <svg
      className="logo-mark"
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="14" cy="14" r="6" stroke="currentColor" strokeWidth="2" />
      <ellipse
        cx="14"
        cy="14"
        rx="12"
        ry="5"
        stroke="currentColor"
        strokeWidth="1.5"
        transform="rotate(-20 14 14)"
      />
      <circle cx="21.5" cy="9.5" r="1.4" fill="currentColor" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M10 2.5 L18 17 H2 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <line x1="10" y1="8" x2="10" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="14.5" r="0.9" fill="currentColor" />
    </svg>
  );
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [heatmapVisible, setHeatmapVisible] = useState(true);
  const [modelChoice, setModelChoice] = useState<ModelChoice>("resnet50");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Revoke the previous object URL whenever it's replaced/unmounted, so we
  // don't leak blob URLs across repeated selections.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError(null);
    setHeatmapVisible(true);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(nextFile ? URL.createObjectURL(nextFile) : null);
  }

  function handleReset() {
    selectFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) selectFile(dropped);
  }

  async function handleAnalyze() {
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

  const methodName = BACKEND_HONORS_MODEL_CHOICE
    ? modelChoice === "resnet50"
      ? "Grad-CAM"
      : "Attention rollout"
    : "Explanation heatmap";

  return (
    <div className="page">
      <header className="header">
        <div className="header-brand">
          <LogoMark />
          <div className="header-titles">
            <span className="header-title">AstroMineAI</span>
            <span className="header-subtitle mono">Vesta surface composition · Dawn FC</span>
          </div>
        </div>

        <div
          className="model-toggle"
          role="group"
          aria-label="Model"
          title={BACKEND_HONORS_MODEL_CHOICE ? undefined : "Backend serves one model"}
        >
          <button
            type="button"
            className="model-toggle-btn"
            aria-pressed={modelChoice === "resnet50"}
            disabled={!BACKEND_HONORS_MODEL_CHOICE}
            onClick={() => setModelChoice("resnet50")}
          >
            ResNet-50
          </button>
          <button
            type="button"
            className="model-toggle-btn"
            aria-pressed={modelChoice === "vit_b"}
            disabled={!BACKEND_HONORS_MODEL_CHOICE}
            onClick={() => setModelChoice("vit_b")}
          >
            ViT-B
          </button>
        </div>
      </header>

      <div className="warning-banner" role="note">
        <WarningIcon />
        <span>
          Pipeline demo, not a Vesta result. Model weights here were trained on synthetic
          labels. The project's compositional-signal test came back negative, so no
          validated composition labels exist. Treat every output as an illustration of the
          interface.
        </span>
      </div>

      <div className="panels">
        <section className="panel panel-input" aria-labelledby="input-heading">
          <h2 className="panel-heading" id="input-heading">
            1 · Input crop
          </h2>

          <div
            className={`dropzone${dragOver ? " is-dragover" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <label
              htmlFor="crop-file"
              style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}
            >
              Choose a Dawn FC image crop
            </label>
            <input
              ref={fileInputRef}
              id="crop-file"
              className="dropzone-input"
              type="file"
              accept="image/*"
              onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
            />

            {previewUrl ? (
              <img src={previewUrl} alt="" className="dropzone-preview" />
            ) : (
              <span className="dropzone-hint">
                Drag and drop an image here, or click to choose a file
              </span>
            )}
          </div>

          {file && <span className="filename mono">{file.name}</span>}

          <div className="input-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={!file || loading}
            >
              {loading ? "Analyzing…" : "Analyze crop"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={handleReset}>
              Reset
            </button>
          </div>
        </section>

        <section
          className="panel panel-output"
          aria-labelledby="output-heading"
          aria-live="polite"
        >
          <h2 className="panel-heading" id="output-heading">
            2 · Estimate and explanation
          </h2>

          <div className="result-region">
            {error ? (
              <div className="error-panel" role="alert">
                <p className="error-title">Not available</p>
                <p className="error-body">{error}</p>
              </div>
            ) : loading ? (
              <p className="result-loading">Choose a crop and analyze it to see an estimate. Analyzing…</p>
            ) : result ? (
              <>
                <div className="result-grid">
                  <div className="result-text">
                    <span className="result-caption mono">PREDICTION · SYNTHETIC LABEL</span>
                    <span className="result-prediction">{result.prediction}</span>
                    <span className="result-confidence mono">
                      {(result.confidence * 100).toFixed(1)}% confidence
                    </span>
                  </div>

                  <div className="result-visual">
                    <div className="visual-header">
                      <span className="method-name">{methodName}</span>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-pressed={heatmapVisible}
                        onClick={() => setHeatmapVisible((v) => !v)}
                      >
                        {heatmapVisible ? "Hide heatmap" : "Show heatmap"}
                      </button>
                    </div>

                    <div className="image-stack">
                      {previewUrl && <img src={previewUrl} alt="Analyzed crop" />}
                      <img
                        src={`data:image/png;base64,${result.heatmap_png_base64}`}
                        alt=""
                        aria-hidden="true"
                        className={`heatmap-overlay${heatmapVisible ? " is-visible" : ""}`}
                      />
                    </div>

                    <div className="legend" aria-hidden="true">
                      <div className="legend-gradient" />
                      <div className="legend-labels">
                        <span>Low</span>
                        <span>High</span>
                      </div>
                    </div>
                  </div>
                </div>

                <p className="explain-note">
                  The heatmap shows where the model looked, not why a surface is a given
                  composition. High influence on a crater rim, a shadow edge or an image
                  border can reflect brightness or illumination rather than mineralogy.
                </p>
                <p className="api-disclaimer">{result.disclaimer}</p>
              </>
            ) : (
              <p className="result-hint">
                Choose a Dawn FC image crop on the left, then analyze it to see a
                prediction and its explanation heatmap here.
              </p>
            )}
          </div>
        </section>
      </div>

      <footer className="footer">
        Vesta only · Region-based splits · Full per-sample provenance · Negative results
        reported
      </footer>
    </div>
  );
}
