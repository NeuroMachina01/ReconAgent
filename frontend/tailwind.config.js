/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0B1220",
        paper: "#121B2E",
        signal: "#4C7DFF",
        ledger: "#34D399",
        flag: "#F5A623",
        alarm: "#FF6B6B",
        chalk: "#E7ECF5",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        display: ["Space Grotesk", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      }
    },
  },
  plugins: [],
}
