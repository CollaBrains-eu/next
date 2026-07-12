export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-lg bg-edge ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent dark:via-white/[0.08]" />
    </div>
  );
}

export function SkeletonLines({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`} data-testid="skeleton-lines">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
