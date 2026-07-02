// Top navigation bar for the AstroMineAI application shell.
import { Link, NavLink } from "react-router-dom";
import { Rocket } from "lucide-react";
import { NAVIGATION_ITEMS } from "@/constants/navigation";
import { ROUTES } from "@/constants/routes";
import { cn } from "@/utils/cn";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

export const Navbar = () => (
  <header className="sticky top-0 z-40 border-b border-space-border bg-space-background/82 backdrop-blur-xl">
    <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
      <Link to={ROUTES.home} className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-lg bg-primary shadow-glow">
          <Rocket className="h-5 w-5 text-white" />
        </span>
        <span>
          <span className="block text-sm font-bold text-white">AstroMineAI</span>
          <span className="block text-xs text-slate-400">Mineral Intelligence</span>
        </span>
      </Link>
      <nav className="hidden items-center gap-1 lg:flex">
        {NAVIGATION_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "rounded-lg px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/10 hover:text-white",
                isActive && "bg-white/10 text-white",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <ThemeToggle />
    </div>
  </header>
);
