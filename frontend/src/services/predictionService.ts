// API facade for uploads, predictions, history, and dashboard data.
import { apiClient } from "@/services/apiClient";
import { mockApi } from "@/services/mockApi";
import type { DashboardData, PredictRequest, PredictionRecord, UploadResponse } from "@/types/prediction";

const useMockApi = import.meta.env.VITE_USE_MOCK_API !== "false";

export const predictionService = {
  async upload(file: File): Promise<UploadResponse> {
    if (useMockApi) return mockApi.upload(file);
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await apiClient.post("/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async predict(payload: PredictRequest): Promise<PredictionRecord> {
    if (useMockApi) return mockApi.predict(payload);
    const { data } = await apiClient.post("/predict", payload);
    return data;
  },

  async getHistory(): Promise<PredictionRecord[]> {
    if (useMockApi) return mockApi.history();
    const { data } = await apiClient.get("/history");
    return data;
  },

  async getPrediction(id: string): Promise<PredictionRecord> {
    if (useMockApi) return mockApi.prediction(id);
    const { data } = await apiClient.get(`/prediction/${id}`);
    return data;
  },

  async getDashboard(): Promise<DashboardData> {
    if (useMockApi) return mockApi.dashboard();
    const [history] = await Promise.all([this.getHistory()]);
    return {
      stats: {
        analyzedSamples: history.length,
        meanConfidence:
          history.reduce((total: number, item: PredictionRecord) => total + item.confidence, 0) / Math.max(history.length, 1),
        activeModels: 1,
        pendingReviews: history.filter((item: PredictionRecord) => item.status !== "complete").length,
      },
      model: {
        name: "AstroMineAI Inference API",
        version: "backend",
        state: "nominal",
        latencyMs: 0,
        lastCalibrated: new Date().toISOString(),
      },
      recent: history.slice(0, 3),
    };
  },
};
