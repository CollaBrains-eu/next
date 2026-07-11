export interface StatusStage {
  key: string;
  label: string;
}

/**
 * Read-only indicator of where an entity's status sits among a fixed,
 * ordered set of stages — distinct from Stepper, which is an interactive
 * multi-step wizard control with a "next" action. This never advances
 * itself; the caller drives currentKey (e.g. from a toggle or a select).
 */
export function StatusPipeline({
  stages,
  currentKey,
}: {
  stages: StatusStage[];
  currentKey: string;
}) {
  const currentIndex = stages.findIndex((s) => s.key === currentKey);

  return (
    <ol className="flex items-center" aria-label="Status">
      {stages.map((stage, index) => {
        const isCurrent = index === currentIndex;
        const isPast = currentIndex !== -1 && index < currentIndex;
        const isReached = isCurrent || isPast;
        const isLast = index === stages.length - 1;
        return (
          <li key={stage.key} className="flex items-center">
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold transition-colors duration-base ${
                isCurrent ? "bg-accent text-white" : isReached ? "text-accent" : "text-ink-3"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  isCurrent ? "bg-white" : isReached ? "bg-accent" : "bg-edge"
                }`}
              />
              {stage.label}
            </span>
            {!isLast && <span className={`mx-1 h-0.5 w-6 rounded-full ${isPast ? "bg-accent" : "bg-edge"}`} />}
          </li>
        );
      })}
    </ol>
  );
}
