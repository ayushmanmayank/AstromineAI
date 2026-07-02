// History page for searching, filtering, and sorting previous prediction runs.
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { SectionHeader } from "@/components/common/SectionHeader";
import { PredictionCard } from "@/components/prediction/PredictionCard";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useHistoryQuery } from "@/hooks/usePredictions";

export const History = () => {
  const { data, isLoading } = useHistoryQuery();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("newest");

  const predictions = useMemo(() => {
    return [...(data ?? [])]
      .filter((item) => item.asteroidName.toLowerCase().includes(search.toLowerCase()))
      .filter((item) => (filter === "all" ? true : item.status === filter))
      .sort((a, b) => {
        if (sort === "confidence") return b.confidence - a.confidence;
        return new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime();
      });
  }, [data, filter, search, sort]);

  return (
    <div className="space-y-8">
      <SectionHeader title="Prediction History" description="Search and review prior asteroid composition analyses from the mission workspace." />
      <div className="grid gap-3 lg:grid-cols-[1fr_180px_180px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
          <Input className="pl-10" placeholder="Search asteroid target" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        <Select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="complete">Complete</option>
          <option value="review">Review</option>
          <option value="processing">Processing</option>
        </Select>
        <Select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="newest">Newest first</option>
          <option value="confidence">Highest confidence</option>
        </Select>
      </div>
      {isLoading ? <LoadingSpinner label="Loading prediction history" /> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {predictions.map((prediction) => (
          <PredictionCard key={prediction.id} prediction={prediction} />
        ))}
      </div>
    </div>
  );
};
