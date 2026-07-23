// Last-resort fallback for Sentry's top-level ErrorBoundary (see main.tsx) --
// deliberately not using useTranslation or design-system components: this
// renders when the React tree itself has crashed, possibly including i18n/
// router context, so it needs to work without depending on anything that
// could itself be broken. Tailwind's CSS custom properties (tokens.css) are
// safe since they're plain global CSS, not React.
export function ErrorFallback() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[var(--bg)] px-6 text-center">
      <p className="text-lg font-semibold text-[var(--text)]">Something went wrong.</p>
      <p className="text-sm text-[var(--text-2)]">Please reload the page. If this keeps happening, contact support.</p>
    </div>
  );
}
