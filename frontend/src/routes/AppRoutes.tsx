// React Router route registration for all AstroMineAI pages.
import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { About } from "@/pages/About/About";
import { Dashboard } from "@/pages/Dashboard/Dashboard";
import { History } from "@/pages/History/History";
import { Home } from "@/pages/Home/Home";
import { Prediction } from "@/pages/Prediction/Prediction";
import { Upload } from "@/pages/Upload/Upload";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      { path: "dashboard", element: <Dashboard /> },
      { path: "upload", element: <Upload /> },
      { path: "prediction/:id", element: <Prediction /> },
      { path: "history", element: <History /> },
      { path: "about", element: <About /> },
    ],
  },
]);
