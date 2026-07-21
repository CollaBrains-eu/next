import { useId } from "react";

export function BrandMark({ size = 28 }: { size?: number }) {
  const gradientId = useId();

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" role="img" aria-label="CollaBrains">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop offset="0%" style={{ stopColor: "var(--gradient-brand-from)" }} />
          <stop offset="100%" style={{ stopColor: "var(--gradient-brand-to)" }} />
        </linearGradient>
      </defs>
      <rect x="1" y="5" width="14" height="14" rx="5" fill={`url(#${gradientId})`} />
      <rect x="9" y="1" width="14" height="14" rx="5" fill={`url(#${gradientId})`} opacity="0.55" />
    </svg>
  );
}
