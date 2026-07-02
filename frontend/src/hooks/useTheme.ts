// Hook for consuming the AstroMineAI display theme context.
import { useContext } from "react";
import { ThemeContext } from "@/contexts/theme-context";

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
};
