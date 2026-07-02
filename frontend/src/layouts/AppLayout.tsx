// Main application layout wrapping navigation, sidebar, footer, and routed content.
import { Outlet } from "react-router-dom";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { ToastViewport } from "@/components/ui/toast";

export const AppLayout = () => (
  <div className="min-h-screen bg-radial-field">
    <Navbar />
    <div className="mx-auto flex max-w-7xl">
      <Sidebar />
      <main className="min-h-[calc(100vh-8rem)] flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
    <Footer />
    <ToastViewport />
  </div>
);
