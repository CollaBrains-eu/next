import { afterEach, describe, expect, it } from "vitest";
import { syncLanguage } from "./auth";
import i18n from "./i18n";

describe("syncLanguage", () => {
  afterEach(() => {
    i18n.changeLanguage("en");
  });

  it("maps a known preferred_language name to its i18next code", () => {
    syncLanguage("Nederlands");
    expect(i18n.language).toBe("nl");
  });

  it("maps Deutsch to de", () => {
    syncLanguage("Deutsch");
    expect(i18n.language).toBe("de");
  });

  it("defaults to English when preferred_language is null", () => {
    syncLanguage(null);
    expect(i18n.language).toBe("en");
  });

  it("defaults to English for an unrecognized value rather than throwing", () => {
    syncLanguage("Klingon");
    expect(i18n.language).toBe("en");
  });
});
