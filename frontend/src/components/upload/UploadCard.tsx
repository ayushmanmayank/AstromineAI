// Drag-and-drop upload card with React Hook Form and Zod validation support.
import { zodResolver } from "@hookform/resolvers/zod";
import { ImagePlus, Sparkles, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { usePredictMutation, useUploadMutation } from "@/hooks/usePredictions";

const uploadSchema = z.object({
  asteroidName: z.string().min(2, "Asteroid name is required"),
  observationMode: z.string().min(2, "Observation mode is required"),
  file: z.instanceof(File, { message: "Observation image is required" }),
});

type UploadFormValues = z.infer<typeof uploadSchema>;

type UploadCardProps = {
  onPredictionReady: (predictionId: string) => void;
};

export const UploadCard = ({ onPredictionReady }: UploadCardProps) => {
  const [previewUrl, setPreviewUrl] = useState<string>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadMutation();
  const predictMutation = usePredictMutation();
  const isProcessing = uploadMutation.isPending || predictMutation.isPending;

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { asteroidName: "", observationMode: "visible-near-ir" },
  });

  const supportedFormats = useMemo(() => ["JPG", "PNG", "TIFF", "FITS"], []);

  useEffect(() => {
    register("file");
  }, [register]);

  const applyFile = (file?: File) => {
    if (!file) return;
    setValue("file", file, { shouldValidate: true });
    setPreviewUrl(URL.createObjectURL(file));
  };

  const onSubmit = async (values: UploadFormValues) => {
    const upload = await uploadMutation.mutateAsync(values.file);
    const prediction = await predictMutation.mutateAsync({
      uploadId: upload.uploadId,
      asteroidName: values.asteroidName,
      observationMode: values.observationMode,
    });
    onPredictionReady(prediction.id);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Asteroid Observation Upload</CardTitle>
        <CardDescription>Submit calibrated imagery or spectral raster products for mineral composition inference.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]" onSubmit={handleSubmit(onSubmit)}>
          <button
            type="button"
            className="min-h-80 rounded-xl border border-dashed border-secondary/40 bg-white/[0.04] p-5 text-left transition hover:border-secondary hover:bg-secondary/5"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              applyFile(event.dataTransfer.files[0]);
            }}
          >
            {previewUrl ? (
              <img src={previewUrl} alt="Uploaded asteroid preview" className="h-full max-h-96 w-full rounded-lg object-cover" />
            ) : (
              <div className="flex h-full min-h-72 flex-col items-center justify-center text-center">
                <UploadCloud className="mb-4 h-12 w-12 text-secondary" />
                <p className="text-lg font-semibold text-white">Drop asteroid imagery here</p>
                <p className="mt-2 max-w-md text-sm text-slate-400">Use mission imagery, lab microscopy, or spectral renderings prepared for analysis.</p>
              </div>
            )}
          </button>
          <div className="space-y-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.tif,.tiff,.fits"
              className="hidden"
              onChange={(event) => applyFile(event.target.files?.[0])}
            />
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-300">Asteroid target</label>
              <Input placeholder="16 Psyche" {...register("asteroidName")} />
              {errors.asteroidName ? <p className="mt-2 text-sm text-red-300">{errors.asteroidName.message}</p> : null}
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-300">Observation mode</label>
              <Select {...register("observationMode")}>
                <option value="visible-near-ir">Visible / Near-IR</option>
                <option value="thermal-ir">Thermal IR</option>
                <option value="radar-albedo">Radar Albedo</option>
                <option value="microscopy">Sample Microscopy</option>
              </Select>
            </div>
            <div className="rounded-xl border border-space-border bg-white/[0.04] p-4">
              <p className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
                <ImagePlus className="h-4 w-4 text-secondary" />
                Supported formats
              </p>
              <div className="flex flex-wrap gap-2">
                {supportedFormats.map((format) => (
                  <span key={format} className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">
                    {format}
                  </span>
                ))}
              </div>
              {errors.file ? <p className="mt-3 text-sm text-red-300">{errors.file.message}</p> : null}
            </div>
            <Button className="w-full" size="lg" type="submit" disabled={isProcessing}>
              {isProcessing ? <LoadingSpinner label="Running inference" /> : <><Sparkles className="h-5 w-5" /> Predict composition</>}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};
