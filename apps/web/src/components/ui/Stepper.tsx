export interface StepItem {
  label: string;
}

export function Stepper({ steps, currentIndex }: { steps: StepItem[]; currentIndex: number }) {
  return (
    <ol className="mb-3.5 flex items-start">
      {steps.map((step, index) => {
        const complete = index < currentIndex;
        const active = index === currentIndex;
        const isLast = index === steps.length - 1;
        return (
          <li key={step.label} className="relative flex flex-1 flex-col items-center gap-1.5">
            <span
              className={`z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-base ease-spring ${
                complete
                  ? "border-accent bg-accent text-white"
                  : active
                    ? "border-accent text-accent"
                    : "border-edge bg-surface text-ink-3"
              }`}
            >
              {complete ? (
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                index + 1
              )}
            </span>
            <span className={`text-[11.5px] ${active ? "font-semibold text-ink" : "text-ink-2"}`}>{step.label}</span>
            {!isLast && (
              <span
                className={`absolute left-1/2 top-3.5 h-0.5 w-full ${complete ? "bg-accent" : "bg-edge"}`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
