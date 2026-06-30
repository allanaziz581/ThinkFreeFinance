/** @type {import('tailwindcss').Config}
 *
 * Design system, grounded in three sources:
 *  - UI UX Pro Max generator (dark, premium, fintech): OLED-leaning neutral
 *    canvas, single accent, "no AI purple/pink gradients", visible focus,
 *    150-300ms hovers, prefers-reduced-motion, responsive 375/768/1024/1440.
 *  - Refero / Vercel spec: 99% achromatic, accent used sparingly, elevation
 *    through hairline borders not heavy shadows, tight radii, negative display
 *    tracking, filled-primary + outlined-secondary button pair.
 *  - Refero / Mercury spec: Deep Space neutral darks, "light not shadow",
 *    4px spacing base, 1200px max-width.
 *
 * Hard constraints: max two corner radii, one type scale, restrained
 * cyan-only accent, subtle 2px hover lifts, one shared easing curve.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Neutral (achromatic) dark canvas. No warm tint, no chroma.
        ink: {
          900: "#0A0B0D", // page background
          800: "#101214", // surface / card
          700: "#14171A", // raised surface
          600: "#181C20", // hover surface
        },
        line: {
          DEFAULT: "rgba(255,255,255,0.08)", // hairline border
          strong: "rgba(255,255,255,0.14)", // hover / emphasis border
        },
        ash: {
          100: "#F4F6F8", // primary text
          300: "#9BA3AD", // secondary text
          500: "#6B7280", // tertiary text
        },
        // The single chromatic accent. Used sparingly (links, primary button,
        // brand mark, a few small marks). Never as a large gradient field.
        brand: {
          DEFAULT: "#38BDF8",
          deep: "#2A93C9",
          soft: "#7DD3FC",
          glow: "rgba(56,189,248,0.10)",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
      },
      letterSpacing: {
        tightest: "-0.03em",
      },
      maxWidth: {
        page: "1160px",
      },
      // Exactly two custom radii beyond none: 6px (controls, chips) and 12px
      // (cards, panels). Everything maps to one of these.
      borderRadius: {
        ctl: "6px",
        panel: "12px",
      },
      transitionTimingFunction: {
        std: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      spacing: {
        4.5: "1.125rem",
        18: "4.5rem",
        22: "5.5rem",
        30: "7.5rem",
      },
    },
  },
  plugins: [],
};
