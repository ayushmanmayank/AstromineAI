// Reusable prediction summary card used in dashboard and history lists.
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ROUTES } from "@/constants/routes";
import type { PredictionRecord } from "@/types/prediction";
import { formatDate, formatPercent } from "@/utils/formatters";

type PredictionCardProps = {
  prediction: PredictionRecord;
};

export const PredictionCard = ({ prediction }: PredictionCardProps) => (
  <Link to={ROUTES.predictionById.replace(":id", prediction.id)}>
    <Card className="group overflow-hidden transition duration-200 hover:-translate-y-1 hover:border-secondary/50">
      <div className="aspect-[16/9] overflow-hidden">
        <img
          src={prediction.imageUrl}
          alt={`${prediction.asteroidName} observation`}
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
        />
      </div>
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-white">{prediction.asteroidName}</h3>
            <p className="text-xs text-slate-400">{formatDate(prediction.uploadedAt)}</p>
          </div>
          <Badge>{prediction.status}</Badge>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">{prediction.dominantMineral}</span>
          <span className="font-semibold text-secondary">{formatPercent(prediction.confidence)}</span>
        </div>
      </div>
    </Card>
  </Link>
);
