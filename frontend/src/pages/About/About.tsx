// About page explaining architecture, stack, research inspiration, and team structure.
import { Cpu, FlaskConical, Network, Users } from "lucide-react";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Card } from "@/components/ui/card";

const sections = [
  {
    title: "Project architecture",
    icon: Network,
    items: ["React research console", "Axios API boundary", "TanStack Query cache", "Future FastAPI inference backend"],
  },
  {
    title: "Technology stack",
    icon: Cpu,
    items: ["React 19", "TypeScript", "Vite", "Tailwind CSS", "shadcn/ui patterns", "Recharts", "React Hook Form", "Zod"],
  },
  {
    title: "Research inspiration",
    icon: FlaskConical,
    items: ["Asteroid spectral taxonomy", "Sample-return mission analysis", "Explainable AI for scientific review", "Planetary resource mapping"],
  },
  {
    title: "Team members",
    icon: Users,
    items: ["Frontend systems", "Machine learning research", "Planetary geology", "Mission operations"],
  },
];

export const About = () => (
  <div className="space-y-8">
    <SectionHeader
      title="About AstroMineAI"
      description="A production-oriented research frontend designed for eventual integration with asteroid imagery, spectroscopy, and mineral inference systems."
    />
    <div className="grid gap-4 md:grid-cols-2">
      {sections.map((section) => (
        <Card key={section.title} className="p-5">
          <section.icon className="mb-4 h-7 w-7 text-secondary" />
          <h2 className="text-xl font-semibold text-white">{section.title}</h2>
          <ul className="mt-4 space-y-3">
            {section.items.map((item) => (
              <li key={item} className="rounded-lg border border-space-border bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
                {item}
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  </div>
);
