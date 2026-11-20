/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0b0d",
          900: "#0f1115",
          850: "#14161c",
          800: "#1a1d24",
          700: "#242833",
          600: "#2f3440",
        },
        brand: {
          400: "#8b9cff",
          500: "#6c7cff",
          600: "#5563f0",
        },
        accent: {
          silence: "#34d399",
          time: "#f59e0b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 30px -12px rgba(0,0,0,0.6)",
      },
      borderRadius: {
        xl2: "1.1rem",
      },
    },
  },
  plugins: [],
};
