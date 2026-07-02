// Dashboard page showing operational metrics, recent predictions, and model status.
import { Link } from "react-router-dom";
import { Activity, Brain, Database, UploadCloud } from "lucide-react";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { SectionHeader } from "@/components/common/SectionHeader";
import { PredictionCard } from "@/components/prediction/PredictionCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROUTES } from "@/constants/routes";
import { useDashboardQuery } from "@/hooks/usePredictions";
import { formatDate, formatNumber, formatPercent } from "@/utils/formatters";

export const Dashboard = () => {
  const { data, isLoading } = useDashboardQuery();

  if (isLoading || !data) return <LoadingSpinner label="Loading mission dashboard" />;

  const stats = [
    { label: "Analyzed samples", value: formatNumber(data.stats.analyzedSamples), icon: Database },
    { label: "Mean confidence", value: formatPercent(data.stats.meanConfidence), icon: Activity },
    { label: "Active models", value: data.stats.activeModels, icon: Brain },
    { label: "Pending reviews", value: data.stats.pendingReviews, icon: UploadCloud },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <SectionHeader title="Mission Dashboard" description="Monitor current asteroid mineral inference throughput, confidence, and model readiness." />
        <Button asChild>
          <Link to={ROUTES.upload}>
            <UploadCloud className="h-5 w-5" /> Quick upload
          </Link>
        </Button>
      </div>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-5">
            <stat.icon className="mb-5 h-6 w-6 text-secondary" />
            <p className="text-sm text-slate-400">{stat.label}</p>
            <p className="mt-2 text-3xl font-bold text-white">{stat.value}</p>
          </Card>
        ))}
      </section>
      <section className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div>
          <h2 className="mb-4 text-xl font-semibold text-white">Recent predictions</h2>
          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-3">
            {data.recent.map((prediction) => (
              <PredictionCard key={prediction.id} prediction={prediction} />
            ))}
          </div>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Model status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">State</span>
              <Badge className="border-emerald-400/30 text-emerald-300">{data.model.state}</Badge>
            </div>
            <div>
              <p className="text-sm text-slate-400">Model</p>
              <p className="mt-1 font-semibold text-white">{data.model.name}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-slate-400">Version</p>
                <p className="mt-1 text-white">{data.model.version}</p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-slate-400">Latency</p>
                <p className="mt-1 text-white">{data.model.latencyMs} ms</p>
              </div>
            </div>
            <p className="text-sm text-slate-400">Last calibrated {formatDate(data.model.lastCalibrated)}</p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
};
