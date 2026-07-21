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
    expect(tokensCss).toContain("--accent: #6C63FF;");
  });
});

describe(".glass-surface utility", () => {
  it("is defined once, using the glass background token", () => {
    expect(indexCss).toContain(".glass-surface");
    expect(indexCss).toContain("var(--bg-card-glass)");
    expect(indexCss).toContain("backdrop-filter: blur(16px);");
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
