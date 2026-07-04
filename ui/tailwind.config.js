/** Tailwind color names are bound to the design-token CSS custom properties
 *  declared in src/index.css — components never hardcode hex values. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        raised: "var(--surface-raised)",
        body: "var(--text)",
        dim: "var(--text-dim)",
        signal: "var(--signal)",
        cost: "var(--cost)",
        danger: "var(--danger)",
        line: "var(--border)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        sans: ['"IBM Plex Sans"', "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
    },
  },
  plugins: [],
};
