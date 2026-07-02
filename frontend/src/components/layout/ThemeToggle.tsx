// Icon-only theme toggle for dark and high-contrast mission modes.
import { Moon, SunMedium } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";

export const ThemeToggle = () => {
  const { theme, toggleTheme } = useTheme();
  const Icon = theme === "dark" ? Moon : SunMedium;

  return (
    <Button
      aria-label="Toggle display contrast"
      title="Toggle display contrast"
      size="icon"
      variant="secondary"
      onClick={toggleTheme}
    >
      <Icon className="h-5 w-5" />
    </Button>
  );
};
