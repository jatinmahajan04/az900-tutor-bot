import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        azure: {
          50: "#eff6ff",
          500: "#0078d4",
          600: "#0062b1",
          700: "#004f8f",
        },
      },
    },
  },
  plugins: [],
};

export default config;
