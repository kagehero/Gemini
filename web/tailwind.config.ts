import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        wash: "#f5f4f0",
        ink: "#1a1917",
        muted: "#6f6e6a",
        accent: "#2a4a6e",
        "accent-hover": "#1e3a56",
        line: "#e5e3de",
        card: "#fdfcfa",
      },
      fontFamily: {
        sans: ["var(--font-noto)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
