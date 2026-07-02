// Responsive sidebar navigation for app pages with research workflows.
import { NavLink } from "react-router-dom";
import { NAVIGATION_ITEMS } from "@/constants/navigation";
import { cn } from "@/utils/cn";

export const Sidebar = () => (
  <aside className="hidden w-64 shrink-0 border-r border-space-border bg-space-card/45 p-4 backdrop-blur-xl lg:block">
    <div className="sticky top-20 space-y-2">
      {NAVIGATION_ITEMS.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/10 hover:text-white",
              isActive && "bg-primary/20 text-white ring-1 ring-primary/30",
            )
          }
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </NavLink>
      ))}
    </div>
  </aside>
);
