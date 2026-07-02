// Mock service responses that mirror backend contracts while backend endpoints are unavailable.
import { mockDashboardStats, mockModelStatus, mockPredictions } from "@/constants/mockData";
import type { DashboardData, PredictRequest, PredictionRecord, UploadResponse } from "@/types/prediction";

const wait = (ms = 450) => new Promise((resolve) => window.setTimeout(resolve, ms));

export const mockApi = {
  async upload(file: File): Promise<UploadResponse> {
    await wait();
    return {
      uploadId: `upload-${crypto.randomUUID()}`,
      imageUrl: URL.createObjectURL(file),
      receivedAt: new Date().toISOString(),
    };
  },

  async predict(request: PredictRequest): Promise<PredictionRecord> {
    await wait(700);
    return {
      ...mockPredictions[0],
      id: request.uploadId,
      asteroidName: request.asteroidName,
      uploadedAt: new Date().toISOString(),
    };
  },

  async history(): Promise<PredictionRecord[]> {
    await wait();
    return mockPredictions;
  },

  async prediction(id: string): Promise<PredictionRecord> {
    await wait();
    return mockPredictions.find((prediction) => prediction.id === id) ?? mockPredictions[0];
  },

  async dashboard(): Promise<DashboardData> {
    await wait();
    return {
      stats: mockDashboardStats,
      model: mockModelStatus,
      recent: mockPredictions.slice(0, 3),
    };
  },
};
