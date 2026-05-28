/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-base": "#0f0f0f",
        "bg-surface": "#1a1a1a",
        "bg-hover": "#252525",
        "fg-default": "#d1d4dc",
        "fg-muted": "#787b86",
        "accent-blue": "#2962ff",
        "accent-green": "#26a69a",
        "accent-red": "#ef5350",
        "border-default": "#2a2e39",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
