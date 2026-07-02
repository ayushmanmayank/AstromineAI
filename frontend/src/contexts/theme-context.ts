// Theme context value and React context shared by the provider and hook.
import { createContext } from "react";

export type Theme = "dark" | "contrast";

export type ThemeContextValue = {
  theme: Theme;
  toggleTheme: () => void;
};

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
