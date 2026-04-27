/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pill: {
          bg: "rgba(20, 20, 20, 0.96)",
          text: "#e0e0e0",
          accent: "#10b981",
        },
        overlay: {
          bg: "rgba(15, 15, 15, 0.98)",
          text: "#f0f0f0",
          code: "#1e1e1e",
        },
      },
    },
  },
  plugins: [],
}
