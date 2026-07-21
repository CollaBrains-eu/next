import logoSrc from "../assets/brand/collabrains-logo.png";

// The source file is the full "collabrAIns" lockup (mascot + wordmark, ~2:1,
// flat white background, no alpha). We only want the mascot here, so the
// image is rendered oversized as a CSS background and shifted so the crop
// window lands on the mascot's region -- any leftover white margin blends
// into the badge's own white background seamlessly. These multipliers are
// tuned by eye against the actual image, not derived from a formula a
// reader could re-check; nudge them visually if the framing looks off.
const RENDERED_WIDTH_MULTIPLIER = 3; // full (untrimmed) image width, relative to `size`
const CROP_LEFT_MULTIPLIER = 1.5; // left edge of the visible window, relative to `size`
const CROP_TOP_MULTIPLIER = 0.055; // top edge of the visible window, relative to `size`

export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <span
      role="img"
      aria-label="CollaBrains"
      className="inline-block shrink-0 overflow-hidden rounded-ds-sm bg-white bg-no-repeat"
      style={{
        width: size,
        height: size,
        backgroundImage: `url(${logoSrc})`,
        backgroundSize: `${size * RENDERED_WIDTH_MULTIPLIER}px auto`,
        backgroundPosition: `-${size * CROP_LEFT_MULTIPLIER}px -${size * CROP_TOP_MULTIPLIER}px`,
      }}
    />
  );
}
