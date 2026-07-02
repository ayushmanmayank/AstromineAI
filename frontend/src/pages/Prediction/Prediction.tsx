// Prediction detail page with composition chart, confidence, probability table, and XAI placeholder.
import { useParams } from "react-router-dom";
import { ConfidenceGauge } from "@/components/charts/ConfidenceGauge";
import { MineralCompositionChart } from "@/components/charts/MineralCompositionChart";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { HeatmapPlaceholder } from "@/components/prediction/HeatmapPlaceholder";
import { ProbabilityTable } from "@/components/prediction/ProbabilityTable";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePredictionQuery } from "@/hooks/usePredictions";
import { formatDate } from "@/utils/formatters";

export const Prediction = () => {
  const { id = "demo-001" } = useParams();
  const { data: prediction, isLoading } = usePredictionQuery(id);

  if (isLoading || !prediction) return <LoadingSpinner label="Loading prediction analysis" />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.18em] text-secondary">Prediction Analysis</p>
          <h1 className="mt-2 text-3xl font-bold text-white">{prediction.asteroidName}</h1>
          <p className="mt-2 text-slate-400">{formatDate(prediction.uploadedAt)} by {prediction.analyst}</p>
        </div>
        <Badge>{prediction.status}</Badge>
      </div>
      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="overflow-hidden">
          <img src={prediction.imageUrl} alt={`${prediction.asteroidName} uploaded observation`} className="h-full min-h-96 w-full object-cover" />
        </Card>
        <div className="space-y-6">
          <ConfidenceGauge value={prediction.confidence} />
          <Card>
            <CardHeader>
              <CardTitle>Mineral composition</CardTitle>
            </CardHeader>
            <CardContent>
              <MineralCompositionChart data={prediction.composition} />
            </CardContent>
          </Card>
        </div>
      </section>
      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Probability table</CardTitle>
          </CardHeader>
          <CardContent>
            <ProbabilityTable composition={prediction.composition} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Explainable AI heatmap</CardTitle>
          </CardHeader>
          <CardContent>
            <HeatmapPlaceholder />
          </CardContent>
        </Card>
      </section>
      <Card>
        <CardHeader>
          <CardTitle>Prediction summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="leading-7 text-slate-300">{prediction.summary}</p>
        </CardContent>
      </Card>
    </div>
  );
};
