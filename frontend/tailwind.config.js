/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#12211A",
        panel: "#192A21",
        panelRaised: "#21362B",
        panelHighlight: "#2A4437",
        borderSubtle: "rgba(255, 255, 255, 0.08)",
        borderStrong: "rgba(255, 255, 255, 0.16)",
        textPrimary: "#F2FBF6",
        textSecondary: "#98B5A5",
        textDisabled: "#5D7569",
        accent: {
          DEFAULT: "#34D399", // Mint / Emerald Green
          hover: "#10B981",
          subtle: "rgba(52, 211, 153, 0.15)",
        },
        live: {
          DEFAULT: "#34D399",
          subtle: "rgba(52, 211, 153, 0.15)",
        },
        severity: {
          critical: "#EF4444",
          high: "#F97316",
          moderate: "#F5B400",
          low: "#34D399",
          info: "#5D7569",
        },
        verification: {
          verified: "#34D399",
          review: "#F5B400",
          rejected: "#EF4444",
          unverified: "#5D7569",
        },
      },
      fontFamily: {
        display: [
          '"Rajdhani"',
          '"Plus Jakarta Sans"',
          "sans-serif",
        ],
        sans: [
          '"Plus Jakarta Sans"',
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"IBM Plex Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        DEFAULT: "6px",
        card: "8px",
      },
    },
  },
  plugins: [],
};
