export function isApplePlatform(
  userAgent: string = navigator.userAgent,
  platform: string = navigator.platform,
  maxTouchPoints: number = navigator.maxTouchPoints,
): boolean {
  if (/iPhone|iPad|iPod/.test(userAgent)) return true;
  // iPadOS Safari reports a desktop Mac user agent; only a touch-capable
  // "MacIntel" is actually an iPad.
  if (platform === "MacIntel" && maxTouchPoints > 1) return true;
  return false;
}

export function buildMapsUrl(
  location: string,
  userAgent: string = navigator.userAgent,
  platform: string = navigator.platform,
  maxTouchPoints: number = navigator.maxTouchPoints,
): string {
  const query = encodeURIComponent(location);
  return isApplePlatform(userAgent, platform, maxTouchPoints)
    ? `https://maps.apple.com/?q=${query}`
    : `https://www.google.com/maps/search/?api=1&query=${query}`;
}
