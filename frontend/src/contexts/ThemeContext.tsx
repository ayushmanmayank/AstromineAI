// Theme provider for toggling dark and high-contrast mission display modes.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeContext, type Theme } from "@/contexts/theme-context";

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    document.documentElement.classList.toggle("contrast", theme === "contrast");
  }, [theme]);

  const value = useMemo(
    () => ({
      theme,
      toggleTheme: () => setTheme((current) => (current === "dark" ? "contrast" : "dark")),
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
