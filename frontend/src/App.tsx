// Root React component that mounts the configured router.
import { RouterProvider } from "react-router-dom";
import { router } from "@/routes/AppRoutes";

export const App = () => <RouterProvider router={router} />;
