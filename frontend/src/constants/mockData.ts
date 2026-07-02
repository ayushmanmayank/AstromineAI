// Mock data used when backend services are unavailable during frontend development.
import type { DashboardStats, ModelStatus, PredictionRecord } from "@/types/prediction";

export const mockPredictions: PredictionRecord[] = [
  {
    id: "demo-001",
    asteroidName: "16 Psyche",
    imageUrl:
      "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1200&q=80",
    uploadedAt: "2026-06-29T18:26:00.000Z",
    status: "complete",
    confidence: 94.2,
    dominantMineral: "Nickel-Iron Alloy",
    analyst: "Orbital Materials Lab",
    summary:
      "The spectral response suggests a metallic-rich body with strong nickel-iron signatures and secondary olivine traces consistent with differentiated asteroid material.",
    composition: [
      { mineral: "Nickel-Iron Alloy", probability: 42, color: "#00C2FF" },
      { mineral: "Olivine", probability: 21, color: "#2563EB" },
      { mineral: "Pyroxene", probability: 17, color: "#7C3AED" },
      { mineral: "Troilite", probability: 12, color: "#F59E0B" },
      { mineral: "Carbonaceous Matrix", probability: 8, color: "#10B981" },
    ],
  },
  {
    id: "demo-002",
    asteroidName: "101955 Bennu",
    imageUrl:
      "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1200&q=80",
    uploadedAt: "2026-06-27T15:10:00.000Z",
    status: "review",
    confidence: 88.7,
    dominantMineral: "Carbonaceous Matrix",
    analyst: "Sample Return Analytics",
    summary:
      "Hydrated mineral features and low albedo texture indicate carbonaceous material with clay-bearing compounds likely present near the sampled regolith.",
    composition: [
      { mineral: "Carbonaceous Matrix", probability: 38, color: "#10B981" },
      { mineral: "Phyllosilicates", probability: 26, color: "#00C2FF" },
      { mineral: "Magnetite", probability: 16, color: "#2563EB" },
      { mineral: "Sulfides", probability: 11, color: "#7C3AED" },
      { mineral: "Organics", probability: 9, color: "#F59E0B" },
    ],
  },
  {
    id: "demo-003",
    asteroidName: "433 Eros",
    imageUrl:
      "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=1200&q=80",
    uploadedAt: "2026-06-25T09:34:00.000Z",
    status: "complete",
    confidence: 91.5,
    dominantMineral: "Pyroxene",
    analyst: "NEA Composition Team",
    summary:
      "The model identifies an S-type signature with pyroxene and olivine as the leading mineral groups across the visible regolith face.",
    composition: [
      { mineral: "Pyroxene", probability: 34, color: "#7C3AED" },
      { mineral: "Olivine", probability: 28, color: "#2563EB" },
      { mineral: "Plagioclase", probability: 18, color: "#00C2FF" },
      { mineral: "Metallic Grains", probability: 13, color: "#F59E0B" },
      { mineral: "Silicates", probability: 7, color: "#10B981" },
    ],
  },
];

export const mockDashboardStats: DashboardStats = {
  analyzedSamples: 1284,
  meanConfidence: 91.8,
  activeModels: 4,
  pendingReviews: 16,
};

export const mockModelStatus: ModelStatus = {
  name: "RegolithNet Composition Ensemble",
  version: "v2.7.4",
  state: "nominal",
  latencyMs: 318,
  lastCalibrated: "2026-06-30T12:00:00.000Z",
};
