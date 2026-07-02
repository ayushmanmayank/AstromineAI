// Shared domain types for asteroid uploads, model predictions, and dashboard metrics.
export type MineralProbability = {
  mineral: string;
  probability: number;
  color: string;
};

export type PredictionStatus = "complete" | "processing" | "review";

export type PredictionRecord = {
  id: string;
  asteroidName: string;
  imageUrl: string;
  uploadedAt: string;
  status: PredictionStatus;
  confidence: number;
  dominantMineral: string;
  composition: MineralProbability[];
  summary: string;
  analyst: string;
};

export type DashboardStats = {
  analyzedSamples: number;
  meanConfidence: number;
  activeModels: number;
  pendingReviews: number;
};

export type ModelStatus = {
  name: string;
  version: string;
  state: "nominal" | "training" | "degraded";
  latencyMs: number;
  lastCalibrated: string;
};

export type DashboardData = {
  stats: DashboardStats;
  model: ModelStatus;
  recent: PredictionRecord[];
};

export type UploadResponse = {
  uploadId: string;
  imageUrl: string;
  receivedAt: string;
};

export type PredictRequest = {
  uploadId: string;
  asteroidName: string;
  observationMode: string;
};
