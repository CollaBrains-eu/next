import { describe, expect, it } from "vitest";
import { buildMapsUrl, isApplePlatform } from "./maps";

const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const IPAD_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
const MAC_DESKTOP_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36";
const WINDOWS_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

describe("isApplePlatform", () => {
  it("detects iPhone via user agent", () => {
    expect(isApplePlatform(IPHONE_UA, "iPhone", 5)).toBe(true);
  });

  it("detects iPad via touch-capable MacIntel platform", () => {
    expect(isApplePlatform(IPAD_UA, "MacIntel", 5)).toBe(true);
  });

  it("does not treat a non-touch Mac desktop as Apple-mobile", () => {
    expect(isApplePlatform(MAC_DESKTOP_UA, "MacIntel", 0)).toBe(false);
  });

  it("returns false for Android", () => {
    expect(isApplePlatform(ANDROID_UA, "Linux armv8l", 5)).toBe(false);
  });

  it("returns false for Windows", () => {
    expect(isApplePlatform(WINDOWS_UA, "Win32", 0)).toBe(false);
  });
});

describe("buildMapsUrl", () => {
  it("builds an Apple Maps link on iOS", () => {
    const url = buildMapsUrl("RDW Keuringsstation, Arnhem", IPHONE_UA, "iPhone", 5);
    expect(url).toBe("https://maps.apple.com/?q=RDW%20Keuringsstation%2C%20Arnhem");
  });

  it("builds a Google Maps link on desktop", () => {
    const url = buildMapsUrl("RDW Keuringsstation, Arnhem", WINDOWS_UA, "Win32", 0);
    expect(url).toBe("https://www.google.com/maps/search/?api=1&query=RDW%20Keuringsstation%2C%20Arnhem");
  });
});
