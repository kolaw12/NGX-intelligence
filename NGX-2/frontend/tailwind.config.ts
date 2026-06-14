import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: {
        DEFAULT: "1rem",
        sm: "1.5rem",
        lg: "2rem",
        xl: "2.5rem",
        "2xl": "3rem",
      },
      screens: {
        "2xl": "1200px",
      },
    },
    extend: {
      colors: {
        navy: {
          DEFAULT: "#131E47",
          50: "#E6E8F0",
          100: "#C6CBDD",
          200: "#959DBC",
          300: "#646F9C",
          400: "#3E4A7C",
          500: "#2A356A",
          600: "#1D2858",
          700: "#131E47",
          800: "#0C1535",
          900: "#070D24",
          950: "#040818",
        },
        royal: {
          DEFAULT: "#2D3B84",
          50: "#E8EAF6",
          100: "#C5CBE9",
          200: "#929BD2",
          300: "#5F6BBC",
          400: "#3D4BA0",
          500: "#2D3B84",
          600: "#243069",
          700: "#1B244F",
          800: "#131A39",
          900: "#0C1126",
        },
        cyan: {
          DEFAULT: "#00DCDC",
          50: "#DDFFFF",
          100: "#B5FBFB",
          200: "#7AF6F6",
          300: "#3FEFEF",
          400: "#0DE5E5",
          500: "#00DCDC",
          600: "#00B0B0",
          700: "#008585",
          800: "#005C5C",
          900: "#003333",
        },
        gold: {
          DEFAULT: "#E89A35",
          50: "#FCEFDA",
          100: "#F8DAA8",
          200: "#F4C376",
          300: "#EFAC45",
          400: "#E89A35",
          500: "#C97D1D",
          600: "#9D6217",
          700: "#714611",
          800: "#452B0A",
          900: "#211404",
        },
        background: "#F4F7FC",
        foreground: "#0B1437",
        surface: {
          DEFAULT: "#FFFFFF",
          elevated: "#F8FAFD",
          muted: "#EEF2F9",
        },
        border: {
          DEFAULT: "rgba(15,20,55,0.08)",
          strong: "rgba(15,20,55,0.16)",
        },
        muted: {
          DEFAULT: "#EEF2F9",
          foreground: "#64748B",
        },
        success: {
          DEFAULT: "#22C55E",
          soft: "rgba(34,197,94,0.12)",
        },
        danger: {
          DEFAULT: "#EF4444",
          soft: "rgba(239,68,68,0.12)",
        },
        warning: {
          DEFAULT: "#F59E0B",
          soft: "rgba(245,158,11,0.12)",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "display-2xl": ["clamp(2.75rem, 5vw, 4.5rem)", { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        "display-xl": ["clamp(2.25rem, 4vw, 3.5rem)", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "display-lg": ["clamp(1.875rem, 3vw, 2.5rem)", { lineHeight: "1.15", letterSpacing: "-0.015em" }],
      },
      borderRadius: {
        lg: "0.75rem",
        xl: "1rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(15,20,55,0.04), 0 4px 16px -8px rgba(15,20,55,0.08)",
        elevated: "0 4px 8px -2px rgba(15,20,55,0.06), 0 12px 32px -8px rgba(15,20,55,0.12)",
        glow: "0 0 0 1px rgba(0,220,220,0.30), 0 8px 24px -8px rgba(0,220,220,0.28)",
      },
      backgroundImage: {
        "radial-navy":
          "radial-gradient(1200px 600px at 50% -10%, rgba(45,59,132,0.55), transparent 60%), radial-gradient(800px 400px at 90% 10%, rgba(0,220,220,0.15), transparent 60%)",
        "radial-light":
          "radial-gradient(1200px 600px at 50% -10%, rgba(0,220,220,0.10), transparent 60%), radial-gradient(900px 500px at 88% 5%, rgba(232,154,53,0.08), transparent 60%), radial-gradient(700px 400px at 5% 30%, rgba(45,59,132,0.08), transparent 60%)",
        "radial-glow":
          "radial-gradient(600px 300px at 10% 10%, rgba(0,220,220,0.14), transparent 60%), radial-gradient(600px 300px at 90% 90%, rgba(232,154,53,0.10), transparent 60%)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ticker-scroll": {
          from: { transform: "translateX(0%)" },
          to: { transform: "translateX(-50%)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(0,220,220,0.45)" },
          "50%": { boxShadow: "0 0 0 8px rgba(0,220,220,0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out",
        "ticker-scroll": "ticker-scroll 60s linear infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
};

export default config;
