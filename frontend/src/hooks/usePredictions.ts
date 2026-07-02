// TanStack Query hooks for prediction and dashboard data access.
import { useMutation, useQuery } from "@tanstack/react-query";
import { predictionService } from "@/services/predictionService";
import type { PredictRequest } from "@/types/prediction";

export const predictionKeys = {
  dashboard: ["dashboard"] as const,
  history: ["history"] as const,
  detail: (id: string) => ["prediction", id] as const,
};

export const useDashboardQuery = () =>
  useQuery({
    queryKey: predictionKeys.dashboard,
    queryFn: predictionService.getDashboard,
  });

export const useHistoryQuery = () =>
  useQuery({
    queryKey: predictionKeys.history,
    queryFn: predictionService.getHistory,
  });

export const usePredictionQuery = (id: string) =>
  useQuery({
    queryKey: predictionKeys.detail(id),
    queryFn: () => predictionService.getPrediction(id),
  });

export const useUploadMutation = () =>
  useMutation({
    mutationFn: (file: File) => predictionService.upload(file),
  });

export const usePredictMutation = () =>
  useMutation({
    mutationFn: (payload: PredictRequest) => predictionService.predict(payload),
  });
