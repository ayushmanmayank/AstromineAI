// Upload page for submitting asteroid observation products to the inference flow.
import { useNavigate } from "react-router-dom";
import { SectionHeader } from "@/components/common/SectionHeader";
import { UploadCard } from "@/components/upload/UploadCard";
import { ROUTES } from "@/constants/routes";
import { useToast } from "@/hooks/useToast";

export const Upload = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Upload Observation"
        description="Drag in asteroid imagery or spectral raster files and run the composition model with mission metadata."
      />
      <UploadCard
        onPredictionReady={(predictionId) => {
          showToast({ title: "Prediction complete", description: "Composition analysis is ready for review." });
          navigate(ROUTES.predictionById.replace(":id", predictionId));
        }}
      />
    </div>
  );
};
