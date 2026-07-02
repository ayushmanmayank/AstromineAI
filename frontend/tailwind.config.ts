// Tailwind theme tokens for the NASA-inspired AstroMineAI interface.
import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        space: {
          background: "#090B12",
          card: "#161B22",
          border: "rgba(148, 163, 184, 0.18)",
        },
        primary: "#2563EB",
        secondary: "#00C2FF",
        accent: "#7C3AED",
      },
      boxShadow: {
        glow: "0 0 42px rgba(0, 194, 255, 0.18)",
      },
      backgroundImage: {
        "radial-field":
          "radial-gradient(circle at 20% 10%, rgba(37, 99, 235, 0.24), transparent 28%), radial-gradient(circle at 85% 25%, rgba(124, 58, 237, 0.18), transparent 24%)",
      },
      animation: {
        "slow-pulse": "pulse 5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
