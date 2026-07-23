import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import tailwindConfig from "../../tailwind.config.js";

// Read the raw CSS text via the filesystem rather than a Vite `?raw` import --
// Vite's CSS plugin short-circuits `?raw` queries for `.css` files under the
// Node/SSR context Vitest runs tests in, silently returning an empty string.
// Also deliberately NOT `new URL("./tokens.css", import.meta.url)` -- Vite
// statically detects that exact call pattern and rewrites it into a
// dev-server asset URL (`http://localhost:.../...`) instead of leaving it as
// a real file:// path, which breaks readFileSync. Plain path.join sidesteps
// that rewrite.
const tokensCss = readFileSync(join(import.meta.dirname, "tokens.css"), "utf-8");
const indexCss = readFileSync(join(import.meta.dirname, "..", "index.css"), "utf-8");

describe("design tokens", () => {
  it("defines a two-stop brand gradient", () => {
    expect(tokensCss).toContain("--gradient-brand-from");
    expect(tokensCss).toContain("--gradient-brand-to");
    expect(tokensCss).toContain(
      "--gradient-brand: linear-gradient(135deg, var(--gradient-brand-from), var(--gradient-brand-to));"
    );
  });

  it("defines a glass-surface background token", () => {
    expect(tokensCss).toContain("--bg-card-glass");
  });

  it("defines a named radius scale without touching existing tokens", () => {
    expect(tokensCss).toContain("--radius-sm: 8px;");
    expect(tokensCss).toContain("--radius-md: 12px;");
    expect(tokensCss).toContain("--radius-lg: 16px;");
    expect(tokensCss).toContain("--radius-xl: 24px;");
    expect(tokensCss).toContain("--accent: #5A52E8;");
  });
});

describe(".glass-surface utility", () => {
  it("is defined once, using the glass background token", () => {
    expect(indexCss).toContain(".glass-surface");
    expect(indexCss).toContain("var(--bg-card-glass)");
    expect(indexCss).toContain("backdrop-filter: blur(16px);");
  });
});

describe("WCAG AA contrast (light theme text tokens)", () => {
  // Regression test for ADR 0066: --text-3/--accent/--success/--danger were
  // computed as failing 4.5:1 against their real usage backgrounds (ADR
  // 0063), and that fix landed in docs/design/violet-design-language.html
  // but never in this file -- these values shipped to production still
  // failing. Pairs/backgrounds below match the exact usage contexts ADR
  // 0063 measured (badge text vs. its own tinted background, form
  // error-message text directly on a card), not arbitrary token pairs.
  function hexToRgb(hex) {
    const m = hex.trim().match(/^#([0-9a-fA-F]{6})$/);
    if (!m) throw new Error(`not a 6-digit hex color: ${hex}`);
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function parseColor(value) {
    const hex = value.match(/^#[0-9a-fA-F]{6}$/);
    if (hex) return { rgb: hexToRgb(value), alpha: 1 };
    const rgba = value.match(
      /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)/
    );
    if (rgba) {
      return {
        rgb: [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])],
        alpha: rgba[4] !== undefined ? Number(rgba[4]) : 1,
      };
    }
    throw new Error(`unrecognized color value: ${value}`);
  }

  function compositeOverOpaque(fg, bgRgb) {
    if (fg.alpha === 1) return fg.rgb;
    return fg.rgb.map((c, i) => fg.alpha * c + (1 - fg.alpha) * bgRgb[i]);
  }

  function relativeLuminance([r, g, b]) {
    const linear = (c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    };
    const [rl, gl, bl] = [r, g, b].map(linear);
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
  }

  function contrastRatio(rgbA, rgbB) {
    const [lLight, lDark] = [relativeLuminance(rgbA), relativeLuminance(rgbB)].sort(
      (a, b) => b - a
    );
    return (lLight + 0.05) / (lDark + 0.05);
  }

  // Read only the :root (light) block -- it appears before `.dark {` in the
  // file, and a non-global regex match returns the first occurrence.
  function readVar(name) {
    const match = tokensCss.match(new RegExp(`--${name}:\\s*([^;]+);`));
    if (!match) throw new Error(`token not found: --${name}`);
    return parseColor(match[1].trim());
  }

  const AA_NORMAL_TEXT = 4.5;

  it("--text-3 on --bg-card and --bg both meet 4.5:1", () => {
    const text3 = readVar("text-3").rgb;
    expect(contrastRatio(text3, readVar("bg-card").rgb)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
    expect(contrastRatio(text3, readVar("bg").rgb)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });

  it("--accent on --accent-bg (badge/secondary-button text) meets 4.5:1", () => {
    const accent = readVar("accent").rgb;
    const accentBg = readVar("accent-bg").rgb;
    expect(contrastRatio(accent, accentBg)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });

  it("--success on --success-bg (composited over --bg-card) meets 4.5:1", () => {
    const success = readVar("success").rgb;
    const successBg = compositeOverOpaque(readVar("success-bg"), readVar("bg-card").rgb);
    expect(contrastRatio(success, successBg)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });

  it("--danger on --bg-card (form error-message text) meets 4.5:1", () => {
    const danger = readVar("danger").rgb;
    expect(contrastRatio(danger, readVar("bg-card").rgb)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });
});

describe("tailwind config", () => {
  it("exposes the gradient-brand background-image utility", () => {
    expect(tailwindConfig.theme.extend.backgroundImage).toEqual({
      "gradient-brand": "var(--gradient-brand)",
    });
  });

  it("exposes ds-prefixed radius utilities without overriding Tailwind's built-in scale", () => {
    const radius = tailwindConfig.theme.extend.borderRadius;
    expect(radius).toEqual({
      "ds-sm": "var(--radius-sm)",
      "ds-md": "var(--radius-md)",
      "ds-lg": "var(--radius-lg)",
      "ds-xl": "var(--radius-xl)",
    });
    expect(radius).not.toHaveProperty("lg");
    expect(radius).not.toHaveProperty("xl");
  });
});
