import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#FF8C42",
        secondary: "#6C63FF",
        accent: "#FFD93D",
        success: "#6BCB77",
        "bg-main": "#FFF8F0",
      },
      fontFamily: {
        story: ["var(--font-story)", "cursive"],
      },
      borderRadius: {
        "story-sm": "12px",
        "story-md": "20px",
        "story-lg": "32px",
      },
    },
  },
  plugins: [],
};
export default config;
