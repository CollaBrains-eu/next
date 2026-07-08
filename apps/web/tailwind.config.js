/** @type {import(\"tailwindcss\").Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--bg)",
        "sidebar-surface": "var(--bg-sidebar)",
        surface: "var(--bg-card)",
        ink: "var(--text)",
        "ink-2": "var(--text-2)",
        "ink-3": "var(--text-3)",
        edge: "var(--border)",
        hover: "var(--hover)",
        active: "var(--active)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "accent-soft": "var(--accent-bg)",
        success: "var(--success)",
        "success-soft": "var(--success-bg)",
        warning: "var(--warning)",
        "warning-soft": "var(--warning-bg)",
        danger: "var(--danger)",
        "danger-soft": "var(--danger-bg)",
      },
      boxShadow: {
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
        modal: "var(--shadow-modal)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["IBM Plex Mono", "SF Mono", "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        "out-token": "cubic-bezier(.16,1,.3,1)",
        spring: "cubic-bezier(.34,1.56,.64,1)",
      },
      transitionDuration: {
        fast: "150ms",
        base: "260ms",
        slow: "550ms",
      },
      keyframes: {
        ripple: {
          to: { transform: "scale(4)", opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};
