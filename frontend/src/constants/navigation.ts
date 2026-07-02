// Primary application navigation used by navbar and sidebar layouts.
import { BarChart3, Database, Home, Info, Radar, UploadCloud } from "lucide-react";
import { ROUTES } from "@/constants/routes";
import type { NavigationItem } from "@/types/navigation";

export const NAVIGATION_ITEMS: NavigationItem[] = [
  { label: "Home", path: ROUTES.home, icon: Home },
  { label: "Dashboard", path: ROUTES.dashboard, icon: BarChart3 },
  { label: "Upload", path: ROUTES.upload, icon: UploadCloud },
  { label: "Prediction", path: ROUTES.prediction, icon: Radar },
  { label: "History", path: ROUTES.history, icon: Database },
  { label: "About", path: ROUTES.about, icon: Info },
];
