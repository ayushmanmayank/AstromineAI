// Landing page introducing AstroMineAI and directing researchers into the workflow.
import { Link } from "react-router-dom";
import { ArrowRight, BrainCircuit, LineChart, ShieldCheck, Telescope } from "lucide-react";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ROUTES } from "@/constants/routes";

const features = [
  { title: "AI mineral inference", icon: BrainCircuit, text: "Estimate asteroid mineral composition from calibrated imagery and spectral products." },
  { title: "Research dashboards", icon: LineChart, text: "Track confidence, recent model activity, and review queues from one command surface." },
  { title: "Explainability-ready", icon: ShieldCheck, text: "Prepare saliency overlays and probability tables for scientific review." },
];

export const Home = () => (
  <div className="space-y-12">
    <section className="grid min-h-[68vh] items-center gap-10 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-7">
        <SectionHeader
          eyebrow="NASA-inspired AI research platform"
          title="AstroMineAI"
          description="Asteroid mineral composition analysis for mission researchers evaluating metallic, silicate, and carbonaceous signatures across observation products."
        />
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to={ROUTES.upload}>
              Get Started <ArrowRight className="h-5 w-5" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link to={ROUTES.dashboard}>View Dashboard</Link>
          </Button>
        </div>
      </div>
      <div className="relative min-h-[420px] overflow-hidden rounded-xl border border-space-border bg-space-card shadow-glow mission-grid">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_52%_48%,rgba(0,194,255,0.35),transparent_14%),radial-gradient(circle_at_55%_51%,rgba(124,58,237,0.2),transparent_24%)]" />
        <div className="absolute left-8 top-8 rounded-xl border border-space-border bg-black/30 p-4 backdrop-blur">
          <Telescope className="mb-3 h-8 w-8 text-secondary" />
          <p className="max-w-xs text-sm text-slate-300">Mission-grade interface for turning observation products into structured composition evidence.</p>
        </div>
      </div>
    </section>
    <section className="grid gap-4 md:grid-cols-3">
      {features.map((feature) => (
        <Card key={feature.title} className="p-5 transition duration-200 hover:-translate-y-1 hover:border-secondary/40">
          <feature.icon className="mb-4 h-8 w-8 text-secondary" />
          <h2 className="text-lg font-semibold text-white">{feature.title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">{feature.text}</p>
        </Card>
      ))}
    </section>
  </div>
);
